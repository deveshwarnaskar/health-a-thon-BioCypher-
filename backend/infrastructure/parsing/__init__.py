"""Infrastructure parsing — Hinglish normaliser and Indian food taxonomy."""

from .hinglish_parser import (
    READING_TAG_LABELS,
    ParsedInput,
    ambiguous_reading_values,
    describe_items,
    parse_inbound,
)
from .nutrition_taxonomy import (
    FOODS,
    GI_ORDER,
    KATORI_LABELS,
    KATORI_VOLUMES,
    FoodDict,
    NutritionEstimate,
    classify_text,
    estimate_carbs_g,
    estimate_nutrition,
    gi_bucket_index,
)

__all__ = [
    "ParsedInput",
    "parse_inbound",
    "ambiguous_reading_values",
    "describe_items",
    "READING_TAG_LABELS",
    "FOODS",
    "KATORI_LABELS",
    "KATORI_VOLUMES",
    "GI_ORDER",
    "FoodDict",
    "NutritionEstimate",
    "classify_text",
    "estimate_carbs_g",
    "estimate_nutrition",
    "gi_bucket_index",
]
