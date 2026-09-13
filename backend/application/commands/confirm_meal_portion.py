"""ConfirmMealPortion command placeholder (Gate 02B)."""

from dataclasses import dataclass, field
from uuid import UUID, uuid4


@dataclass(frozen=True)
class ConfirmMealPortion:
    command_id: UUID = field(default_factory=uuid4)
    meal_draft_id: UUID | None = None
    portion_confirmed: bool = False