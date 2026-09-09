"""omadocs: one invocation, one new Drive copy; never synchronization."""
VERSION = "0.1.0"
PLUGIN_ID = "io.github.pablousx.omadocs"


def build_id():
    """Code fingerprint for safe helper replacement after a plugin update."""
    import hashlib
    from pathlib import Path
    digest = hashlib.sha256()
    for path in sorted(Path(__file__).parent.glob("*.py")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()[:32]
