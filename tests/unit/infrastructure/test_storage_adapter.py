"""Tests for S3 Object Storage Adapter (Gate 05).

Verifies:
1. Conformance to IObjectStorage port.
2. Put and get binary payloads.
3. Key sanitization and rejection of directory traversal attacks.
4. Correct KeyError handling for non-existent keys.
5. In-memory test fallback without requiring live AWS credentials.
"""

import pytest

from backend.application.ports.storage import IObjectStorage
from backend.infrastructure.storage.s3_storage import S3ObjectStorage


def test_storage_adapter_implements_port_protocol():
    storage = S3ObjectStorage()
    assert isinstance(storage, IObjectStorage)


def test_put_and_get_payload():
    storage = S3ObjectStorage(bucket="clinical-reports")
    key = "patients/123/report_20260913.pdf"
    content = b"%PDF-1.4 Mock PDF Content"

    storage.put(key, content)
    assert storage.exists(key)

    retrieved = storage.get(key)
    assert retrieved == content


def test_key_sanitization_and_rejection_of_traversal():
    storage = S3ObjectStorage()

    # Leading slashes stripped safely
    storage.put("/reports/test.pdf", b"test")
    assert storage.get("reports/test.pdf") == b"test"

    # Directory traversal blocked
    with pytest.raises(ValueError, match="Illegal object key"):
        storage.put("../secret.txt", b"hack")

    with pytest.raises(ValueError, match="Illegal object key"):
        storage.get("reports/../../etc/passwd")

    # Empty key rejected
    with pytest.raises(ValueError, match="non-empty string"):
        storage.put("", b"empty")


def test_type_safety_on_payload():
    storage = S3ObjectStorage()
    with pytest.raises(TypeError, match="must be bytes"):
        storage.put("file.txt", "string payload")  # type: ignore


def test_missing_object_raises_key_error():
    storage = S3ObjectStorage()
    with pytest.raises(KeyError):
        storage.get("non_existent_key.pdf")
