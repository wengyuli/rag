"""Deterministic resource-counter and ASGI authorization tests, without a DB.

Run in the backend environment:
    python -m unittest discover -s tests -p 'test_system_metrics.py' -v
"""
from collections import namedtuple
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "llamaindex_rag"))
from system_metrics import ResourceSampler, cpu_percent, parse_cpu_stat, parse_meminfo

DiskUsage = namedtuple("DiskUsage", "total used free")


class CounterTests(unittest.TestCase):
    def test_cpu_guest_is_not_double_counted(self):
        previous, cores = parse_cpu_stat("cpu 10 0 0 90 0 0 0 0 8 0\ncpu0 1\ncpu1 1\nintr 0\n")
        current, _ = parse_cpu_stat("cpu 20 0 0 180 0 0 0 0 18 0\n")
        self.assertEqual(cores, 2)
        self.assertEqual(cpu_percent(previous, current), 10.0)
        self.assertIsNone(cpu_percent(None, current))

    def test_cpu_iowait_is_idle_and_invalid_intervals_are_unknown(self):
        previous = (0,) * 8
        current = (10, 0, 0, 70, 20, 0, 0, 0)
        self.assertEqual(cpu_percent(previous, current), 10.0)
        self.assertIsNone(cpu_percent(current, current))
        # A falling individual counter is unreliable even if total rises.
        self.assertIsNone(cpu_percent(current, (100, 0, 0, 70, 19, 0, 0, 0)))
        for text in ("cpu bad\n", "cpu -1 0 0 0\n", "intr 2\n"):
            with self.assertRaises(ValueError):
                parse_cpu_stat(text)

    def test_available_memory_includes_reclaimable_cache(self):
        memory = parse_meminfo("MemTotal: 1000 kB\nMemFree: 100 kB\nMemAvailable: 650 kB\nCached: 550 kB\n")
        self.assertEqual(memory, {"total_bytes": 1024000, "used_bytes": 358400,
                                  "available_bytes": 665600, "percent": 35.0})
        for text in ("MemTotal: 1000 kB\nMemFree: 100 kB\n",
                     "MemTotal: 0 kB\nMemAvailable: 0 kB\n",
                     "MemTotal: 100 kB\nMemAvailable: 101 kB\n",
                     "MemTotal: 100 MB\nMemAvailable: 50 MB\n"):
            with self.assertRaises(ValueError):
                parse_meminfo(text)


class SamplerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rag-resource-test-")
        self.root = Path(self.temp.name)
        self.proc = self.root / "proc"
        self.cgroup = self.root / "cgroup"
        self.files = self.root / "files"
        (self.proc / "self").mkdir(parents=True)
        self.cgroup.mkdir()
        self.files.mkdir()
        self.stat(10, 90)
        (self.proc / "meminfo").write_text("MemTotal: 1000 kB\nMemAvailable: 650 kB\n")
        (self.proc / "version").write_text("Linux version 7.0.11-orbstack-test")
        (self.proc / "self/cgroup").write_text("0::/\n")
        (self.cgroup / "memory.current").write_text("123456\n")
        (self.cgroup / "memory.max").write_text("max\n")
        self.samplers = []

    def tearDown(self):
        for sampler in self.samplers:
            sampler.stop()
        self.temp.cleanup()

    def stat(self, busy, idle):
        (self.proc / "stat").write_text(f"cpu {busy} 0 0 {idle} 0 0 0 0 0 0\ncpu0 1\ncpu1 1\n")

    def make_sampler(self, **kwargs):
        sampler = ResourceSampler(self.files, self.proc, self.cgroup,
                                  in_container=kwargs.pop("in_container", True), **kwargs)
        self.samplers.append(sampler)
        return sampler

    def test_sample_first_cpu_unknown_then_real_delta_and_disk_filesystem(self):
        sampler = self.make_sampler()
        with patch("system_metrics.shutil.disk_usage", return_value=DiskUsage(1000, 400, 580)):
            first = sampler.sample()
            self.assertIsNone(first["cpu"]["percent"])
            self.assertEqual(first["cpu"]["logical_cores"], 2)
            self.stat(40, 160)
            second = sampler.sample()
        self.assertEqual(second["cpu"]["percent"], 30.0)
        self.assertEqual(second["disk"]["percent"], 40.0)
        self.assertEqual(second["disk"]["free_bytes"], 580)
        self.assertEqual(second["memory"]["percent"], 35.0)
        self.assertEqual(second["backend"], {"memory_bytes": 123456, "memory_limit_bytes": None})
        self.assertEqual(second["scope"]["kind"], "docker_vm")
        self.assertEqual(second["errors"], [])
        self.assertEqual(second["history"][-1]["timestamp"], second["sampled_at"])
        self.assertTrue(second["sampled_at"].endswith("+00:00"))

    def test_snapshot_is_a_copy_and_does_not_sample(self):
        sampler = self.make_sampler()
        sampler.sample()
        with patch("pathlib.Path.read_text", side_effect=AssertionError("request did I/O")), \
             patch("system_metrics.shutil.disk_usage", side_effect=AssertionError("request did I/O")):
            snapshot = sampler.snapshot()
            snapshot["memory"]["percent"] = -10
            snapshot["history"][0]["memory_percent"] = -20
            self.assertEqual(sampler.snapshot()["memory"]["percent"], 35.0)
            self.assertEqual(sampler.snapshot()["history"][0]["memory_percent"], 35.0)

    def test_history_is_bounded(self):
        sampler = self.make_sampler()
        for i in range(65):
            self.stat(10 + i, 90 + i)
            sampler.sample()
        history = sampler.snapshot()["history"]
        self.assertEqual(len(history), 60)
        self.assertEqual(history[-1]["cpu_percent"], 50.0)

    def test_missing_cpu_resets_baseline_and_recovers(self):
        sampler = self.make_sampler()
        sampler.sample()
        (self.proc / "stat").unlink()
        missing = sampler.sample()
        self.assertIsNone(missing["cpu"]["percent"])
        self.assertIsNone(missing["cpu"]["logical_cores"])
        self.assertTrue(missing["errors"])
        self.stat(30, 170)
        self.assertIsNone(sampler.sample()["cpu"]["percent"])
        self.stat(40, 260)
        self.assertEqual(sampler.sample()["cpu"]["percent"], 10.0)

    def test_invalid_memory_and_failed_disk_are_not_reported_as_zero(self):
        sampler = self.make_sampler()
        (self.proc / "meminfo").write_text("MemTotal: invalid kB\n")
        with patch("system_metrics.shutil.disk_usage", side_effect=OSError("unmounted")):
            result = sampler.sample()
        self.assertTrue(all(value is None for value in result["memory"].values()))
        self.assertIsNone(result["disk"]["percent"])
        self.assertIsNone(result["disk"]["total_bytes"])
        self.assertIsNone(result["history"][-1]["memory_percent"])
        self.assertIsNone(result["history"][-1]["disk_percent"])
        self.assertEqual(len(result["errors"]), 2)

    def test_cgroup_membership_and_limit_and_missing_stats(self):
        group = self.cgroup / "backend"
        group.mkdir()
        (group / "memory.current").write_text("4321\n")
        (group / "memory.max").write_text("65536\n")
        (self.proc / "self/cgroup").write_text("0::/backend\n")
        sampler = self.make_sampler()
        self.assertEqual(sampler.sample()["backend"], {"memory_bytes": 4321, "memory_limit_bytes": 65536})
        (group / "memory.current").unlink()
        result = sampler.sample()
        self.assertEqual(result["backend"], {"memory_bytes": None, "memory_limit_bytes": None})
        self.assertTrue(any("cgroup v2" in error for error in result["errors"]))
        (self.proc / "self/cgroup").write_text("0::/../escape\n")
        with self.assertRaises(ValueError):
            sampler._container_memory()

    def test_scope_does_not_treat_every_container_as_a_vm(self):
        (self.proc / "version").write_text("Linux version 6.12-generic")
        self.assertEqual(self.make_sampler().snapshot()["scope"]["kind"], "docker_linux")
        self.assertEqual(self.make_sampler(in_container=False).snapshot()["scope"]["kind"], "linux_host")
        (self.proc / "stat").unlink()
        self.assertEqual(self.make_sampler(in_container=False).snapshot()["scope"]["kind"], "process")

    def test_start_is_idempotent_and_stop_joins_background_sampler(self):
        sampler = self.make_sampler(interval=0.01)
        sampled = threading.Event()
        original = sampler.sample
        calls = []

        def tracked_sample():
            result = original()
            calls.append(1)
            if len(calls) >= 2:
                sampled.set()
            return result

        with patch.object(sampler, "sample", side_effect=tracked_sample):
            sampler.start()
            first_thread = sampler._thread
            sampler.start()
            self.assertIs(first_thread, sampler._thread)
            self.assertTrue(sampled.wait(timeout=1), "Background sampler did not run")
            sampler.stop()
            self.assertFalse(first_thread.is_alive())
            self.assertIsNone(sampler._thread)


class MetricsRouteTests(unittest.TestCase):
    def test_admin_only_cached_resource_endpoint(self):
        from fastapi import Depends, FastAPI, HTTPException
        from fastapi.testclient import TestClient
        from dependencies import get_current_user, oauth2_scheme
        from routers import system

        def identity(token=Depends(oauth2_scheme)):
            if token not in ("admin", "member"):
                raise HTTPException(401)
            return SimpleNamespace(role=token)

        app = FastAPI()
        app.include_router(system.router)
        app.dependency_overrides[get_current_user] = identity
        with TestClient(app) as client, patch.object(system, "get_metrics_snapshot", return_value={"sampled_at": "test"}) as read:
            self.assertEqual(client.get("/api/system/metrics").status_code, 401)
            self.assertEqual(client.get("/api/system/metrics?token=admin").status_code, 401)
            self.assertEqual(client.get("/api/system/metrics", headers={"Authorization": "Bearer member"}).status_code, 403)
            self.assertEqual(client.get("/api/system/metrics", headers={"Authorization": "Bearer invalid"}).status_code, 401)
            response = client.get("/api/system/metrics", headers={"Authorization": "Bearer admin"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"sampled_at": "test"})
            self.assertEqual(response.headers["cache-control"], "no-store")
            read.assert_called_once_with()


if __name__ == "__main__":
    unittest.main(verbosity=2)
