"""Empathetic, scientifically grounded clinical conversational assistant for WhatsApp.

Pure domain/application service:
1. Standard library imports only.
2. ICMR / RSSDI / ADA clinical diabetes management guidelines.
3. Clinical information asymmetry: strictly zero carb/GI words in patient-facing chat;
   instead uses intuitive portion sizing (katori/plate), fiber/protein balance tips, and clinical ranges.
4. Warm, respectful human tone with patient name personalization ("Namaste {name} ji! 🙏").
5. Hypoglycemia clinical safety protocol (Rule of 15 alert for glucose < 70 mg/dL).
"""

from __future__ import annotations

import re
from typing import Optional

_COMMON_STAPLES = [
    ("roti", "Roti", "Whole grain energy staple"),
    ("chapati", "Chapati", "Whole grain energy staple"),
    ("phulka", "Phulka", "Whole grain energy staple"),
    ("paratha", "Paratha", "Whole grain energy staple"),
    ("rice", "Rice", "Energy staple"),
    ("chawal", "Chawal", "Energy staple"),
    ("dal", "Dal", "Protein & fiber source"),
    ("daal", "Dal", "Protein & fiber source"),
    ("sambar", "Sambar", "Protein & fiber source"),
    ("rajma", "Rajma", "Protein & fiber source"),
    ("chole", "Chole", "Protein & fiber source"),
    ("sabzi", "Sabzi", "Fiber & micronutrients"),
    ("tarkari", "Sabzi", "Fiber & micronutrients"),
    ("bhaji", "Sabzi", "Fiber & micronutrients"),
    ("salad", "Salad", "Fresh fiber & micronutrients"),
    ("dahi", "Dahi", "Probiotic & calcium"),
    ("curd", "Curd", "Probiotic & calcium"),
    ("paneer", "Paneer", "Protein source"),
    ("chicken", "Chicken", "Protein source"),
    ("fish", "Fish", "Protein & omega-3 source"),
    ("egg", "Egg", "Protein source"),
    ("anda", "Egg", "Protein source"),
    ("oats", "Oats", "High fiber breakfast"),
    ("poha", "Poha", "Breakfast staple"),
    ("idli", "Idli", "Fermented breakfast staple"),
    ("dosa", "Dosa", "Breakfast staple"),
]


def _clean_name(patient_name: str = "") -> str:
    cleaned = (patient_name or "").strip()
    return cleaned if cleaned else ""


