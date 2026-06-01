from __future__ import annotations

import os
import time
from pathlib import Path


class FileLock:
    def __init__(self, path: str | Path, timeout_sec: float = 30) -> None:
        self.path = Path(path)
        self.timeout_sec = timeout_sec
        self._fh = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open("a+b")
        deadline = time.monotonic() + self.timeout_sec
        while True:
            try:
                self._lock()
                return self
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"Timed out waiting for file lock: {self.path}")
                time.sleep(0.1)

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            self._unlock()
        finally:
            if self._fh is not None:
                self._fh.close()
                self._fh = None

    def _lock(self) -> None:
        assert self._fh is not None
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
            return

        import fcntl

        fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _unlock(self) -> None:
        if self._fh is None:
            return
        if os.name == "nt":
            import msvcrt

            try:
                self._fh.seek(0)
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
            return

        import fcntl

        fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)

