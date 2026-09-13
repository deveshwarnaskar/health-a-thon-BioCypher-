"""UHID value object placeholder (Gate 02B)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class UHID:
    value: str