def build_glucose_clinical_response(
    patient_name: str,
    value_mg_dl: int,
    tag: Optional[str] = None,
) -> str:
    """Build a warm, clinically interpreted glucose response for the patient."""
    name = _clean_name(patient_name)
    prefix = f"Namaste {name} ji! 🙏\n" if name else ""

    tag_upper = (tag or "").upper()
    is_fasting = ("FASTING" in tag_upper or "FAST" in tag_upper)
    is_pp = any(
        x in tag_upper
        for x in (
            "POST_PRANDIAL",
            "POSTPRANDIAL",
            "PP",
            "POST_LUNCH",
            "POSTLUNCH",
            "POST_DINNER",
            "POSTDINNER",
            "POST_MEAL",
            "POSTMEAL",
            "POST_BREAKFAST",
            "POSTBREAKFAST",
        )
    ) or "POST" in tag_upper

    # Determine clinical feedback based on ICMR / RSSDI / ADA targets
    if value_mg_dl < 70:
        # Clinical emergency: Hypoglycemia
        return (
            f"{prefix}⚠️ *Dhyan dein: Sugar level {value_mg_dl} mg/dL darz ho gaya hai, yeh LOW (Hypoglycemia) hai!*\n\n"
            "👉 *Abhi kya karein (Rule of 15)*:\n"
            "1. Turant 3–4 chammach shakkar/glucose paani, aadha glass fruit juice, ya 3-4 candies lein.\n"
            "2. 15 minute aaram karein aur dobara sugar check karein.\n"
            "3. Agar kamzori ya chakkar barkaraar rahe, toh turant doctor ya emergency se sampark karein.\n\n"
            "Aapke care team dashboard par alert send kar diya gaya hai."
        )

    if is_fasting:
        context_str = "Fasting sugar"
        if 70 <= value_mg_dl <= 130:
            assessment = "✅ Yeh normal fasting target range (70–130 mg/dL) ke andar hai — bohot badhiya control! 👍"
            tip = "Subah ka halka aur balanced naashta karein."
        elif 131 <= value_mg_dl <= 180:
            assessment = "ℹ️ Yeh target fasting range se thoda elevated hai (target: < 130 mg/dL)."
            tip = "Paryapt paani peeyein aur naashte mein fiber (jaise oats/sprouts) shamil karein."
        else:
            assessment = "⚠️ Yeh target se kaafi high hai (target: < 130 mg/dL)."
            tip = "Apni prescribed medicine aur pani ka dhyan rakhein. Agar tabiyat ajeeb lage toh doctor se consult karein."
    elif is_pp:
        context_str = "Post-meal sugar"
        if value_mg_dl <= 140:
            assessment = "🌟 Bahut badhiya! Aapka post-meal level bilkul optimal hai (< 140 mg/dL)."
            tip = "Khane ke baad 10-15 minute ki halki walk sugar ko stable rakhne mein madad karti hai."
        elif 141 <= value_mg_dl <= 180:
            assessment = "✅ Yeh post-meal target (< 180 mg/dL) ke mutabiq stable hai! 👍"
            tip = "Aise hi balanced plate follow karte rahein."
        else:
            assessment = "ℹ️ Yeh post-meal target (< 180 mg/dL) se thoda high hai."
            tip = "Agle meal mein roti/chawal ki matra santulit rakhein aur sabzi/salad zyada lein."
    else:
        context_str = "Glucose reading"
        if 70 <= value_mg_dl <= 140:
            assessment = "✅ Reading normal range ke andar hai! 👍"
            tip = "Sehatmand aahar aur pani ka niyamit sevan karte rahein."
        elif 141 <= value_mg_dl <= 200:
            assessment = "ℹ️ Reading thodi elevated hai."
            tip = "Agle meal mein meetha lene se bachein aur hari sabzi badhayein."
        else:
            assessment = "⚠️ Reading high hai (target se zyada)."
            tip = "Paani khoob peeyein aur zaroorat padne par doctor se salah lein."

    return (
        f"{prefix}Aapki {context_str} *{value_mg_dl} mg/dL* safaltapoorvak darz kar li gayi hai.\n\n"
        f"{assessment}\n"
        f"💡 *Tip*: {tip}\n\n"
        "Doctor dashboard ke saath real-time sync kar diya gaya hai."
    )


def build_meal_clinical_prompt(
    patient_name: str,
    raw_description: str,
) -> str:
    """Build a natural, empathetic meal draft prompt acknowledging food composition."""
    name = _clean_name(patient_name)
    prefix = f"Namaste {name} ji! 🙏\n" if name else ""

    low_desc = raw_description.lower()
    plate_items = []
    seen = set()

    for token, label, desc in _COMMON_STAPLES:
        if re.search(r"\b" + re.escape(token) + r"\b", low_desc):
            if label not in seen:
                seen.add(label)
                # Attempt extracting preceding quantity (e.g. '2 roti' -> '2 ')
                m = re.search(r"(\d+)\s*" + re.escape(token), low_desc)
                qty_str = f"{m.group(1)} " if m else ""
                plate_items.append(f"• {qty_str}{label} ({desc})")

    composition_str = ""
    if plate_items:
        composition_str = "\n📋 *Plate Composition:*\n" + "\n".join(plate_items) + "\n"

    return (
        f"{prefix}Aapka meal *'{raw_description}'* note kar liya gaya hai.{composition_str}\n"
        "Kripya confirm karein kya portion sahi hai? (YES / Haan bhejein, ya portion: Small / Medium / Large batayein). 👇\n\n"
        "Confirm karte hi yeh aapke clinical record mein update ho jayega."
    )


def build_meal_confirmation_response(
    patient_name: str,
    meal_description: str,
    portion_label: str,
) -> str:
    """Build a warm acknowledgment once a meal is confirmed."""
    name = _clean_name(patient_name)
    prefix = f"Dhanyawad {name} ji! 🙏" if name else "Dhanyawad! 🙏"

    return (
        f"{prefix} Aapka meal *'{meal_description}'* ({portion_label}) record ho gaya hai.\n\n"
        "✅ Yeh record aapke doctor aur clinical care team ke dashboard par sync ho gaya hai. "
        "Aise hi regular meal tracking se aapka blood sugar control behtar hoga! 🥗"
    )


