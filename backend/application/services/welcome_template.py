"""Rich structured welcome template for THALI x P.L.A.T.E. WhatsApp channel."""

from __future__ import annotations


def build_welcome_message(patient_name: str = "") -> str:
    """Construct an organized, patient-personalized WhatsApp onboarding message."""
    name = (patient_name or "").strip()
    greeting = f"Namaste {name} ji! 🙏" if name else "Namaste! 🙏"

    return (
        f"{greeting} Welcome to *THALI × P.L.A.T.E.* — aapka 24×7 personal health assistant aur diabetes care companion.\n\n"
        "Aapka WhatsApp number ab aapke THALI × P.L.A.T.E. health profile se safaltapoorvak link ho gaya hai! "
        "Aap jo bhi yahan share karenge, woh seedhe aapke doctor aur care team ke dashboard par real-time sync hota rahega.\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🎙️ *Text, Photo & Voice Note — Sabhi Suvidhaayein!*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Aapko lamba type karne ki bilkul zaroorat nahi hai. Aap teeno tareeqon se communicate kar sakte hain:\n"
        "• 💬 *Text*: Likh kar message bhejein\n"
        "• 📸 *Photo*: Apni plate/thali ki photo bhej kar meal track karein\n"
        "• 🎙️ *Voice Note*: WhatsApp ka mic button dabayein aur aaram se Hindi, English ya Hinglish mein bol kar bhej dein!\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🤝 *Main Aapka Companion Kaise Banunga?*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "• ⏰ *Timely Reminders*: Main aapko samay-samay par sugar check karne, khana log karne aur daily routine ke pyare reminders bhejunga.\n"
        "• 🩺 *Health & Wellbeing Check-ins*: Main aapse beech-beech mein poochhunga ki aap kaisa mehsoos kar rahe hain aur koi dikkat toh nahi ho rahi.\n"
        "• 📊 *Real-time Insights*: Har meal aur sugar reading par clinical analysis milta rahega.\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📝 *Records Kaise Log Karein? (How to Log)*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "1. 🩸 *Blood Sugar / Glucose Readings*:\n"
        "   Sugar darz karein — text likhein ya mic daba kar voice note 🎙️ bhejein:\n"
        "   👉 *'110 fasting'* ya *'118 fasting'* (subah khali pet)\n"
        "   👉 *'145 after lunch'* ya *'160 pp'*\n"
        "   👉 *'aaj subah 125 tha'*\n\n"
        "2. 🍽️ *Meals & Khana (Diet Tracking)*:\n"
        "   Aap Text, Plate Photo ya Voice Note teeno se khana darz kar sakte hain:\n"
        "   👉 *Text*: '2 roti, 1 katori dal aur thoda salad'\n"
        "   👉 *Plate Photo 📸*: Apni thali ki photo click karke yahan bhej dein!\n"
        "   👉 *Voice Note 🎙️*: Mic dabayein aur bol dein jo aapne khaya.\n"
        "   _(Hamara AI clinical engine automatically ICMR/NIN guidelines ke mutabiq carbohydrates, calories aur glycemic impact calculate kar lega.)_\n\n"
        "3. ⚠️ *Symptoms & Health Issues*:\n"
        "   Agar tabiyat kharaab lage ya sugar low/high ke lakshan lagein, text ya voice note 🎙️ mein batayein:\n"
        "   👉 *'Sir ghoom raha hai / chakkar aa rahe hain'*\n"
        "   👉 *'Bohot zyada pyaas ya kamzori lag rahi hai'*\n"
        "   Hum turant ise aapke record mein add karke doctor ko notify karenge.\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⚡ *Quick Commands*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "• *status* — Aapki aakhri sugar reading aur summary dekhne ke liye.\n"
        "• *help* — Yeh guide aur instructions dobara dekhne ke liye.\n"
        "• *cancel* — Galti se darz entry ko cancel karne ke liye.\n"
        "• *haan / yes* — Meal confirmation ke liye.\n\n"
        "✨ *Shuru karein!* Kripya apna aaj ka sugar reading ya pichhla meal text, photo 📸 ya voice note 🎙️ mein yahan bhejein! 👇\n\n"
        "⚠️ *Emergency Notice*: Kisi bhi severe emergency mein turant apne doctor ya nazdeeki hospital se sampark karein."
    )


__all__ = ["build_welcome_message"]
