"""AuditStore — durable JSON persistence for AuditRecord V1.

Stores AuditRecord objects as individual JSON files.
No database. No message queue. No distributed storage.
JSON files are sufficient for V1.

Each AuditRecord is stored as:
    {storage_dir}/{interaction_id}.json

The store is NOT thread-safe for concurrent writes to the same file.
V1 assumes single-process operation.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from controlplane.schemas.audit_record import AuditRecord

logger = logging.getLogger(__name__)


class AuditStoreError(Exception):
    """Base exception for AuditStore failures."""


class AuditStore:
    """Durable JSON persistence for AuditRecord objects.

    V1 implementation stores each AuditRecord as a separate JSON file.
    Files are named by interaction_id for direct lookup.

    Persistence guarantees:
        - save() writes atomically (write-to-temp, then rename)
        - get() reads from disk on every call (no in-memory cache)
        - list() scans the storage directory
        - Corrupt/missing files are handled explicitly
    """

    def __init__(self, storage_dir: str | Path) -> None:
        """Initialize the AuditStore.

        Args:
            storage_dir: Directory path for audit JSON files.
                         Created if it does not exist.
        """
        self._storage_dir = Path(storage_dir)
        self._storage_dir.mkdir(parents=True, exist_ok=True)

    @property
    def storage_dir(self) -> Path:
        return self._storage_dir

    def save(self, audit_record: AuditRecord) -> None:
        """Persist an AuditRecord to disk.

        Writes atomically using write-to-temp-then-rename pattern.
        If persistence fails, raises AuditStoreError — never pretends success.

        Args:
            audit_record: The AuditRecord to persist.

        Raises:
            AuditStoreError: If the write fails for any reason.
        """
        file_path = self._file_path(audit_record.interaction_id)
        temp_path = file_path.with_suffix(".tmp")

        try:
            data = audit_record.model_dump(mode="json")
            json_str = json.dumps(data, indent=2, default=str)

            temp_path.write_text(json_str, encoding="utf-8")
            temp_path.replace(file_path)

            logger.debug(
                "AuditRecord persisted: interaction_id=%s, path=%s",
                audit_record.interaction_id,
                file_path,
            )
        except Exception as exc:
            # Clean up temp file if it exists
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass

            raise AuditStoreError(
                f"Failed to persist AuditRecord for interaction {audit_record.interaction_id}: {exc}"
            ) from exc

    def get(self, interaction_id: UUID) -> AuditRecord | None:
        """Retrieve an AuditRecord by interaction_id.

        Returns None if the record does not exist or is corrupt.
        Logs a warning for corrupt files.

        Args:
            interaction_id: The interaction UUID to look up.

        Returns:
            The AuditRecord if found and valid, None otherwise.
        """
        file_path = self._file_path(interaction_id)

        if not file_path.exists():
            return None

        try:
            json_str = file_path.read_text(encoding="utf-8")
            data = json.loads(json_str)
            return AuditRecord.model_validate(data)
        except Exception as exc:
            logger.warning(
                "Corrupt audit file for interaction %s: %s",
                interaction_id,
                exc,
            )
            return None

    def list(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List stored audit records (metadata only, not full records).

        Returns a lightweight list of interaction summaries sorted by
        created_at descending.

        Args:
            limit: Maximum number of records to return.
            offset: Number of records to skip.

        Returns:
            List of dicts with interaction_id, created_at, final_decision_id.
        """
        results: list[dict[str, Any]] = []

        for file_path in sorted(self._storage_dir.glob("*.json")):
            try:
                json_str = file_path.read_text(encoding="utf-8")
                data = json.loads(json_str)
                results.append(
                    {
                        "interaction_id": data.get("interaction_id"),
                        "created_at": data.get("created_at"),
                        "final_decision_id": data.get("final_decision_id"),
                        "policy_id": data.get("policy_id"),
                        "frozen_v1_version": data.get("frozen_v1_version"),
                    }
                )
            except Exception as exc:
                logger.warning("Skipping corrupt audit file %s: %s", file_path, exc)
                continue

        # Sort by created_at descending
        results.sort(key=lambda r: r.get("created_at") or "", reverse=True)

        return results[offset : offset + limit]

    def reset(self) -> None:
        """Reset the store: remove all audit files and start fresh.

        Deletes all .json files in the storage directory, then recreates it.
        Used at the start of each UI session to guarantee a clean state.
        """
        import shutil
        import tempfile

        # Remove all JSON files in the current directory
        for f in self._storage_dir.glob("*.json"):
            try:
                f.unlink()
            except OSError:
                pass
        # Also remove any leftover .tmp files
        for f in self._storage_dir.glob("*.tmp"):
            try:
                f.unlink()
            except OSError:
                pass
        logger.info("AuditStore reset: cleared all records in %s", self._storage_dir)

    def _file_path(self, interaction_id: UUID) -> Path:
        """Get the file path for a given interaction_id."""
        return self._storage_dir / f"{interaction_id}.json"
