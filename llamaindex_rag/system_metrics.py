"""Read-only Linux/Docker resource sampling with a bounded in-memory history.

CPU counters follow https://docs.kernel.org/filesystems/proc.html : guest time
is already included in user/nice, so only the first eight counters are summed.
Container memory follows https://docs.kernel.org/admin-guide/cgroup-v2.html .
No Docker socket, elevated container privileges, or external service is needed.
"""
from collections import deque
from copy import deepcopy
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import shutil
import threading

logger = logging.getLogger(__name__)
SAMPLE_INTERVAL_SECONDS = 2
HISTORY_LENGTH = 60


def parse_cpu_stat(content):
    """Return the aggregate counters and system core count from /proc/stat."""
    lines = content.splitlines()
    aggregate = next((line.split()[1:] for line in lines if line.startswith("cpu ")), None)
    if aggregate is None or len(aggregate) < 4:
        raise ValueError("缺少 CPU 计数器")
    counters = [int(value) for value in aggregate[:8]]
    if any(value < 0 for value in counters):
        raise ValueError("CPU 计数器无效")
    counters += [0] * (8 - len(counters))
    cores = sum(1 for line in lines if line.split() and line.split()[0][3:].isdigit()
                and line.startswith("cpu"))
    return tuple(counters), cores or None


def cpu_percent(previous, current):
    """Average busy CPU percentage across all visible cores, or unknown."""
    if previous is None:
        return None
    deltas = [new - old for old, new in zip(previous, current)]
    # Counters can reset; Linux also documents that iowait can decrease.
    # Such intervals do not represent a reliable utilization sample.
    if any(value < 0 for value in deltas) or sum(deltas) <= 0:
        return None
    total = sum(deltas)
    idle = deltas[3] + deltas[4]
    return round(100 * (total - idle) / total, 1)


def parse_meminfo(content):
    values = {}
    for line in content.splitlines():
        key, _, raw = line.partition(":")
        if key not in ("MemTotal", "MemAvailable"):
            continue
        parts = raw.split()
        if len(parts) != 2 or parts[1] != "kB":
            raise ValueError("内存计数器单位无效")
        values[key] = int(parts[0]) * 1024
    total, available = values.get("MemTotal"), values.get("MemAvailable")
    if total is None or available is None or total <= 0 or not 0 <= available <= total:
        raise ValueError("内存计数器缺失或无效")
    # MemAvailable includes reclaimable page cache; MemFree alone overstates use.
    used = total - available
    return {"total_bytes": total, "used_bytes": used, "available_bytes": available,
            "percent": round(used * 100 / total, 1)}


