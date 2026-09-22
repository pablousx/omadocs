#!/usr/bin/env python3
"""Build reproducible GitHub release assets from a clean Git commit."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parent.parent


def git(*args, text=True):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=text)


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--ref", default="HEAD", help="Commit to archive (default: HEAD)")
parser.add_argument("--output-dir", default="dist", help="Ignored output directory")
args = parser.parse_args()

status = git("status", "--porcelain=v1", "--untracked-files=all").strip()
if status:
    raise SystemExit("Refusing to build release assets from a dirty working tree.")

commit = git("rev-parse", f"{args.ref}^{{commit}}").strip()
manifest = json.loads(git("show", f"{commit}:manifest.json"))
version = manifest["version"]
if manifest.get("id") != "io.github.pablousx.omadocs":
    raise SystemExit("Unexpected plugin identity in release commit.")

output = (ROOT / args.output_dir).resolve()
if not output.is_relative_to(ROOT):
    raise SystemExit("Output directory must stay inside the repository.")
output.mkdir(parents=True, exist_ok=True)

archive = output / f"omadocs-{version}.zip"
license_copy = output / f"omadocs-{version}-LICENSE.txt"
checksums = output / "SHA256SUMS"

with tempfile.TemporaryDirectory(prefix="omadocs-release-") as temporary:
    temporary_archive = Path(temporary) / archive.name
    subprocess.run(
        [
            "git",
            "archive",
            "--format=zip",
            f"--prefix=omadocs-{version}/",
            f"--output={temporary_archive}",
            commit,
        ],
        cwd=ROOT,
        check=True,
    )
    archive.write_bytes(temporary_archive.read_bytes())

license_copy.write_bytes(git("show", f"{commit}:LICENSE", text=False))

assets = (archive, license_copy)
lines = [f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}" for path in assets]
checksums.write_text("\n".join(lines) + "\n")

print(f"Built release assets for {version} at commit {commit}:")
for path in (*assets, checksums):
    print(path.relative_to(ROOT))
