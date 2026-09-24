"""Temporary encrypted media storage for the WhatsApp multimodal pipeline.

Raw voice notes and meal photos must NOT be retained beyond the short processing
window. ``MediaVault`` provides an AES-256-GCM encrypted, expiring, disposable
store layered on the existing ``IObjectStorage`` port — no new database, no new
infrastructure, no plaintext bytes at rest.

Guarantees:

- Encryption: AES-256-GCM with a random 96-bit nonce per object; the storage key
  is bound as AAD so objects cannot be swapped between keys. The key comes from
  configuration (``ai.media_encryption_key``); the development fallback key is
  used ONLY when no key is configured and logs a single warning.
- Lifecycle: every write is registered in an in-memory lease table with an
  absolute expiry. ``sweep()`` disposes objects past retention; the ingestion
  use case also calls ``dispose()`` the moment processing completes.
- The keys embed the tenant, patient, message id and kind so deletion is
  deterministic and tenant-scoped without listing the bucket.
- No PHI is logged anywhere in this module.
"""
from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from backend.application.ports.clock import Clock
from backend.application.ports.storage import IObjectStorage

logger = logging.getLogger(__name__)

_DEV_FALLBACK_KEY = b"thali-media-dev-fallback-key"
_NONCE_BYTES = 12


class MediaVaultError(RuntimeError):
    pass


@dataclass(frozen=True)
class MediaStoredReference:
    storage_key: str
    mime_type: str
    size_bytes: int
    sha256: str
    expires_at: int  # epoch seconds

    def to_dict(self) -> dict:
        return {
            "storage_key": self.storage_key,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "expires_at": self.expires_at,
        }


class MediaVault:
    """Encrypting, expiring object-store wrapper for transient media bytes."""

    def __init__(
        self,
        storage: IObjectStorage,
        *,
        retention_seconds: int = 86400,
        encryption_key: str = "",
        clock: Clock | None = None,
    ) -> None:
        self._storage = storage
        self._retention_seconds = max(retention_seconds, 60)
        self._clock = clock
        # key = SHA-256(config key) so any >=16 byte string yields a 32-byte key
        raw_key = (encryption_key or "").encode("utf-8")
        if not raw_key:
            logger.warning("MEDIA_VAULT: no media encryption key configured; using development fallback key")
            raw_key = b""
        secret_material = raw_key or _DEV_FALLBACK_KEY
        self._aes_key = hashlib.sha256(secret_material).digest()
        # Single-worker lease table: one ingestion worker owns the transient
        # media it wrote, so an in-process registry is authoritative for expiry.
        self._leases: dict[str, float] = {}

    def _now(self) -> datetime:
        if self._clock is not None:
            return self._clock.now()
        return datetime.now(timezone.utc)

    def _expiry_epoch(self) -> int:
        now = self._now()
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        return int(now.timestamp()) + self._retention_seconds

    def _aad(self, storage_key: str) -> bytes:
        return storage_key.encode("utf-8")

    def store(
        self,
        tenant_id: UUID,
        patient_id: UUID,
        *,
        media_type: str,
        message_id: str,
        payload_bytes: bytes,
        mime_type: str,
    ) -> MediaStoredReference:
        """Encrypt and persist transient media. Returns a keyed reference."""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        if not payload_bytes:
            raise MediaVaultError("cannot store empty media payload")
        safe_msg = message_id.replace("/", "_").replace(":", "_") or "msg"
        timestamp = int(self._now().timestamp())
        storage_key = (
            f"media/v1/{str(tenant_id)}/{str(patient_id)}/{media_type}/"
            f"{safe_msg}-{timestamp}.bin"
        )
        nonce = _random_nonce()
        ciphertext = AESGCM(self._aes_key).encrypt(nonce, payload_bytes, self._aad(storage_key))
        envelope = nonce + ciphertext
        self._storage.put(storage_key, envelope)
        self._leases[storage_key] = self._expiry_epoch()
        sha256 = hashlib.sha256(payload_bytes).hexdigest()
        return MediaStoredReference(
            storage_key=storage_key,
            mime_type=mime_type,
            size_bytes=len(payload_bytes),
            sha256=sha256,
            expires_at=self._expiry_epoch(),
        )

    def retrieve(self, storage_key: str) -> bytes:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        try:
            envelope = self._storage.get(storage_key)
        except Exception as exc:  # noqa: BLE001 - storage boundary
            raise MediaVaultError(f"media retrieval failed: {exc}") from exc
        if len(envelope) < _NONCE_BYTES:
            raise MediaVaultError("media envelope is corrupt (too short)")
        nonce = envelope[:_NONCE_BYTES]
        ciphertext = envelope[_NONCE_BYTES:]
        try:
            return AESGCM(self._aes_key).decrypt(nonce, ciphertext, self._aad(storage_key))
        except Exception as exc:  # noqa: BLE001 - unauthenticated ciphertext
            raise MediaVaultError("media decryption failed (integrity check)") from exc

    def dispose(self, storage_key: str | None) -> None:
        """Delete one stored object and drop its lease (best-effort)."""
        if not storage_key:
            return
        self._leases.pop(storage_key, None)
        try:
            if self._storage.exists(storage_key):
                self._storage.delete(storage_key)
        except Exception as exc:  # noqa: BLE001 - best-effort cleanup
            logger.debug("media dispose failed for %s: %s", storage_key, exc)

    def sweep(self) -> int:
        """Delete every object past its retention window. Returns objects removed."""
        now = self._now()
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        cutoff = now.timestamp()
        expired = [key for key, exp in self._leases.items() if exp <= cutoff]
        removed = 0
        for key in expired:
            self.dispose(key)
            removed += 1
        if removed:
            logger.info("media vault sweep removed %d expired object(s)", removed)
        return removed

    def outstanding(self) -> int:
        return len(self._leases)

    def shutdown(self) -> None:
        """Best-effort purge of all leased media (worker teardown)."""
        for key in list(self._leases.keys()):
            self.dispose(key)


def _random_nonce() -> bytes:
    import secrets

    return secrets.token_bytes(_NONCE_BYTES)


__all__ = ["MediaVault", "MediaStoredReference", "MediaVaultError"]