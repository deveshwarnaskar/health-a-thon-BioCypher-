import { useState, useEffect } from "react";
import type { SupportedLanguage, TranslationDictionary } from "./types";
import { en } from "./translations/en";
import { hi } from "./translations/hi";
import { bn } from "./translations/bn";
import { ta } from "./translations/ta";
import { te } from "./translations/te";
import { mr } from "./translations/mr";

export type { SupportedLanguage } from "./types";

const translations: Record<SupportedLanguage, TranslationDictionary> = {
  en,
  hi,
  bn,
  ta,
  te,
  mr,
};

type NestedKeyOf<ObjectType extends object> = {
  [Key in keyof ObjectType & (string | number)]: ObjectType[Key] extends object
    ? `${Key}.${NestedKeyOf<ObjectType[Key]>}`
    : `${Key}`;
}[keyof ObjectType & (string | number)];

export type TranslationKey = NestedKeyOf<TranslationDictionary>;

class I18nManager {
  private currentLanguage: SupportedLanguage = "en";
  private listeners = new Set<(lang: SupportedLanguage) => void>();

  getLanguage(): SupportedLanguage {
    return this.currentLanguage;
  }

  setLanguage(lang: SupportedLanguage): void {
    if (this.currentLanguage === lang) return;
    if (!(lang in translations)) return;
    this.currentLanguage = lang;
    for (const listener of this.listeners) {
      try {
        listener(lang);
      } catch {
        // Listener failure shouldn't crash i18n
      }
    }
  }

  subscribe(listener: (lang: SupportedLanguage) => void): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  /**
   * Resolves translation key with guaranteed English fallback.
   * NEVER returns a raw unrendered key to the user.
   */
  t(key: TranslationKey | string, params?: Record<string, string | number>): string {
    const parts = key.split(".");
    let value = this.resolvePath(translations[this.currentLanguage], parts);

    // Fallback to English if missing in selected language
    if (value === undefined && this.currentLanguage !== "en") {
      value = this.resolvePath(translations.en, parts);
    }

    // Safety fallback if completely missing
    if (value === undefined) {
      // Return a human-readable title-cased string of the last segment instead of raw key
      const fallback = parts[parts.length - 1] ?? key;
      const spaced = fallback.replace(/([A-Z])/g, " $1").trim();
      value = spaced.charAt(0).toUpperCase() + spaced.slice(1);
    }

    if (params) {
      for (const [pKey, pVal] of Object.entries(params)) {
        value = value.replace(new RegExp(`{{${pKey}}}`, "g"), String(pVal));
      }
    }

    return value;
  }

  private resolvePath(obj: any, parts: string[]): string | undefined {
    let current = obj;
    for (const part of parts) {
      if (!current || typeof current !== "object") return undefined;
      current = current[part];
    }
    return typeof current === "string" ? current : undefined;
  }
}

export const i18n = new I18nManager();
export const t = (key: TranslationKey | string, params?: Record<string, string | number>): string =>
  i18n.t(key, params);

export function useTranslation(): {
  t: (key: TranslationKey | string, params?: Record<string, string | number>) => string;
  language: SupportedLanguage;
  setLanguage: (lang: SupportedLanguage) => void;
} {
  const [language, setLanguageState] = useState<SupportedLanguage>(i18n.getLanguage());

  useEffect(() => {
    return i18n.subscribe((newLang) => {
      setLanguageState(newLang);
    });
  }, []);

  return {
    t: (key, params) => i18n.t(key, params),
    language,
    setLanguage: (lang) => i18n.setLanguage(lang),
  };
}
