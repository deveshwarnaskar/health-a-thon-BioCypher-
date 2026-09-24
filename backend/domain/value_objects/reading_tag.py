"""ReadingTag value object placeholder (Gate 02B).

Context tag for glucose readings, aligning with the prototype's PB/PL/PD and
fasting conventions.
"""

from enum import Enum


class ReadingTag(str, Enum):
    FASTING = "fasting"
    PRE_MEAL = "premeal"
    POST_BREAKFAST = "postbreakfast"
    POST_LUNCH = "postlunch"
    POST_DINNER = "postdinner"
    POST_PRANDIAL = "postprandial"
    POST_MEAL = "postprandial"