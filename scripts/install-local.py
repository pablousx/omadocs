#!/usr/bin/python
"""Install a complete development copy without restarting Quickshell."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--no-enable", action="store_true", help="Install a disabled copy for an isolated UI fixture")
args = parser.parse_args()

root = Path(__file__).resolve().parent.parent
manifest = json.loads((root / "manifest.json").read_text())
plugin_id = manifest["id"]
target = Path.home() / ".config/omarchy/plugins" / plugin_id
marker = ".omadocs-development-source"
env = dict(os.environ, OMARCHY_SHELL_IPC_TIMEOUT="10s")
if target.exists() and (not (target / marker).is_file() or (target / marker).read_text().strip() != str(root)):
    raise SystemExit("Refusing to replace an existing plugin that is not this development copy.")
subprocess.run(["omarchy", "plugin", "validate", str(root)], check=True)
sources = list(root.glob("*.qml")) + list(root.glob("*.js")) + [root / "omadocs-run"]
for name in ("omadocs", "assets"):
    sources.extend(p for p in (root / name).rglob("*") if p.is_file() and "__pycache__" not in p.parts)
digest = hashlib.sha256()
for path in sorted(sources):
    digest.update(str(path.relative_to(root)).encode())
    digest.update(path.read_bytes())
revision = digest.hexdigest()[:16]
target.parent.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix=".omadocs-install-", dir=target.parent.parent) as temp:
    staged = Path(temp) / plugin_id
    runtime = staged / "runtime" / revision
    runtime.mkdir(parents=True)
    for source in sources:
        dest = runtime / source.relative_to(root)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
    # Quattro 4.0.3 can retain failed components after rescan. A versioned path
    # gives Qt a fresh component URL while using the exact repository sources.
    manifest["entryPoints"] = {kind: "runtime/" + revision + "/" + path for kind, path in manifest["entryPoints"].items()}
    (staged / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (staged / marker).write_text(str(root) + "\n")
    subprocess.run(["omarchy", "plugin", "validate", str(staged)], check=True)
    if target.exists():
        subprocess.run(["omarchy", "plugin", "disable", plugin_id], check=True, env=env)
        os.replace(target, Path(temp) / "previous")
    os.replace(staged, target)
subprocess.run(["omarchy-shell", "shell", "rescanPlugins"], check=True, env=env)
for attempt in range(40):
    result = subprocess.run(["omarchy", "plugin", "list", "--json"], capture_output=True, text=True, check=True, env=env)
    if any(item.get("id") == plugin_id for item in json.loads(result.stdout)):
        break
    time.sleep(0.1)
else:
    raise SystemExit("Plugin discovery timed out.")
if not args.no_enable:
    subprocess.run(["omarchy", "plugin", "enable", plugin_id], check=True, env=env)
print("Installed local development copy:", target)
