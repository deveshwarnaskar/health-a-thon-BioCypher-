"""Turn a raw inbound message into a typed, safe ParsedInput.

The prototype speaks one neutral wire-format (dict) that either the WhatsApp
Cloud webhook or the built-in simulator produces:

    {
      "patient_id": int,          # which patient this message belongs to
      "sender_phone": str,        # stable identity — decides patient vs caregiver role
      "kind": "text"|"photo"|"voice"|"reading"|None,   # None = auto-detect
      "ts": "2026-...Z",          # optional, defaults to now
      "text": str|None,           # raw text / STT result / photo caption
      "photo_path": str|None,     # local path when kind == photo
      "reading": float|None,      # glucose value when ready-provided
      "reading_tag": "fasting|pre|postprandial|postbreakfast|postlunch|postdinner"
    }

Parsing never raises: anything unparseable becomes a Refusal object so the
channel gets a polite help message instead of a crash.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

from ..config import Settings
from .clock import iso_now, now_local

_GLUE_RE = re.compile(
    r"(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])")


def normalize_glued_numbers(text: Optional[str]) -> str:
    """Insert a space at every letter<->digit boundary so glued tokens like
    'was100', '3am', '1cup' and '200mgdl' become readable by word-anchored
    number regexes. Pure numbers ('2024') and pure words are untouched, and the
    transform is idempotent."""
    s = str(text or "")
    if not s:
        return s
    return _GLUE_RE.sub(" ", s)


_READING_FULL = re.compile(
    r"^\s*([a-z][a-z ]*?)\??\s*[:=]?\s*(\d{2,3}(?:\.\d)?)\s*(mg/dl)?\s*$", re.I)
_READING_SHORT = re.compile(r"^\s*(\d{2,3}(?:\.\d)?)\s*$")
_TAG_MAP = {"fasting": "fasting", "fast": "fasting", "fbs": "fasting",
            "pre": "pre", "before": "pre", "pre meal": "pre",
            "post": "postprandial", "after": "postprandial", "postprandial": "postprandial",
            "pp": "postprandial", "ppbg": "postprandial", "pp2": "postprandial",
            "post breakfast": "postbreakfast", "postbreakfast": "postbreakfast",
            "after breakfast": "postbreakfast", "pb": "postbreakfast",
            "post lunch": "postlunch", "postlunch": "postlunch",
            "after lunch": "postlunch", "pl": "postlunch",
            "post dinner": "postdinner", "postdinner": "postdinner",
            "after dinner": "postdinner", "pd": "postdinner",
            "prick": "postprandial", "fingerprick": "postprandial", "glucometer": "postprandial",
            "random": "random", "rdn": "random", "rbg": "random",
            "random check": "random", "normal": "random", "general": "random",
            "kabhi bhi": "random"}

READING_TAG_LABELS = {
    "fasting": "fasting", "pre": "pre-meal",
    "postprandial": "postprandial (2 hr)",
    "random": "random",
    "postbreakfast": "post-breakfast",
    "postlunch": "post-lunch",
    "postdinner": "post-dinner",
}

# Patient-facing (Hinglish) names for the same tags in confirmations.
PATIENT_TAG_LABELS = {
    "fasting": "Fasting", "pre": "Khane se pehle (needed nahi)",
    "postprandial": "Khane ke baad",
    "random": "Random",
    "postbreakfast": "Breakfast ke baad",
    "postlunch": "Lunch ke baad",
    "postdinner": "Dinner ke baad",
}

_CONFIRM = {"yes", "y", "ok", "okay", "confirm", "hmm", "ha", "haan", "correct",
            "right", "theek", "theek hai", "thik", "thik h", "acha", "achha",
            "sahi", "sahi hai", "ji", "ji haan", "done", "yep", "sure"}

_PORTION_MAP = {
    "s": "s", "small": "s", "chota": "s", "chhota": "s", "kam": "s",
    "m": "m", "medium": "m", "theek": "m", "normal": "m",
    "l": "l", "large": "l", "bada": "l", "zyada": "l", "jyada": "l",
}

# Patient-stated meal/portion sizes that we store verbatim ("200ml", "do katori").
_SIZE_UNITS = ("ml", "g", "gm", "gr", "kg", "l", "litre", "litres", "liter")
_SIZE_BOWLS = ("bowl", "bowls", "katori", "katora", "plate", "plates",
               "thali", "glass", "cup", "cups", "dona", "pao")
_SIZE_COUNT = ("do", "teen", "char", "paanch", "ek", "two", "three", "four",
               "five", "one")

# Words that cannot be a food noun right after a count — so "3 am",
# "8 30 am", "at 7 in the morning" are never mistaken for a portion count.
_COUNT_FILLERS = {
    "am", "pm", "a", "p", "baje", "o", "in", "at", "on", "the", "a", "an",
    "of", "to", "was", "is", "are", "were", "tha", "thi", "us", "kar", "ka",
    "ki", "ke", "me", "mein", "and", "or", "ya", "but", "so",
}


def portion_text(text: str) -> Optional[str]:
    """Extract the patient-stated size verbatim, e.g. '200ml', '2 bowls',
    'do katori'. Returns None when no explicit size was mentioned."""
    low = str(text or "").lower()
    m = re.search(
r"(\d+(?:\.\d+)?\s*(?:ml|g|l|kg|glass|bowl|katori|katora|plate|cup)"
            r"s?)\b", low)
    if m:
        return m.group(1).strip()
    m = re.search(r"(\d+\s*(?:ml|g|kg)?\s*(?:bowl|katori|plate|thali|glass|cup"
                  r"|dona)s?\b)", low)
    if m:
        return m.group(1).strip()
    m = re.search(r"((?:do|teen|char|paanch|ek|two|three|four|five)\s+"
                  r"(?:bowl|katori|plate|thali|glass|cup|dona)s?\b)", low)
    if m:
        return m.group(1).strip()
    # A bare food count is itself the stated size: "3 strawberries",
    # "two chocolates", "5 roti". Clock minutes never match — the token after
    # the number must be a real word (see _COUNT_FILLERS) and the count must be
    # small (single digit or a word). An EXPLICIT size word elsewhere in the
    # message ("2 roti dal small") wins over the count — the count is returned
    # only when it is the ONLY size the patient stated.
    if re.search(r"\b(?:small|medium|large|chota|chhota|chhoti|chote|medium|"
                 r"bada|badi|bara|big|zyada|jyada|full|half|normal|theek)\b",
                 low):
        return None
    m = re.search(
        r"\b(\d|[2-9]|do|teen|char|paanch|ek|one|two|three|four|five|six|"
        r"seven|eight|nine|ten)\s+([a-z]{2,})\b", low)
    if m and m.group(2).lower() not in _COUNT_FILLERS:
        return m.group(1)
    return None


# ---- time/size noise stripping (so clock minutes & portion counts are never
# ---- misread as glucose readings: "8 30 am" must never yield a 30 reading)
_CLOCK_NOISE_RE = re.compile(
    r"\b\d{1,2}:\d{2}\s*(?:am|pm|a|p|o[ ']?clock)?\b", re.I)
_AMPM_NOISE_RE = re.compile(
    r"\b\d{1,2}\s*(?:am|pm|baje|o[ ']?clock)\b", re.I)
_PART_DAY_RE = re.compile(
    r"\b(?:morning|subah|saver|savre|savere|afternoon|dopahar|dophar|noon|"
    r"evening|shaam|shyam|night|raat|ratri)\b", re.I)
# "8 30 am" / "subah 8 30" — space-separated hour-minute pair.
_SPACE_PAIR_RE = re.compile(r"\b(\d{1,2})\s+(\d{2})\s*(am|pm|baje)?\b", re.I)
_SIZE_NOISE_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:ml|g|gm|gr|kg|litre|litres|liter|glass|bowl|bowls|"
    r"katori|katora|plate|plates|thali|cups?|dona|pao)\b", re.I)
_COUNT_NOISE_RE = re.compile(
    r"\b(?:do|teen|char|paanch|ek|two|three|four|five|one)\s+(?:bowl|bowls|"
    r"katori|katora|plate|plates|thali|glass|cups?|dona)\b", re.I)

# Single-word dish names/aliases: a NUMBER immediately before one of these is a
# portion COUNT ("100 chocolates", "4 chole", "6 samosa"), never a glucose
# reading. Built from the nutrition catalog so we never guess food words.
from .nutrition import _ALIASES as _NUTRITION_ALIASES  # noqa: E402
from .nutrition import FOODS as _NUTRITION_FOODS  # noqa: E402


def _food_tokens() -> set[str]:
    toks: set[str] = set()
    for name, _g, _c, _gi, _p in _NUTRITION_FOODS:
        if " " not in name:
            toks.add(name)
    for alias in _NUTRITION_ALIASES:
        if " " not in alias:
            toks.add(alias)
    return toks


_FOOD_TOKENS = _food_tokens()
# Words that announce a READING: a value directly after these is sugar, even if
# a dish word happens to follow ("sugar 100 ... chocolate" keeps the 100).
_READING_PRECEDERS = {
    "sugar", "glucose", "reading", "level", "fasting", "fast", "fbs", "rbs",
    "pp", "bg", "mgdl", "was", "is", "are", "were", "tha", "thi", "the", "a",
    "subah", "shaam", "raat", "morning", "evening", "night", "after", "baad",
    "pe", "par", "ke", "ka", "ki", "around", "about", "approx",
}


def _is_food_word(tok: str) -> bool:
    t = tok.strip(".,:;'\"()!?").lower()
    if not t:
        return False
    if t in _FOOD_TOKENS:
        return True
    if t.endswith("s") and t[:-1] in _FOOD_TOKENS:
        return True
    if t.endswith("ies") and (t[:-3] + "y") in _FOOD_TOKENS:
        return True
    return False


def _strip_food_counts(low: str) -> str:
    """Drop '<count> <dish>' pairs ('100 chocolates', '4 roti') so a portion
    count is never misread as a glucose value. A count right after a reading
    word ("sugar 100 ... chocolate") is kept — that 100 is the sugar."""
    toks = low.split()
    n = len(toks)
    if n < 2:
        return low
    out: list[str] = []
    for i, t in enumerate(toks):
        prev = toks[i - 1] if i > 0 else ""
        nxt = toks[i + 1] if i + 1 < n else ""
        if (len(t) in (2, 3) and t.isdigit()
                and _is_food_word(nxt)
                and prev.strip(".,:;'\"").lower() not in _READING_PRECEDERS):
            continue
        out.append(t)
    return " ".join(out)


def _strip_space_pairs(low: str) -> str:
    """Drop '8 30 am' / 'shaam 8 30' pairs, but only when they look like a
    time (am/pm/baje or a day-part word in the message) so a phrase like
    'ate 2 roti' is untouched."""
    def _repl(m: re.Match) -> str:
        hh, mm = int(m.group(1)), int(m.group(2))
        period = (m.group(3) or "").lower()
        if hh <= 23 and mm <= 59 and (period or _PART_DAY_RE.search(low)):
            return " "
        return m.group(0)
    return _SPACE_PAIR_RE.sub(_repl, low)


def strip_reading_noise(text: Optional[str]) -> str:
    """Remove clock times, "8 30 am", "100 ml" and "do katori" clutter so only
    real glucose numbers remain when scanning a message for a reading."""
    low = normalize_glued_numbers(text)
    low = _CLOCK_NOISE_RE.sub(" ", low)
    low = _strip_space_pairs(low)
    low = _AMPM_NOISE_RE.sub(" ", low)
    low = _SIZE_NOISE_RE.sub(" ", low)
    low = _COUNT_NOISE_RE.sub(" ", low)
    low = _strip_food_counts(low)
    return re.sub(r"\s+", " ", low).strip()


_SIZE_FILLERS = {
    "the", "a", "an", "was", "were", "is", "are", "tha", "thi", "portion",
    "size", "sahi", "pakka", "ji", "h", "ka", "ki", "ke", "me", "mein", "mai",
    "bhi", "hi", "bas", "ye", "yhi", "wahi", "around", "about", "kya", "my",
    "i", "it", "its", "uska", "iska", "ho", "gaya",
}


def _is_size_answer(text: Optional[str]) -> Optional[str]:
    """True when the whole message is ONLY a portion-size answer ('100ml',
    '2 bowls', 'do katori', 'was 200ml', 'small'). Returns the verbatim size
    text so the pending meal confirm gets finalized instead of a confused
    clarify."""
    low = str(text or "").strip().lower()
    if not low or len(low) > 60:
        return None
    ptext = portion_text(low)
    if ptext:
        rest = re.sub(re.escape(ptext), " ", low, count=1)
        words = [w for w in re.split(r"[^a-z0-9]+", rest) if w]
        if not words or all(w in _SIZE_FILLERS for w in words):
            return ptext
        return None
    low2 = re.sub(r"\s+", " ", low.strip().strip(".,;:!?")).strip()
    if low2 in _PORTION_MAP:
        return low2
    m = re.match(
        r"^(half|full|do|ek|teen|char|paanch|one|two|three|four|five|"
        r"1|2|3|4|5)?\s*(katori|bowl|plate|thali|glass|cup|dona|pao)s?$",
        low2)
    if m:
        return low2
    return None


# ---- meal/reading correction & reference intents ----------------------
_REF_CUES = ("same", "wahi", "wohi", "dono", "yahe", "yhi", "pehle", "earlier")
_CORR_PREV_CUES = ("wrong", "galat", "galti", "mistake", "not", "nhi", "nahi",
                   "tha", "told", "change", "changed", "different", "alag",
                   "sahi", "koi aur")
_REF_STRONG = ("not the one", "the one i told", "i told", "jo bola",
               "pehle bola", "jo maine bola", "bola tha", "boli thi",
               "told was", "told you")

# ---- "change X to Y" / "instead of X" -----------------------------------
# A replacement names TWO dishes: the OLD one to supersede (kept with a red
# cross in the log) and the NEW one actually eaten. We need the old dish's
# exact phrase so the new meal can EXCLUDE it and the supersede can find the
# right row by name — never by time-recency alone.
_STOP_BEFORE_OLD = ("today", "yesterday", "tomorrow", "kal", "aaj", "abhi",
                    "morning", "subah", "evening", "shaam", "night", "raat",
                    "at", "after", "baad", "was", "were", "tha", "thi", "is",
                    "are", "and", "but", "so", "with", "then")


def _is_change_text(text: Optional[str]) -> bool:
    low = str(text or "").lower()
    return ("instead of" in low or "insteadof" in low
            or any(k in low for k in ("i told", "change", "changed",
                                      "replace", "replaced", "badal", "badlo",
                                      "sudhar", "swap")))


# Pronouns/referent words are never dish names: "the one i told" refers to the
# pending meal but carries no old-dish phrase to supersede by name. Any of
# these inside a candidate makes it a referent, not a dish ("one i" is junk).
_NON_DISH_JUNK = {
    "one", "it", "that", "this", "same", "those", "these", "thing", "some",
    "khana", "khaana", "wala", "waala", "wali", "dino", "earlier", "yesterday",
    "today", "morning", "then", "the", "a", "an", "to", "with", "ko", "ka",
    "ki", "ke", "se", "me", "i", "i've", "i'm", "i'", "maine", "main", "you",
    "who", "which", "told", "mentioned", "said", "bata", "bataya", "batayi",
    "batayo", "bola", "bolaya", "bolayi", "was", "were", "is", "are", "ate",
    "khaya", "tha", "thi", "not", "actually", "instead",
}


def _is_plausible_dish_phrase(p: Optional[str]) -> bool:
    """Guard against pronoun/'the one i told' captures when extracting the OLD
    dish — a bare referent is not a dish to supersede by name."""
    if not p:
        return False
    p = re.sub(r"\s+", " ", p.lower()).strip().strip(".,:;'\"")
    if not p:
        return False
    words = p.split()
    if len(words) > 6:
        return False
    if any(w in _NON_DISH_JUNK for w in words):
        return False
    if len(words) == 1 and not _is_food_word(words[0]):
        return False
    return True


def change_old_dish(text: Optional[str]) -> Optional[str]:
    """The OLD dish phrase in a change/replacement message, else None.

    'today i actually ate chole bhature instead of the chocolate i told you'
        -> 'chocolate'
    'change chole bhature to white rice 1 cup'  -> 'chole bhature'
    'i ate kitkat instead of chocolate'          -> 'chocolate'
    """
    low = re.sub(r"\s+", " ", str(text or "").lower()).strip().strip(".,:;'\"")
    if not low:
        return None
    # "instead of (the) X ..." — consume trailing referents like 'i told you'.
    m = re.search(r"\binstead of\s+(?:the\s+|that\s+)?(.+)$", low)
    if m:
        tail = m.group(1)
        tail = re.split(r"\b(?:that\s+)?(?:i |i've |i'm |maine |main )(?:told|"
                        r"mentioned|bata(?:ya|i|o)?|bola(?:ya)?|said)\b",
                        tail, maxsplit=1)[0]
        for stop in re.finditer(r"\s+(?:today|yesterday|kal|aaj|abhi|at|after|"
                                r"and|was|were|tha|thi|morning|subah|shaam|"
                                r"raat|night)\b", tail):
            tail = tail[:stop.start()]
            break
        tail = tail.strip(" .,:;'\"")
        if tail and _is_plausible_dish_phrase(tail):
            return tail
    # "change X to Y" / "replace X with Y" / "badal do X ko Y".
    m = re.search(r"\b(?:change|changed|replace|replaced|swap|badal|badlo|"
                  r"sudhar|update)\s+(.+?)\s+(?:to|ko|me|se|with)\s+\S", low)
    if m:
        old = m.group(1).strip(" .,:;'\"")
        old = re.split(r"\b(?:to|ko|se|me|with)\b", old, maxsplit=1)[0].strip()
        if old and _is_plausible_dish_phrase(old):
            return old
    # "the X i told you (was wrong)" — the OLD dish sits between a leading
    # "the/that" and the tell-referent, which is stripped so "the chocolate i
    # told" yields "chocolate".
    m = re.search(r"\b(?:the|that)\s+", low)
    if m:
        after = low[m.end():]
        after = re.split(r"\b(?:that\s+)?(?:i |i've |i'm |maine |main )?"
                         r"(?:told|mentioned|said|bata(?:ya|i|o)?|"
                         r"bola(?:ya)?)\b",
                         after, maxsplit=1)[0]
        after = re.split(r"\s+(?:today|yesterday|kal|aaj|morning|was|were|"
                         r"tha|thi|is|and|but|so|not)\b", after,
                         maxsplit=1)[0]
        after = after.strip(" .,:;'\"")
        if _is_plausible_dish_phrase(after):
            return after
    return None


def change_remainder(text: Optional[str]) -> str:
    """Text with the change/reference phrase stripped so dish extraction sees
    ONLY the NEW dish. 'chole bhature instead of the chocolate i told you'
    -> 'chole bhature'; 'i ate kitkat instead of chocolate' -> 'i ate kitkat'."""
    low = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    low = re.sub(r"\binstead of\b.*$", " ", low)
    low = re.sub(r"\b(?:change|changed|replace|replaced|swap|badal|badlo|"
                 r"sudhar|update)\s+\S.*?\s+(?:to|ko|se|me|with)\s+", " ", low)
    low = re.sub(r"\b(?:that\s+)?(?:i |i've |i'm |maine |main )?(?:told|"
                 r"mentioned|bata(?:ya|i|o)?|bola(?:ya)?|said)\b.*?"
                 r"(?=\b(?:today|yesterday|kal|aaj|at|after|and|was|were|"
                 r"morning|subah|shaam|raat|night)\b)|$", " ", low)
    return re.sub(r"\s+", " ", low).strip()


def dish_mentions_phrase(item_names: object, phrase: Optional[str]) -> bool:
    """True when a dish-item name matches the OLD phrase we are replacing
    ('chocolate' matches 'chocolate'/'chocolates'; 'bhature' matches the items
    of a 'chole bhature' row)."""
    if not phrase:
        return False
    p = re.sub(r"\s+", " ", phrase.lower()).strip().strip(".,:;'\"")
    if not p:
        return False
    pwords = set(re.split(r"\s+", p))
    for name in (item_names or []):
        n = re.sub(r"\s+", " ", str(name or "").lower()).strip().strip(".")
        nwords = set(re.split(r"\s+", n))
        if n == p:
            return True
        if pwords and nwords and len(pwords & nwords) >= min(1, len(nwords)):
            return True
    return False


def _reference_correction(text: Optional[str]) -> bool:
    """True when the message refers to a MEAL the patient named before and
    corrects/changes it ("not the one i told", "same only, the meal i told was
    wrong") WITHOUT naming a new dish or a number. Such a message must never
    fabricate a dish name (see nutrition._fallback_dish) — the worker replaces
    or confirms the prior meal instead."""
    low = strip_reading_noise(text).lower()
    low = re.sub(r"\s+", " ", low).strip()
    if not low or len(low) > 60:
        return False
    if re.search(r"\d", low):
        return False
    if _is_size_answer(low) or _is_confirm(low):
        return False
    if any(s in low for s in _REF_STRONG):
        return True
    has_ref = any(w in low for w in _REF_CUES)
    has_corr = any(w in low for w in _CORR_PREV_CUES)
    return bool(has_ref and has_corr)


_DELETE_WORDS = ("delete", "remove", "hata", "hatao", "hatana", "hatayo",
                 "mita", "mitao", "mitana", "nikal", "nikalo", "clear",
                 "erase")
_MEAL_DELETE_WORDS = ("khana", "khaana", "meal", "dish", "dishes", "food",
                      "makan")
_READING_DELETE_WORDS = ("sugar", "glucose", "reading", "prick", "value",
                         "log", "entry", "record")


def _is_reading_delete(text: Optional[str]) -> bool:
    """'sugar delete karo' / 'remove the 2pm reading' / 'us reading ko hatao'
    -> True. Meal-deletes are handled separately (see _is_meal_delete)."""
    low = str(text or "").lower()
    if not any(re.search(rf"\b{re.escape(w)}\b", low) for w in _DELETE_WORDS):
        return False
    if any(mw in low for mw in _MEAL_DELETE_WORDS):
        return False
    if any(re.search(rf"\b{re.escape(k)}\b", low) for k in _READING_DELETE_WORDS):
        return True
    return bool(re.search(r"\b\d{2,3}\b", low))


def _is_meal_delete(text: Optional[str]) -> bool:
    """'khana delete karo' / 'delete the meal i logged' -> True."""
    low = str(text or "").lower()
    if not any(re.search(rf"\b{re.escape(w)}\b", low) for w in _DELETE_WORDS):
        return False
    return any(mw in low for mw in _MEAL_DELETE_WORDS)


_DAY_REF_RE = re.compile(r"\b(kal|yesterday|parso[ _]kal|parso|aaj|today|abh[ií])\b")
_EDIT_MARKS = ("wala", "wali", "wale", "galat", "wrong", "sahi", "update",
               "change", "changed", "edit", "replace", "correct", "correction",
               "sudhar", "badlo", "badal", "kar do")


def _dated_edit_value(text: Optional[str],
                      msg_ts: Optional[str] = None) -> Optional[tuple]:
    """'kal 8 am wala galat tha, 140 tha' -> (value, ts_for_that_time).
    Returns (float, iso-ts) when the message names an explicit day/time,
    uses a correction marker AND carries exactly one glucose-sized value —
    the patient is fixing a PAST logged reading, not reporting a new one."""
    low = str(text or "").lower()
    if not _DAY_REF_RE.search(low):
        return None
    if not any(m in low for m in _EDIT_MARKS):
        return None
    nums = [float(m) for m in re.findall(r"\b\d{2,3}(?:\.\d)?\b", low)
            if 20 <= float(m) <= 600]
    if len(nums) != 1:
        return None
    ts = reading_timestamp(text, msg_ts or iso_now()).strftime(
        "%Y-%m-%dT%H:%M:%S")
    return nums[0], ts


@dataclass
class ParsedInput:
    kind: str                      # text | photo | voice | reading | confirm | correct | refusal
    text: Optional[str] = None
    items: list[dict] = field(default_factory=list)
    reading: Optional[float] = None
    reading_tag: Optional[str] = None
    portion_letter: Optional[str] = None
    portion_text: Optional[str] = None
    ts: datetime = field(default_factory=now_local)
    raw: str = ""

    @property
    def is_reading(self) -> bool:
        return self.kind == "reading"

    @property
    def is_meal(self) -> bool:
        return self.kind in ("text", "photo", "voice", "correct")

    @property
    def is_confirm(self) -> bool:
        return self.kind == "confirm"


def _is_confirm(text: str) -> bool:
    low = text.strip().lower()
    if low in _CONFIRM:
        return True
    words = low.split()
    if len(words) <= 4 and all(w in _CONFIRM or w in ("hai", "h", "ji", "to", "bhi", "tha", "sir") for w in words):
        return True
    return False


_DONE_PHRASES = {
    "that's all", "thats all", "thaits all", "that's it", "thats it",
    "all done", "all logged", "ok done", "okay done", "done", "bas",
    "bas karo", "bas itna", "itna hi", "ho gaya", "ho gya", "hogaya",
    "bus", "chalega", "finished", "complete", "completed", "done for today",
    "dono ho gaya", "sab ho gaya", "sab logged", "ok thanks", "thanks ji",
}

# Polite trailing "log kar lena" style cues ("sukoon se log kar lena").
# Only when the line carries NO digits or other data — otherwise "1 aur log
# kar lena" must stay a normal answer.
_DONE_SUFFIXES = (
    "log kar lena", "log kar dena", "log karna", "kar dena",
    "kar lena", "kar do", "bata dena", "bata lena",
)


def _is_done(text: Optional[str]) -> bool:
    """'that's all' / 'bas' / 'ho gaya' — the patient says logging is over for
    now. Pure courtesy: never blocks, never logs anything."""
    low = str(text or "").strip().lower()
    low = re.sub(r"\s+", " ", low).strip(".,!? ")
    if not low or len(low) > 30:
        return False
    if low in _DONE_PHRASES:
        return True
    if re.search(r"\d", low):
        return False
    return any(p in low for p in _DONE_SUFFIXES)


def _tag_from_text(prefix: str) -> str:
    cleaned = prefix.lower().strip()
    if cleaned in _TAG_MAP:
        return _TAG_MAP[cleaned]
    # Meal-slot specific words take precedence over generic type words
    if re.search(r"\b(breakfast|nashta|pb)\b", cleaned):
        return "postbreakfast"
    if re.search(r"\b(lunch|dopahar|pl)\b", cleaned):
        return "postlunch"
    if re.search(r"\b(dinner|raat|pd)\b", cleaned):
        return "postdinner"
    # Fasting only when the patient says so (empty-stomach cues). "morning"/
    # "subah" are timing, NOT fasting. Random is its own explicit type. A bare
    # or uncontextualised reading is a random check, never an assumed 2-hour
    # post-meal value.
    if re.search(r"\b(random|randomly|rdn|rbg|random blood glucose)\b", cleaned):
        return "random"
    if re.search(r"\b(fasting|fast|fbs|khali\s*pet|khali\s*pet\b|roza|rozey|empty\s*stomach)\b", cleaned):
        return "fasting"
    if re.search(r"\b(pre|before|pehle)\b", cleaned):
        return "pre"
    if re.search(r"\b(post|after|baad|pp|ppbg)\b", cleaned):
        return "postprandial"
    # Default is Random Blood Glucose (RBG). postprandial is ONLY logged when
    # the patient actually says after/baad/post-2hr; a bare or uncontextualised
    # reading is a random check, never an assumed 2-hour post-meal value.
    return "random"


def parse_inbound(raw: dict, cfg: Settings, mock_vision=None) -> ParsedInput:
    """Normalize a raw wire message. Never raises."""
    if not isinstance(raw, dict):
        return ParsedInput(kind="refusal", raw=str(raw)[:80])

    kind = raw.get("kind")
    text = raw.get("text")
    if text:
        from .ai import refine_text_local
        text = refine_text_local(text)

    photo = raw.get("photo_path")
    reading = raw.get("reading")

    if kind == "reading" or reading is not None:
        return _as_reading(raw, reading)

    # A raw text that is itself a glucose number/reading → reading.
    if kind in (None, "text") and text:
        r = _reading_from_text(text, raw)
        if r:
            return r

    # Confirm / correct replies to a pending meal estimate.
    if text:
        low = text.strip().lower()
        if _is_confirm(text):
            return ParsedInput(kind="confirm", text=low, ts=_ts(raw), raw=low)
        pm = re.match(r"^(correct|nhi|nahi|no)\s*.?\s*([a-z]+)$", low)
        portion_word = (pm.group(2) if pm else low).strip()
        if portion_word in _PORTION_MAP:
            return ParsedInput(kind="confirm", text=low,
                               portion_letter=_PORTION_MAP[portion_word],
                               portion_text=portion_text(low),
                               ts=_ts(raw), raw=low)
        cm = re.match(r"^correct\s+(.+)$", low)
        if cm:
            return ParsedInput(kind="correct", text=cm.group(1), ts=_ts(raw), raw=low)

    if kind in (None, "text", "voice") and text:
        return ParsedInput(kind="text", text=text, items=_items(text, cfg),
                           portion_text=portion_text(text),
                           ts=_ts(raw), raw=text)

    if kind == "photo" or photo:
        items = _mock_photo(raw, cfg, mock_vision)
        return ParsedInput(kind="photo", text=text, items=items,
                           ts=_ts(raw), raw="photo")

    return ParsedInput(kind="refusal", raw="unrecognized input")


_AMBIGUITY_MARKERS = (
    "or", "ya ", "yaa", "shayad", "shaydd", "maybe", "may be", "mabbe",
    "approx", "approximately", "around", "roughly", "pata", "under", "close to",
    "almost", "nearly",
)


def ambiguous_reading_values(text: str) -> list[float]:
    """Deterministic (no-LLM) detector for an UNRESOLVED glucose reading.

    Returns the sorted candidate values (20-600) when a single message carries
    two or more plausible readings joined by an uncertainty/alternative word
    ("230 or 330", "shayad 230 ya 330..."). Used so the webhook path never also
    fires a meal portion-confirm for the same message — the dashboard AI intake
    asks the one clarifying question instead. Returns [] when unambiguous.
    """
    if not text:
        return []
    low = strip_reading_noise(text)
    if not any(m in low for m in _AMBIGUITY_MARKERS):
        return []
    vals = sorted({float(m) for m in re.findall(r"\b\d{2,3}(?:\.\d)?\b", low)
                   if 20 <= float(m) <= 600})
    return vals if len(vals) >= 2 else []


# ---- follow-up answer detection (deterministic, dashboard-driven) ------
# Short replies that answer the reading-context/tag question the AI asked
# ("khane ke baad", "fasting", "post lunch" ...). Never treated as food/sugar.
_TAG_CUES = ("fasting", "fast", "fbs", "khali", "roza",
             "breakfast", "nashta", "lunch", "dopahar", "dinner", "raat",
             "pre", "before", "pehle", "post", "after", "baad", "pp",
             "random", "khane")
_TAG_DENY = ("roti", "sabzi", "sabji", "paneer", "chana", "dahi", "chawal",
             "rice", "paratha", "dosa", "idli", "khana", "khaana", "mithai",
             "photo", "picture")
# Words that mark a tag as NEGATED: "wo fasting nhi thi" does NOT set fasting.
_TAG_NEGATION = ("nhi", "nahi", "not", "no ", "nop", "never",
                 "nope", "nah", "ni")

_RESOLUTION_CUES = ("hai", "theek", "thik", "sahi", "sachi", "correct",
                    "confirm", "pakka", "wala", "2nd", "second", "1st",
                    "first", "it is", "it's", "yahe", "yhi", "hi hai",
                    "definitely", "exact", "exactly", "choose ", "select ",
                    " wali")

# Words that signal a CHANGE/correction ("change 120 to 130", "update karo").
_CORRECTION_WORDS = ("change", "changed", "update", "correct", "correction",
                     "sudhar", "badlo", "badal", "kar do", "karne", "edit",
                     "replace", "sudhara")


def _has_negation(low: str) -> bool:
    """Word-boundary negation check for short tag answers."""
    return any(re.search(rf"\b{re.escape(w)}\b", low) for w in _TAG_NEGATION)


def _is_tag_negation(text: Optional[str]) -> Optional[str]:
    """'wo fasting nhi thi' / 'not fasting' -> the DENIED tag (never applied).

    The patient is telling us the reading is NOT that context, so the denied
    tag must never be written to the log. We return it so the worker can keep
    the correct existing tag (or ask again) instead of mis-tagging.
    """
    low = _strip_time(text)
    if not low or len(low) > 26:
        return None
    if re.search(r"\d", low):
        return None
    if any(w in low for w in _TAG_DENY):
        return None
    if not any(c in low for c in _TAG_CUES):
        return None
    if not _has_negation(low):
        return None
    return _tag_from_text(low)


def _strip_time(text: Optional[str]) -> str:
    """'khane ke pehle 07:06 am' -> 'khane ke pehle'. Removes the clutter
    patients append after answering the before/after question."""
    low = str(text or "").strip().lower()
    low = re.sub(r"\b\d{1,2}:\d{2}\s*(?:am|pm|a|p|o[ ']?clock)?\b", " ", low)
    low = _strip_space_pairs(low)
    low = re.sub(r"\b\d{1,2}\s*(?:am|pm|baje|o[ ']?clock)\b", " ", low)
    low = re.sub(r"\b(07|7|08|8|09|9|1[0-9]|2[0-3]):\d{2}\b", " ", low)
    return re.sub(r"\s+", " ", low).strip()


def _is_tag_answer(text: Optional[str]) -> Optional[str]:
    """'khane ke baad' / 'fasting' / 'post lunch' -> the reading-context tag.

    Returns the tag when the message is a short answer to the tag question the
    AI asked, otherwise None. Purely deterministic. A NEGATION ('fasting nhi
    thi') is a different intent — never read as a tag.
    """
    low = _strip_time(text)
    if not low or len(low) > 22:
        return None
    if re.search(r"\d", low):
        return None
    if any(w in low for w in _TAG_DENY):
        return None
    if not any(c in low for c in _TAG_CUES):
        return None
    if _has_negation(low):
        return None
    # A message that names any FOOD ("lunch me chole bhature") is a meal,
    # never a tag answer — the deny-list alone can't cover the whole catalog.
    if any(_is_food_word(t) for t in low.split()):
        return None
    return _tag_from_text(low)


def _is_correction(text: Optional[str]) -> bool:
    low = str(text or "").lower()
    return any(re.search(rf"\b{re.escape(w)}\b", low) for w in _CORRECTION_WORDS)


def _correction_value(text: Optional[str]) -> Optional[float]:
    """The corrected VALUE the patient wants ("130 not 120", "change 120 to
    130", "wo 130 tha 120 nahi"). Returns None when it cannot be decided.

    - change words: value after the converter word (to/par/pe -> 130).
    - two numbers + a negation: the number that ISN'T negated is the truth.
    """
    low = str(text or "").lower()
    nums = [(float(m.group()), m.start())
            for m in re.finditer(r"\b\d{2,3}(?:\.\d)?\b", low)
            if 20 <= float(m.group()) <= 600]
    vals = [v for v, _ in nums]
    if not vals:
        return None

    converter = re.search(r"\b(to|par|pe|mein|me)\b", low)
    if _is_correction(low):
        if converter:
            tail = low[converter.end():]
            m = re.search(r"\b(\d{2,3}(?:\.\d)?)\b", tail)
            if m and 20 <= float(m.group(1)) <= 600:
                return float(m.group(1))
        # 'change 120 to 130' without a converter -> assume the LAST value
        return vals[-1]

    # Two sugar-lookalike numbers + a negation ("130 not 120", "wo 130 tha
    # 120 nahi", "not 120, 130 hai"): pick the number that is NOT the denied
    # one. The denied number sits right next to the negation word.
    if len(vals) == 2 and _has_negation(low):
        neg_pos = min((m.start() for m in re.finditer(
            r"\b(nhi|nahi|not)\b", low)), default=None)
        if neg_pos is not None:
            after = [v for v, pos in nums if neg_pos < pos < neg_pos + 8]
            before = [v for v, pos in nums if neg_pos - 9 < pos < neg_pos]
            denied = None
            if len(after) == 1:
                denied = after[0]
            elif len(before) == 1:
                denied = before[0]
            if denied is not None:
                return vals[1] if vals[0] == denied else vals[0]
    return None


def _resolution_cue_value(text: Optional[str]) -> Optional[float]:
    """A single glucose value offered as THE answer ("230 hai", "it's 230",
    "first wala 230"). Returns the value or None."""
    low = str(text or "").lower()
    nums = [float(m) for m in re.findall(r"\b\d{2,3}(?:\.\d)?\b", low)
            if 20 <= float(m) <= 600]
    if len(nums) != 1:
        return None
    if any(c in low for c in _RESOLUTION_CUES):
        return nums[0]
    return None


def _single_number_value(text: Optional[str]) -> Optional[float]:
    low = str(text or "")
    nums = [float(m) for m in re.findall(r"\b\d{2,3}(?:\.\d)?\b", low)
            if 20 <= float(m) <= 600]
    return nums[0] if len(nums) == 1 else None


def _is_dup_answer(text: Optional[str]) -> Optional[str]:
    """Answer to the 'already logged — naya ya mistake?' question."""
    low = str(text or "").lower().strip()
    if not low:
        return None
    if re.search(r"\b(naya|nayi|new)\b", low):
        return "new"
    if re.search(r"\b(no?[h]?i add|dont add|do not add)\b", low):
        return "skip"
    if low in ("nahi", "nai", "no", "nhi", "mistake", "galat", "galti",
               "skip", "pehle se hai", "already hai", "already logged"):
        return "skip"
    if re.search(r"\b(mistake|galat|galti|pehle se|already)\b", low) and len(low.split()) <= 3:
        return "skip"
    return None


# ---- explicit date/time references ("yesterday evening near 3pm") -------
_TIME_SHIFTS = (
    (r"\b(parso[ _]kal|day before yesterday|two days ago|2 din pehle|do din pehle)\b", -2),
    (r"\b(parso[ _]parso|three days ago|3 din pehle|teen din pehle)\b", -3),
    (r"\b(pichhle[ _]din|past[ _]few[ _]days)\b", -3),
    (r"\b(kal|yesterday|last[ _]night|last[ _]evening)\b", -1),
    (r"\b(aaj|today|abh?i)\b", 0),
)
_PART_DEFAULTS = (
    (("subah", "savre", "morning", "pratha", "praata"), 8),
    (("dophar", "noon", "afternoon", "doupahar"), 13),
    (("shaam", "evening", "sanja", "sayankar"), 18),
    (("raat", "night", "rathri", "midnight"), 21),
)

_MONTHS = {
    "jan": 1, "january": 1, "janvari": 1,
    "feb": 2, "february": 2, "farvari": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5, "mai": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7, "julai": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}
_MONTH_RE = ("jan(?:uary|vari)?|feb(?:ruary|vari)?|mar(?:ch)?|apr(?:il)?"
             "|may|mai|jun(?:e)?|jul(?:y|ai)?|aug(?:ust)?|sep(?:t|tember)?"
             "|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?")


def _explicit_date(text: Optional[str], base: date) -> Optional[date]:
    """True calendar date the patient said ('14 july', 'july 14',
    '14th of july', '14/07', '14-07' [+ year]). Returns None when absent.

    No year -> assume the message year, pulled back one year when the result
    would be in the future (patients back-log past dates).
    """
    low = str(text or "").lower()
    found: Optional[tuple[int, int, int]] = None
    # '14 july' / '14th of july' / '14 july 2026'
    m = re.search(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+of\s+({_MONTH_RE})\b", low)
    if not m:
        m = re.search(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MONTH_RE})\b", low)
    if m:
        found = (int(m.group(1)), _MONTHS[re.sub(r"\W", "", m.group(2))], None)
    else:
        # 'july 14' / 'july 14th' / 'july 14 2026'
        m = re.search(rf"\b({_MONTH_RE})\s+(\d{{1,2}})(?:st|nd|rd|th)?\b", low)
        if m:
            found = (int(m.group(2)), _MONTHS[re.sub(r"\W", "", m.group(1))], None)
    if not found:
        # numeric '14/07' or '14-07' (day/month), not a clock '07:05'
        m = re.search(r"\b(\d{1,2})[/-](\d{1,2})\b", low)
        if m:
            found = (int(m.group(1)), int(m.group(2)), None)
    if not found:
        return None
    day, mon, _y = found
    yr = base.year
    ym = re.search(r"\b(20\d{2}|19\d{2})\b", low)
    if ym:
        yr = int(ym.group(1))
    try:
        d = date(yr, mon, day)
    except ValueError:
        return None
    if d > base:
        d = date(yr - 1, mon, day)  # past back-logging beats a future date
    return d


def time_reference(text: Optional[str]) -> tuple[int, Optional[int]]:
    """(day_shift, minute_of_day|None) from explicit words in the message."""
    low = str(text or "").lower()
    shift = 0
    for pat, s in _TIME_SHIFTS:
        if re.search(pat, low):
            shift = s
            break
    minute: Optional[int] = None
    hh: Optional[int] = None
    explicit_ampm = False
    # "8 30 am" / "subah 8 30" — space-separated hour-minute. Accepted only
    # with am/pm/baje or a day-part word so 'ate 30' is never a clock.
    m_sp = _SPACE_PAIR_RE.search(low)
    if m_sp:
        hh_sp, mm_sp = int(m_sp.group(1)), int(m_sp.group(2))
        period_sp = (m_sp.group(3) or "").lower()
        if hh_sp <= 23 and mm_sp <= 59 and (period_sp or _PART_DAY_RE.search(low)):
            hh = hh_sp
            explicit_ampm = period_sp in ("am", "pm")
            if period_sp == "pm" and hh < 12:
                hh += 12
            elif period_sp == "am" and hh == 12:
                hh = 0
            minute = hh * 60 + mm_sp
    if minute is None:
        m = re.search(r"(\d{1,2})(?::(\d{2}))?(?:\s*(am|pm|baje)\b)", low)
        if not m:
            m = re.search(r"(\d{1,2}):(\d{2})\b", low)
        if m:
            hh = int(m.group(1))
            mm = int(m.group(2) or 0)
            period = (str(m.group(3) or "") if m.lastindex >= 3 else "").strip()
            if period in ("am", "pm"):
                explicit_ampm = True
            if period == "pm" and hh < 12:
                hh += 12
            elif period == "am" and hh == 12:
                hh = 0
            minute = hh * 60 + mm
        else:
            # Bare hour tied to a part-of-day word ("at 7 in the morning",
            # "7 subah", "8 raat", "shaam 3") — the explicit hour wins, so
            # "yesterday at 7 in the morning" is 07:00 and NOT the generic
            # morning default of 08:00. "sugar 130 morning" can never match
            # because \d{1,2} cannot swallow the third digit.
            _PART_DAY = (r"(?:morning|subah|saver|savre|savere|afternoon|"
                         r"dopahar|evening|shaam|shyam|night|raat|ratri)")
            m2 = re.search(
                rf"\b(?:at|about|around|karib|lagbhag)?\s*(\d{{1,2}})(?!\d)"
                rf"(?:\s*baje\b)?\s*(?=(?:in\s+the\s+)?{_PART_DAY}\b)", low)
            if not m2:
                m2 = re.search(
                    rf"\b{_PART_DAY}\b\s*(?:ke\s+)?(\d{{1,2}})(?!\d)"
                    rf"(?:\s*baje\b)?", low)
            if m2:
                hh = int(m2.group(1))
                minute = hh * 60
    if minute is not None and not explicit_ampm and hh is not None and hh < 12:
        # Evening/night hours without am/pm: "shaam 3" -> 15:00, "raat 8" ->
        # 20:00, "shaam 3 baje" -> 15:00. True 24h-style hours stay untouched.
        if re.search(
                r"\b(?:afternoon|dopahar|evening|shaam|shyam|night|raat|ratri)\b",
                low):
            minute += 12 * 60
    if minute is None:
        for words, default_h in _PART_DEFAULTS:
            if any(w in low for w in words):
                minute = default_h * 60
                break
    return shift, minute


def reading_timestamp(text: Optional[str], msg_ts: str) -> datetime:
    """Timestamp for this reading: the message time by default, overridden
    only when the patient explicitly mentions another day/time
    ("yesterday evening near 3pm", "14 july shaam 3 baje", ...)."""
    try:
        base = datetime.fromisoformat(str(msg_ts).replace("Z", "")[:19])
    except (ValueError, TypeError):
        base = now_local()
    shift, minute = time_reference(text)
    explicit = _explicit_date(text, base.date())
    if explicit is not None:
        shift = (explicit - base.date()).days
    if minute is None:
        minute = base.hour * 60 + base.minute
    day = base.date() + timedelta(days=shift)
    return datetime.combine(day, datetime.min.time().replace(
        hour=minute // 60, minute=minute % 60))


def _ts(raw: dict) -> datetime:
    try:
        return datetime.fromisoformat(raw["ts"].replace("Z", ""))
    except (KeyError, ValueError, AttributeError):
        return now_local()


def _as_reading(raw: dict, value) -> ParsedInput:
    try:
        v = float(value)
    except (TypeError, ValueError):
        v = math.nan
    tag = str(raw.get("reading_tag") or "").lower().strip()
    tag = _TAG_MAP.get(tag, tag or "random")
    if not (20 <= v <= 600):
        return ParsedInput(kind="refusal", raw=f"reading out of range: {value}")
    return ParsedInput(kind="reading", reading=v, reading_tag=tag,
                       ts=_ts(raw), raw=str(value))


def _reading_from_text(text: str, raw: Optional[dict] = None) -> Optional[ParsedInput]:
    ts = _ts(raw) if raw else now_local()
    text = normalize_glued_numbers(text)
    m = _READING_SHORT.match(text.strip())
    if m:
        val = float(m.group(1))
        if 20 <= val <= 600:
            return ParsedInput(kind="reading", reading=val, reading_tag="random",
                               ts=ts, raw=text.strip())
        return ParsedInput(kind="refusal", raw=text.strip())

    m_full = _READING_FULL.match(text)
    if m_full:
        val = float(m_full.group(2))
        prefix = m_full.group(1).lower().strip()
        tag = _tag_from_text(prefix)
        if 20 <= val <= 600:
            return ParsedInput(kind="reading", reading=val, reading_tag=tag,
                               ts=ts, raw=text.strip())
        return ParsedInput(kind="refusal", raw=text.strip())

    # Natural conversational pattern: e.g. "aaj subah fasting 135 tha", "my sugar is 142"
    low = text.lower().strip()
    # Scan a noise-stripped COPY (clocks, sizes, counts removed first) so
    # "today at 10 pm ... rading was 200" finds 200 — never the 2-digit hour —
    # and "3am" stays a time. The FULL text still drives context/tag words.
    scan = strip_reading_noise(low)
    # Find any standalone 2 to 3 digit number (with optional decimal)
    num_match = re.search(r"\b(\d{2,3}(?:\.\d)?)\s*(?:mg/?dl)?\b", scan)
    if num_match:
        context_words = (
            "sugar", "glucose", "bg", "fbs", "rbs", "ppbg", "mg/dl", "mgdl",
            "reading", "level", "fasting", "fast", "khali", "pet", "subah",
            "morning", "pre", "pehle", "post", "after", "baad", "breakfast",
            "nashta", "lunch", "dopahar", "dinner", "raat",
            "prick", "pricking", "fingerprick", "finger prick", "glucometer", "strip", "test"
        )
        if any(cw in low for cw in context_words):
            try:
                val = float(num_match.group(1))
            except ValueError:
                return None
            if not (20 <= val <= 600):
                # Not a glucose-sized number (clock hour, day, count) — this is
                # a meal/other message, never a refusal.
                return None

            tag = _tag_from_text(low)
            return ParsedInput(kind="reading", reading=val, reading_tag=tag,
                               ts=ts, raw=text.strip())

    return None


def _items(text: str, cfg: Settings) -> list[dict]:
    from .nutrition import classify_text, KATORI_LABELS
    rows = classify_text(text)
    out = []
    for r in rows:
        known = bool(r.get("known", True))
        out.append({
            "item": r["item"], "genus": r["genus"],
            "portion": r.get("portion", "m"),
            "portion_label": KATORI_LABELS.get(r.get("portion", "m")),
            # Carb/GI numbers are deliberately NOT written: the record keeps
            # only what the patient actually said (food + size).
            "known": known,
        })
    return out


def _mock_photo(raw: dict, cfg: Settings, mock_vision) -> list[dict]:
    from .nutrition import detect_photo, KATORI_LABELS
    now = now_local()
    if mock_vision is not None and callable(mock_vision):
        rows = mock_vision(raw.get("photo_path") or "", now.hour, 0)
    else:
        ts = raw.get("ts", "")
        day = int(ts[:10].replace("-", "")) if len(ts) >= 10 else int(now.strftime("%Y%m%d"))
        rows = detect_photo(now.hour, day, cfg)
    out = []
    for r in rows:
        out.append({
            "item": r["item"], "genus": r["genus"],
            "portion": r.get("portion", "m"),
            "portion_label": KATORI_LABELS.get(r.get("portion", "m")),
        })
    # health-year safety: keep the echo identical for later text correction
    return out


def describe_items(items: list[dict]) -> str:
    """Patient-facing echo of a detected plate — portion labels only, never numbers."""
    if not items:
        return "nothing I could recognise yet"
    parts = []
    for it in items[:4]:
        label = it.get("portion_label", "Medium (220 ml)")
        parts.append(f"{it['item']} · {label}")
    return ", ".join(parts) + ("." if parts else "")