def match_conversational_query(text: str, patient_name: str = "") -> Optional[str]:
    """Identify if text is a conversational healthcare/assistant question and generate a human reply."""
    low = (text or "").strip().lower()
    if not low:
        return None

    name = _clean_name(patient_name)
    greeting = f"Namaste {name} ji! 🙏 " if name else "Namaste! 🙏 "

    # 1. Onboarding / How-to-log / Connected confirmation
    how_to_patterns = (
        r"\b(how\s+(can|do|to)\s+(i\s+)?(log|record|enter|track|use|send))\b",
        r"\b(kaise\s+(log|darz|record|bhejein|karein|bhej|use))\b",
        r"\b(whatsapp\s+is\s+connected|connected|jud\s+gaya|connect\s+ho\s+gaya)\b",
        r"\b(kya\s+karna\s+hai|what\s+should\s+i\s+do\s+next)\b",
    )
    if any(re.search(pat, low) for pat in how_to_patterns):
        return (
            f"{greeting}Aapka WhatsApp account bilkul sahi tareeqe se jud chuka hai!\n\n"
            "Aap yahan 2 zaroori cheezein aasaani se note kar sakte hain:\n"
            "1. 🩸 *Blood Sugar*: Bas likh kar bhejein, jaise:\n"
            "   👉 '118 fasting'\n"
            "   👉 '142 post lunch'\n"
            "2. 🍽️ *Khana (Meals)*: Jo bhi aapne khaya, natural bhasha mein batayein, jaise:\n"
            "   👉 '2 roti aur dal'\n"
            "   👉 '1 bowl oats aur doodh'\n"
            "   📸 Aap apni thali ki photo bhi bhej sakte hain!\n\n"
            "Hamaara AI engine automatically ise calculate karke aapke doctor ke dashboard par update karta rahega. "
            "Abhi shuru karne ke liye apna sugar reading ya pichhla meal yahan likh kar bhejein! 👇"
        )

    # 2. Acute symptoms / Dizziness / Low sugar feeling
    symptom_patterns = (
        r"\b(chakkar|dizzy|dizziness|kamzori|weakness|shivering|faint|behoshi|sweating|pasina|pyaas|thirsty)\b",
        r"\b(tabiyat\s+kharab|not\s+feeling\s+well|chhati\s+mein\s+dard)\b",
    )
    if any(re.search(pat, low) for pat in symptom_patterns):
        return (
            f"⚠️ *Dhyan dein {name} ji*:\n"
            "Chakkar aana, kamzori ya achanak pasina aana low blood sugar (Hypoglycemia) ke sanket ho sakte hain.\n\n"
            "👉 *Turant karein*:\n"
            "1. Agar glucometer paas hai, turant sugar check karein.\n"
            "2. Agar sugar < 70 mg/dL hai ya measurement sambhav nahi hai, turant 3–4 chammach glucose/shakkar paani ya thoda fruit juice lein.\n"
            "3. 15 minute aaram karein.\n\n"
            "⚠️ Agar tabiyat zyada kharab lage ya seene mein dard/behoshi mehsoos ho, toh bina deri kiye turant doctor ya emergency hospital se sampark karein."
        )

    # 3. Dietary & Food questions (Fruits, Mango, Rice, Sweets, etc.)
    has_question = bool(
        re.search(
            r"\b(kha\s+sakta|kha\s+sakte|can\s+i\s+eat|should\s+i\s+eat|diet\s+mein|kya\s+khayein|allowed|permission|safe\s+to\s+eat)\b",
            low,
        )
        or "?" in low
    )
    has_food_topic = bool(
        re.search(
            r"\b(mango|aam|mithai|sweet|sugar\s+free|rice|chawal|banana|kela|chikoo|grapes|angur|fruit|fruits|diet|food|eat|eating)\b",
            low,
        )
    )
    if has_question and has_food_topic:
        return (
            f"{greeting}Diabetes care mein khane-peene ka santulan sabse mahatvapoorna hai (ICMR guidelines):\n\n"
            "• 🥭 *Meethe Phal (Aam, Kela, Chikoo)*: Inme natural fruit sugars tez asar karti hain. Inhe kam matra mein (jaise aam ke 1-2 slice) khayein, preferably khane ke turant baad nahi balki mid-morning snack ke roop mein, sath mein 4-5 badam/nuts lein.\n"
            "• 🥗 *Thali ka Niyam (Balanced Plate)*: Aadhi plate hari sabzi/salad, 1 katori dal/paneer (protein), aur 1-2 roti rakhein. Isse khane ke baad sugar spike nahi hota.\n"
            "• 🍚 *Chawal*: Brown rice ya boiled rice kam matra mein dal/sabzi ke sath lein.\n\n"
            "Aap jo bhi khayein, yahan likh kar bhej dein (jaise '1 bowl rice aur dal') taaki doctor ko aapke diet pattern ka pata rahe!"
        )

    # 4. Gratitude / Pleasantries
    thanks_patterns = (
        r"\b(thank\s*you|thanks|dhanyawad|shukriya|bahut\s+achha|great|good\s+job)\b",
        r"\b(good\s+morning|shubh\s+prabhat|good\s+evening|shubh\s+sandhya|good\s+night)\b",
    )
    if any(re.search(pat, low) for pat in thanks_patterns):
        return (
            f"Aapka bohot swagat hai {name} ji! 🙏\n"
            "Aapki sehat aur care team ka coordination hamari pehli prathmikta hai. "
            "Kisi bhi samay apna sugar reading ya khana yahan share kar sakte hain. Sehatmand aur khush rahein! 🌟"
        )

    return None


