import type { ReadingTag } from "./types";

export type ParsedGlucoseVoice = {
  value: number | null;
  tag: ReadingTag | null;
  rawTranscript: string;
};

const TAG_KEYWORDS: Record<ReadingTag, string[]> = {
  fasting: [
    "fasting",
    "khali pet",
    "khali pet",
    "subah",
    "morning",
    "before breakfast",
    "fbs",
    "empty stomach",
  ],
  premeal: [
    "pre-meal",
    "pre meal",
    "premeal",
    "before lunch",
    "before dinner",
    "before food",
    "khane se pehle",
  ],
  postbreakfast: [
    "post-breakfast",
    "post breakfast",
    "postbreakfast",
    "nashta",
    "after breakfast",
  ],
  postlunch: [
    "post-lunch",
    "post lunch",
    "postlunch",
    "after lunch",
    "dopahar",
    "lunch ke baad",
  ],
  postdinner: [
    "post-dinner",
    "post dinner",
    "postdinner",
    "after dinner",
    "dinner ke baad",
    "raat",
  ],
};

/**
 * Parses spoken Indic/English audio transcript for blood glucose value and context tag.
 */
export function parseGlucoseVoiceTranscript(transcript: string): ParsedGlucoseVoice {
  const clean = (transcript || "").trim();
  const lower = clean.toLowerCase();

  let detectedValue: number | null = null;
  let detectedTag: ReadingTag | null = null;

  // 1. Detect candidate numbers
  // Matches 2 to 3 digit numbers (e.g. 95, 115, 230)
  const numberMatches = clean.match(/\b\d{2,3}\b/g);
  if (numberMatches) {
    for (const match of numberMatches) {
      const num = parseInt(match, 10);
      if (num >= 20 && num <= 600) {
        detectedValue = num;
        break;
      }
    }
  }

  // 2. Detect context tag keywords
  for (const [tag, keywords] of Object.entries(TAG_KEYWORDS) as [ReadingTag, string[]][]) {
    if (keywords.some((kw) => lower.includes(kw))) {
      detectedTag = tag;
      break;
    }
  }

  return {
    value: detectedValue,
    tag: detectedTag,
    rawTranscript: clean,
  };
}
