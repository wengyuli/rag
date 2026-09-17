from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess

root = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("--manifest", default="models-manifest.json")
parser.add_argument("--model-dir", default="runtime/models/bge-reranker-base")
args = parser.parse_args()
model_dir = root / args.model_dir
model_dir.mkdir(parents=True, exist_ok=True)
manifest_path = root / args.manifest
manifest = json.loads(manifest_path.read_text())
repo = manifest["repository"]
revision = manifest["revision"]

for name, expected in manifest["files"].items():
    if Path(name).name != name:
        raise ValueError("Invalid model filename in manifest")
    target = model_dir / name
    candidate = target
    if not target.exists():
        url = f"https://huggingface.co/{repo}/resolve/{revision}/{name}"
        candidate = target.with_suffix(target.suffix + ".part")
        print("Downloading", name, flush=True)
        subprocess.run([
            "curl", "--fail", "--location", "--retry", "3", "--retry-all-errors",
            "--continue-at", "-", "--speed-time", "30", "--speed-limit", "1024",
            "--connect-timeout", "20", "--max-time", "600", "--silent", "--show-error",
            "--output", str(candidate), url
        ], check=True)
    digest = hashlib.sha256()
    with candidate.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    if candidate.stat().st_size != expected["size"] or digest.hexdigest() != expected["sha256"]:
        raise RuntimeError(f"Model checksum mismatch: {candidate}. Move it aside before retrying.")
    if candidate != target:
        candidate.replace(target)
    print("Verified", name, target.stat().st_size, "bytes", flush=True)

shutil.copyfile(manifest_path, root / "runtime" / (model_dir.name + "-manifest.json"))
print("Model ready:", repo, revision, flush=True)
