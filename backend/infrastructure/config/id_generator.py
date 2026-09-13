"""UUID4 identifier generator adapter (Gate 05).

Implements the application IdGenerator port using Python's uuid.uuid4().
"""

from __future__ import annotations

import uuid
from uuid import UUID


class Uuid4IdGenerator:
    """Production ID generator producing random standard UUID4s."""

    def new_uuid(self) -> UUID:
        return uuid.uuid4()