def generate_conversational_reply(
    text: str,
    patient_name: str = "",
    ai_completer: Optional[Any] = None,
) -> str:
    # 1. First check critical emergency safety triage patterns (hypoglycemia symptoms, acute weakness/dizziness)
    name = _clean_name(patient_name)
    low = (text or "").strip().lower()
    symptom_patterns = (
        r"\b(chakkar|dizzy|dizziness|kamzori|weakness|shivering|faint|behoshi|sweating|pasina|pyaas|thirsty)\b",
        r"\b(tabiyat\s+kharab|not\s+feeling\s+well|chhati\s+mein\s+dard)\b",
    )
    if any(re.search(pat, low) for pat in symptom_patterns):
        return (
            f"⚠️ *Dhyan dein {name} ji*:\n"
            "Chakkar aana, kamzori ya achanak pasina aana low blood sugar (Hypoglycemia) ke sanket ho sakte hain.\n\n"
            "👉 *Turant karein*:\n"
            "1. Agar glucometer paas hai, turant sugar check karein.\n"
            "2. Agar sugar < 70 mg/dL hai ya measurement sambhav nahi hai, turant 3–4 chammach glucose/shakkar paani ya thoda fruit juice lein.\n"
            "3. 15 minute aaram karein.\n\n"
            "⚠️ Agar tabiyat zyada kharab lage ya seene mein dard/behoshi mehsoos ho, toh bina deri kiye turant doctor ya emergency hospital se sampark karein."
        )

    # 2. Try external AI completer (Sarvam Indic AI) for natural, personalized, culturally nuanced health guidance
    if ai_completer is not None and callable(ai_completer):
        try:
            ai_reply = ai_completer(text, patient_name)
            if ai_reply:
                return str(ai_reply).strip()
        except Exception:
            pass

    # 3. Deterministic rules fallback (dietary staples, onboarding guides, pleasantries)
    deterministic_match = match_conversational_query(text, patient_name=patient_name)
    if deterministic_match:
        return deterministic_match

    # 3. Safe fallback guidance
    name = _clean_name(patient_name)
    prefix = f"Namaste {name} ji! 🙏 " if name else "Namaste! 🙏 "
    return (
        f"{prefix}Main aapka THALI health companion hoon. "
        "Aap yahan apna blood sugar reading (jaise '120 fasting') ya khana (jaise '2 roti aur dal') darz kar sakte hain. "
        "Kisi bhi emergency ya tez asuvidha mein kripya turant apne doctor ya najdeeki hospital se sampark karein."
    )


__all__ = [
    "build_glucose_clinical_response",
    "build_meal_clinical_prompt",
    "build_meal_confirmation_response",
    "match_conversational_query",
    "generate_conversational_reply",
]
