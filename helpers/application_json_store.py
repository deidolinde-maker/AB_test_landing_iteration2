from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from helpers.file_lock import FileLock


SOURCE_ITERATION = "iteration_2_applications"
SCHEMA_VERSION = 1


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ApplicationJsonStore:
    def __init__(
        self,
        path: str | Path,
        *,
        run_id: str,
        build_number: str,
        lock_timeout_sec: float = 30,
    ) -> None:
        self.path = Path(path)
        self.run_id = run_id
        self.build_number = build_number
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        self.lock_timeout_sec = lock_timeout_sec

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = self._empty_payload()
        with FileLock(self.lock_path, self.lock_timeout_sec):
            self._atomic_write(payload)

    def ensure_current_run(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with FileLock(self.lock_path, self.lock_timeout_sec):
            if not self.path.exists():
                self._atomic_write(self._empty_payload())
                return
            payload = self._read_or_create()
            if (
                payload.get("run_id") != self.run_id
                or payload.get("build_number") != self.build_number
                or payload.get("source_iteration") != SOURCE_ITERATION
            ):
                self._atomic_write(self._empty_payload())

    def append(self, record: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with FileLock(self.lock_path, self.lock_timeout_sec):
            payload = self._read_or_create()
            self._assert_current_run(payload)
            payload.setdefault("applications", []).append(record)
            payload["updated_at"] = utc_now_iso()
            self._atomic_write(payload)

    def read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _empty_payload(self) -> dict[str, Any]:
        now = utc_now_iso()
        return {
            "run_id": self.run_id,
            "build_number": self.build_number,
            "created_at": now,
            "updated_at": now,
            "source_iteration": SOURCE_ITERATION,
            "schema_version": SCHEMA_VERSION,
            "applications": [],
        }

    def _read_or_create(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty_payload()
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _assert_current_run(self, payload: dict[str, Any]) -> None:
        if payload.get("run_id") != self.run_id:
            raise AssertionError(
                "Step: Подготовка JSON-файла для третьей итерации\n"
                f"Expected run_id: {self.run_id}\n"
                f"Actual run_id: {payload.get('run_id')}"
            )
        if payload.get("build_number") != self.build_number:
            raise AssertionError(
                "Step: Подготовка JSON-файла для третьей итерации\n"
                f"Expected build_number: {self.build_number}\n"
                f"Actual build_number: {payload.get('build_number')}"
            )

    def _atomic_write(self, payload: dict[str, Any]) -> None:
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            dir=str(self.path.parent),
            text=True,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
                fh.write("\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_name, self.path)
        finally:
            try:
                Path(tmp_name).unlink(missing_ok=True)
            except Exception:
                pass
