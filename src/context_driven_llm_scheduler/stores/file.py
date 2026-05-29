"""File-based context store: one JSON file per pulse id."""

import json
import os
import re
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import portalocker

from context_driven_llm_scheduler.core.exceptions import StoreError
from context_driven_llm_scheduler.core.store import ContextStore
from context_driven_llm_scheduler.core.types import Context

_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]")


class FileStore(ContextStore):
    """Persist each pulse context as a JSON file under a root directory.

    Concurrency safety is provided by an exclusive ``portalocker`` lock on a
    per-key lock file, held for the duration of :meth:`transaction`. Writes
    are atomic (temp file + ``os.replace``), so a reader never sees a partial
    file even without the lock.

    Attributes:
        root: Directory that holds the ``<key>.json`` and ``<key>.lock`` files.
    """

    root: Path

    def __init__(self, root: str | os.PathLike[str]) -> None:
        """Initialize the store, creating ``root`` if needed.

        Args:
            root: Directory in which context files are stored.
        """
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _safe_key(self, key: str) -> str:
        """Return a filesystem-safe stem for ``key``.

        Args:
            key: The raw pulse id.

        Returns:
            A sanitized stem with unsafe characters replaced by ``_``.

        Raises:
            StoreError: If ``key`` is empty.
        """
        if not key:
            raise StoreError("Pulse key must be a non-empty string")
        return _UNSAFE_CHARS.sub("_", key)

    def _data_path(self, key: str) -> Path:
        return self.root / f"{self._safe_key(key)}.json"

    def _lock_path(self, key: str) -> Path:
        return self.root / f"{self._safe_key(key)}.lock"

    def load(self, key: str) -> Context:
        """Load the context for ``key`` (empty dict if absent)."""
        path = self._data_path(key)
        if not path.exists():
            return {}
        try:
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise StoreError(
                f"Failed to load context for '{key}': {exc}"
            ) from exc

    def save(self, key: str, context: Context) -> None:
        """Atomically persist ``context`` for ``key``."""
        path = self._data_path(key)
        try:
            fd, tmp_name = tempfile.mkstemp(
                dir=self.root, prefix=path.stem, suffix=".tmp"
            )
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(context, handle, ensure_ascii=False, indent=2)
            os.replace(tmp_name, path)
        except (OSError, TypeError, ValueError) as exc:
            raise StoreError(
                f"Failed to save context for '{key}': {exc}"
            ) from exc

    def delete(self, key: str) -> None:
        """Remove the context file for ``key`` if it exists."""
        self._data_path(key).unlink(missing_ok=True)

    @contextmanager
    def transaction(self, key: str) -> Iterator[None]:
        """Hold an exclusive file lock on ``key`` for the block."""
        lock = portalocker.Lock(
            str(self._lock_path(key)),
            mode="w",
            flags=portalocker.LOCK_EX,
        )
        with lock:
            yield
