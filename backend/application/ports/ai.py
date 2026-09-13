"""AI extraction port (Gate 02B).

Future implementation target: ``backend.infrastructure.ai`` (Gemini intake
analysis, currently ``app/core/ai.py`` / ``app/core/intake_ai.py``).
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class IAiExtractionEngine(Protocol):
    def refine(self, text: str) -> str: ...
    def analyze_intake(self, text: str) -> dict: ...