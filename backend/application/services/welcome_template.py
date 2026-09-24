"""Rich structured welcome template for THALI x P.L.A.T.E. WhatsApp channel."""

from __future__ import annotations


def build_welcome_message(patient_name: str = "") -> str:
    """Construct an organized, patient-personalized WhatsApp onboarding message."""
    name = (patient_name or "").strip()
    greeting = f"Namaste {name} ji! 🙏" if name else "Namaste! 🙏"

    return (
        f"{greeting} Welcome to *THALI × P.L.A.T.E.* — your personal health assistant & diabetes care companion.\n\n"
        "🔗 *Kyu judaa hai yeh WhatsApp account? (Purpose of Connection)*\n"
        "Aapka WhatsApp number ab aapke THALI × P.L.A.T.E. health profile se safaltapoorvak link ho gaya hai. "
        "Iska mukhya uddeshya hai ki aap bina kisi jhanjhat ke, directly WhatsApp par apna daily glucose aur khana track kar sakein, "
        "jo seedhe aapke doctor aur care team ke dashboard ke saath real-time sync hota hai.\n\n"
        "📋 *Aap yahan kya-kya share kar sakte hain? (What you can share)*\n"
        "1. 🩸 *Blood Sugar / Glucose Readings*:\n"
        "   • Apni reading seedhe likhein, jaise:\n"
        "     👉 '110 fasting'\n"
        "     👉 '145 after lunch' ya '160 pp'\n"
        "     👉 'aaj subah 125 tha'\n\n"
        "2. 🍽️ *Meals & Daily Diet (Khana)*:\n"
        "   • Jo bhi aapne khaya, natural bhasha mein likhein:\n"
        "     👉 '2 roti aur 1 katori dal'\n"
        "     👉 '1 bowl rice, mixed sabzi aur dahi'\n"
        "     👉 '2 idli and sambar'\n"
        "   • Aap apni thali/plate ki photo bhi bhej sakte hain! 📸\n"
        "   • Hamaara AI/ML clinical engine automatically ICMR/IFCT dietary guidelines ke anusar carbohydrates aur glycemic index calculate karta hai.\n\n"
        "⚡ *Kaise use karein? (Quick Helpful Commands)*\n"
        "• *'status'* — Aapki aakhri glucose reading aur summary dekhne ke liye.\n"
        "• *'help'* — Madad aur instructions dobara dekhne ke liye.\n"
        "• *'cancel'* — Kisi galti se darz meal draft ko cancel karne ke liye.\n"
        "• *'Yes / Haan'* — Khana confirm karne ke liye jab THALI aapse portion poochhe.\n\n"
        "Aapka health safar aasan aur scientifically proven tareeqe se manage hoga. "
        "Shuru karne ke liye, kripya apna aaj ka sugar reading ya pichhla meal yahan likh kar bhejein! 👇\n\n"
        "⚠️ *Emergency Notice*: Emergency ya acute medical symptoms hone par turant apne doctor ya hospital se sampark karein."
    )


__all__ = ["build_welcome_message"]
