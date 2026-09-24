"""KatoriVolume value object (Gate 03).

Canonical household volumetric classes used by the existing Aahaar portion
vocabulary. No nutritional interpretation is performed here.
"""

from dataclasses import dataclass

from ..exceptions import InvalidKatoriVolume

KATORI_VOLUMES_ML = frozenset({150, 220, 350})

_KATORI_LABELS = {150: "small", 220: "medium", 350: "large"}


@dataclass(frozen=True)
class KatoriVolume:
    volume_ml: int

    def __post_init__(self) -> None:
        if not isinstance(self.volume_ml, int) or isinstance(self.volume_ml, bool):
            raise InvalidKatoriVolume(f"katori volume must be an integer, got {self.volume_ml!r}")
        if self.volume_ml not in KATORI_VOLUMES_ML:
            raise InvalidKatoriVolume(
                f"unsupported katori volume {self.volume_ml} ml; "
                f"canonical classes are {sorted(KATORI_VOLUMES_ML)} ml"
            )

    @property
    def label(self) -> str:
        return _KATORI_LABELS[self.volume_ml]

    def __str__(self) -> str:
        return f"{self.volume_ml} ml"