class ResourceSampler:
    def __init__(self, files_path=None, proc_root="/proc", cgroup_root="/sys/fs/cgroup",
                 interval=SAMPLE_INTERVAL_SECONDS, history_length=HISTORY_LENGTH,
                 in_container=None):
        self.files_path = Path(files_path or os.getenv("FILES_ROOT", "./files")).resolve()
        self.proc_root = Path(proc_root)
        self.cgroup_root = Path(cgroup_root)
        self.interval = interval
        self._in_container = Path("/.dockerenv").exists() if in_container is None else in_container
        self._scope = self._detect_scope()
        self._history = deque(maxlen=history_length)
        self._previous_cpu = None
        self._snapshot_lock = threading.Lock()
        self._sample_lock = threading.Lock()
        self._lifecycle_lock = threading.Lock()
        self._thread = None
        self._stop_event = threading.Event()
        self._latest = self._empty_snapshot()

    def _detect_scope(self):
        if self._in_container:
            kernel = ""
            for filename in ("sys/kernel/osrelease", "version"):
                try:
                    kernel += (self.proc_root / filename).read_text(encoding="utf-8").lower()
                except OSError:
                    pass
            if "orbstack" in kernel or "linuxkit" in kernel:
                return {"kind": "docker_vm", "label": "Docker 虚拟机",
                        "description": "CPU 和内存为 Docker Linux 虚拟机的整体资源，包含其他容器；不是 Mac 物理主机总量，也不是本服务独占用量。"}
            return {"kind": "docker_linux", "label": "Docker 运行环境",
                    "description": "CPU 和内存为容器可见的 Linux 系统整体资源，包含其他服务；macOS 上通常对应 Docker 虚拟机，不代表本容器配额。"}
        if (self.proc_root / "stat").exists():
            return {"kind": "linux_host", "label": "Linux 主机",
                    "description": "CPU 和内存为当前 Linux 系统整体资源，包含系统上的其他进程。"}
        return {"kind": "process", "label": "当前运行环境",
                "description": "当前环境未提供 Linux /proc 统计，CPU 和内存显示为不可用；磁盘仍按资料目录所在文件系统统计。"}

    def _empty_snapshot(self):
        return {
            "sampled_at": None,
            "interval_seconds": self.interval,
            "scope": dict(self._scope),
            "cpu": {"percent": None, "logical_cores": None},
            "memory": {"total_bytes": None, "used_bytes": None, "available_bytes": None, "percent": None},
            "disk": {"label": "资料存储卷", "path": str(self.files_path),
                     "total_bytes": None, "used_bytes": None, "free_bytes": None, "percent": None},
            "backend": {"memory_bytes": None, "memory_limit_bytes": None},
            "history": [],
            "errors": [],
        }

    def _container_memory(self):
        """Read this container's cgroup v2, not the parent's or Docker daemon's."""
        membership = (self.proc_root / "self/cgroup").read_text(encoding="utf-8")
        relative = next((line[3:] for line in membership.splitlines() if line.startswith("0::")), None)
        if relative is None:
            raise ValueError("未提供 cgroup v2 内存统计")
        if not relative.startswith("/") or ".." in Path(relative).parts:
            raise ValueError("cgroup 路径无效")
        group = self.cgroup_root / relative.lstrip("/")
        current = int((group / "memory.current").read_text(encoding="utf-8").strip())
        limit_text = (group / "memory.max").read_text(encoding="utf-8").strip()
        limit = None if limit_text == "max" else int(limit_text)
        if current < 0 or (limit is not None and limit <= 0):
            raise ValueError("容器内存计数器无效")
        # memory.current includes page cache; it is not process RSS.
        return {"memory_bytes": current, "memory_limit_bytes": limit}

    def sample(self):
        """Read a sample off the request path; failed metrics remain null."""
        with self._sample_lock:
            result = self._empty_snapshot()
            result["sampled_at"] = datetime.now(timezone.utc).isoformat()
            try:
                current, cores = parse_cpu_stat((self.proc_root / "stat").read_text(encoding="utf-8"))
                result["cpu"] = {"percent": cpu_percent(self._previous_cpu, current), "logical_cores": cores}
                if self._previous_cpu is not None and result["cpu"]["percent"] is None:
                    result["errors"].append("CPU 计数器未递增或已重置，本次利用率不可用")
                self._previous_cpu = current
            except (OSError, ValueError, UnicodeError):
                self._previous_cpu = None
                result["errors"].append("无法读取 Linux CPU 统计")
            try:
                result["memory"] = parse_meminfo((self.proc_root / "meminfo").read_text(encoding="utf-8"))
            except (OSError, ValueError, UnicodeError):
                result["errors"].append("无法读取 Linux 内存统计")
            try:
                disk = shutil.disk_usage(self.files_path)
                if disk.total <= 0 or not 0 <= disk.used <= disk.total or not 0 <= disk.free <= disk.total:
                    raise ValueError("磁盘计数器无效")
                result["disk"].update(total_bytes=disk.total, used_bytes=disk.used,
                                      free_bytes=disk.free, percent=round(disk.used * 100 / disk.total, 1))
            except (OSError, ValueError):
                result["errors"].append("无法读取资料目录所在文件系统的磁盘统计")
            if self._in_container:
                try:
                    result["backend"] = self._container_memory()
                except (OSError, ValueError, UnicodeError):
                    result["errors"].append("后端容器内存统计不可用（需要 cgroup v2）")
            self._history.append({"timestamp": result["sampled_at"],
                                  "cpu_percent": result["cpu"]["percent"],
                                  "memory_percent": result["memory"]["percent"],
                                  "disk_percent": result["disk"]["percent"]})
            result["history"] = list(self._history)
            with self._snapshot_lock:
                self._latest = result
        return self.snapshot()

    def snapshot(self):
        with self._snapshot_lock:
            return deepcopy(self._latest)

    def _run(self, stop_event):
        while not stop_event.wait(self.interval):
            try:
                self.sample()
            except Exception:
                # A programming/unexpected platform error must not kill sampling.
                logger.exception("资源采样失败")

    def start(self):
        with self._lifecycle_lock:
            if self._thread and self._thread.is_alive():
                return
            self._previous_cpu = None
            self.sample()
            self._stop_event = threading.Event()
            self._thread = threading.Thread(target=self._run, args=(self._stop_event,),
                                            name="resource-metrics", daemon=True)
            self._thread.start()

    def stop(self):
        with self._lifecycle_lock:
            self._stop_event.set()
            if self._thread:
                self._thread.join(timeout=3)
                if not self._thread.is_alive():
                    self._thread = None


_sampler = ResourceSampler()


def start_metrics():
    _sampler.start()


def stop_metrics():
    _sampler.stop()


def get_metrics_snapshot():
    return _sampler.snapshot()
