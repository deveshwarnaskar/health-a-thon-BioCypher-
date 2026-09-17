"""ListFacilities query contract (Gate 10K-B)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ListFacilities:
    limit: int = 50
