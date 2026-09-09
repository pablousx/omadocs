"""Private application directories. Never use a plaintext secret fallback."""
import os
from pathlib import Path
import stat
from dataclasses import dataclass
from .errors import Fault


def private_dir(path):
    path = Path(path)
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    st = path.lstat()
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
        raise Fault("local_file")
    return path


def private_file(path, flags=os.O_RDWR | os.O_CREAT):
    fd = os.open(path, flags | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    st = os.fstat(fd)
    if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077 or st.st_nlink != 1:
        os.close(fd)
        raise Fault("local_file")
    return fd


@dataclass(frozen=True)
class Paths:
    state: Path
    cache: Path
    runtime: Path
    config: Path
    data: Path
    bin: Path

    @classmethod
    def user(cls):
        home = Path.home()
        def xdg(key, default):
            value = Path(os.environ.get(key, str(default)))
            if not value.is_absolute():
                raise Fault("invalid_input")
            return value
        return cls(xdg("XDG_STATE_HOME", home / ".local/state") / "omadocs",
                   xdg("XDG_CACHE_HOME", home / ".cache") / "omadocs",
                   xdg("XDG_RUNTIME_DIR", Path("/run/user") / str(os.getuid())) / "omadocs",
                   xdg("XDG_CONFIG_HOME", home / ".config"),
                   xdg("XDG_DATA_HOME", home / ".local/share"), home / ".local/bin")

    def prepare(self):
        for p in (self.state, self.cache, self.runtime):
            private_dir(p)
        private_dir(self.cache / "snapshots")

    @property
    def socket(self):
        return self.runtime / "helper.sock"
