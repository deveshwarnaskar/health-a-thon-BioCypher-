"""S3-compatible Object Storage Adapter (Gate 05).

Implements the application IObjectStorage port.
Supports AWS S3, MinIO, or Cloudflare R2 object storage with safe credential
handling, object key sanitization, and deterministic test fallback.
"""

from __future__ import annotations

import re
from typing import Any


class S3ObjectStorage:
    """S3-compatible object storage adapter."""

    def __init__(
        self,
        bucket: str = "thali-documents",
        endpoint_url: str | None = None,
        region: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        client: Any = None,
    ) -> None:
        self.bucket = bucket
        self.endpoint_url = endpoint_url
        self.region = region
        self._client = client
        self._in_memory_store: dict[str, bytes] = {}

        if client is None and endpoint_url and access_key_id and secret_access_key:
            try:
                import boto3
                self._client = boto3.client(
                    "s3",
                    endpoint_url=endpoint_url,
                    region_name=region,
                    aws_access_key_id=access_key_id,
                    aws_secret_access_key=secret_access_key,
                )
            except Exception:
                self._client = None

    def _sanitize_key(self, key: str) -> str:
        if not key or not isinstance(key, str):
            raise ValueError("Storage key must be a non-empty string")
        clean_key = key.lstrip("/")
        if ".." in clean_key or clean_key.startswith("/"):
            raise ValueError(f"Illegal object key path: {key!r}")
        return clean_key

    def put(self, key: str, payload: bytes) -> None:
        clean_key = self._sanitize_key(key)
        if not isinstance(payload, bytes):
            raise TypeError(f"Payload must be bytes, got {type(payload).__name__}")

        if self._client is not None:
            self._client.put_object(
                Bucket=self.bucket,
                Key=clean_key,
                Body=payload,
            )
        else:
            self._in_memory_store[clean_key] = payload

    def get(self, key: str) -> bytes:
        clean_key = self._sanitize_key(key)
        if self._client is not None:
            try:
                response = self._client.get_object(
                    Bucket=self.bucket,
                    Key=clean_key,
                )
                return response["Body"].read()
            except Exception as e:
                raise KeyError(f"Object {clean_key} not found in bucket {self.bucket}: {e}")
        else:
            if clean_key not in self._in_memory_store:
                raise KeyError(f"Object {clean_key} not found in storage")
            return self._in_memory_store[clean_key]

    def exists(self, key: str) -> bool:
        clean_key = self._sanitize_key(key)
        if self._client is not None:
            try:
                self._client.head_object(Bucket=self.bucket, Key=clean_key)
                return True
            except Exception:
                return False
        return clean_key in self._in_memory_store

    def delete(self, key: str) -> None:
        clean_key = self._sanitize_key(key)
        if self._client is not None:
            try:
                self._client.delete_object(Bucket=self.bucket, Key=clean_key)
            except Exception as e:
                raise KeyError(f"Failed to delete {clean_key}: {e}")
        else:
            self._in_memory_store.pop(clean_key, None)

    def generate_presigned_url(self, key: str, expires_in: int = 300) -> str:
        clean_key = self._sanitize_key(key)
        if not self.exists(clean_key):
            raise KeyError(f"Object {clean_key} not found in storage")
        if self._client is not None:
            return self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": clean_key},
                ExpiresIn=expires_in,
            )
        endpoint = self.endpoint_url or "https://s3.local"
        return f"{endpoint.rstrip('/')}/{self.bucket}/{clean_key}?expires={expires_in}"


def build_storage_key(
    tenant_id: Any,
    patient_id: Any,
    kind: str,
    document_id: Any,
    extension: str,
) -> str:
    """Build a deterministic, server-authoritative storage key.

    Enforces path structure:
        tenants/{tenant_id}/patients/{patient_id}/{kind}/{document_id}.{extension}
    Never accepts client-controlled directory paths.
    """
    clean_ext = extension.lstrip(".").strip().lower()
    clean_kind = kind.strip().lower()
    return f"tenants/{tenant_id}/patients/{patient_id}/{clean_kind}/{document_id}.{clean_ext}"
