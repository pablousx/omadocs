#!/usr/bin/env python3
"""Validate the publishable tree without printing OAuth configuration values."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import tomllib

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from omadocs import VERSION, PLUGIN_ID
from omadocs.accounts import bundled_client
from omadocs.errors import Fault

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--custom-setup', action='store_true', help='Allow a release that explicitly requires custom OAuth setup')
args = parser.parse_args()
manifest = json.loads((root/'manifest.json').read_text())
project = tomllib.loads((root/'pyproject.toml').read_text())['project']
errors = []
if manifest['id'] != PLUGIN_ID or manifest['name'] != 'omadocs' or manifest['barWidget']['displayName'] != 'omadocs':
    errors.append('The permanent ID and display name must match the release configuration.')
if manifest['version'] != VERSION or project['version'] != VERSION:
    errors.append('Release versions disagree.')
for name in ('LICENSE', 'README.md', 'docs/uninstall.md', 'site/index.html', 'site/privacy.html', 'site/terms.html'):
    if not (root/name).is_file():
        errors.append('Missing release file: '+name)
client_path = root/'assets/oauth-client.json'
if not args.custom_setup or client_path.exists():
    try:
        bundled_client(client_path)
    except Fault:
        errors.append('A valid bundled Desktop client is required for built-in sign-in.')
tracked = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=root).split(b'\0')
for raw in tracked:
    if not raw:
        continue
    name = raw.decode()
    path = root/name
    if path.is_symlink():
        errors.append('Symlink in release: '+name)
    if not path.is_file():
        continue
    if any(part in ('__pycache__', 'node_modules', '.venv') for part in path.relative_to(root).parts):
        errors.append('Generated directory in release: '+name)
    if path.suffix in ('.db', '.sqlite3', '.sqlite', '.log') or name.endswith(('.tar.gz', '.pyc')):
        errors.append('Private/generated artifact in release: '+name)
    if path.suffix == '.json' and path != client_path:
        try:
            value = json.loads(path.read_bytes())
        except (ValueError, UnicodeError):
            continue
        if isinstance(value, dict) and set(value) & {'installed','web','access_token','refresh_token','private_key'}:
            errors.append('Credential-shaped JSON in release: '+name)
    # A Desktop application's public client_secret has a single explicit home.
    if path != client_path and re.search(rb'(?:GOCSPX-[A-Za-z0-9_-]{12,}|ya29\.[A-Za-z0-9_-]{15,}|gh[pousr]_[A-Za-z0-9]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)', path.read_bytes()):
        errors.append('Credential-like content needs review: '+name)
if errors:
    raise SystemExit('\n'.join(errors))
print('Release checks passed: plugin identity, matching versions, Desktop client schema, publication files, and artifact/credential checks.')
