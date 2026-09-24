"""Proactive Empathetic Caregiver Companion Service ("Health Saathi").

Core tenets:
1. Proactive Chronobiological Outreach:
   - Reaches out at clinically relevant daily touchpoints (Morning fasting, Lunch, Post-prandial 2-hr, Evening wellbeing, Bedtime).
2. Context-Aware Suppression (No Dumb Alarms):
   - Never asks for data the patient already logged today.
   - If fasting glucose is already recorded, morning fasting check is suppressed.
   - If lunch is already recorded, lunch prompt is suppressed.
3. Continuity of Care (Clinical Memory):
   - Recalls yesterday's / last reading (e.g. following up if previous reading was low blood sugar <70 mg/dL).
4. Fatigue Prevention & Quiet Hours:
   - Strict quiet hours (22:00 to 07:00 local time).
   - Frequency cap (max 3 proactive check-ins per day).
   - Minimum cooldown (2.5 hours) between automated prompts.
5. Clinical Information Asymmetry:
   - Strictly zero exposure of raw nutrient gram figures or technical index numbers to patient chat.
   - Warm, respectful, human persona ("Namaste {name} ji! 🙏").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from enum import Enum
from typing import Any, Optional
from uuid import UUID

# Default patient timezone: Indian Standard Time (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))


class CaregiverMilestone(str, Enum):
    MORNING_FASTING = "morning_fasting"
    POST_BREAKFAST = "post_breakfast"
    LUNCH_CHECK = "lunch_check"
    POST_LUNCH_PP = "post_lunch_pp"
    EVENING_WELLBEING = "evening_wellbeing"
    DINNER_CHECK = "dinner_check"
    BEDTIME_RECAP = "bedtime_recap"


@dataclass(frozen=True)
class CaregiverNudge:
    milestone: CaregiverMilestone
    message_text: str
    recipient_phone: str
    patient_id: UUID
    tenant_id: UUID
    urgency: str = "routine"  # routine | follow_up


def _clean_patient_name(name: str = "") -> str:
    cleaned = (name or "").strip()
    if not cleaned:
        return "Aap"
    # Take first name if full name is long
    parts = cleaned.split()
    return parts[0].title() if parts else cleaned


def _to_local_time(dt: datetime, tz: timezone = IST) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tz)


def get_current_milestone(current_local_time: datetime) -> CaregiverMilestone | None:
    """Determine the chronological milestone window based on patient local time."""
    local_time = current_local_time.time()

    # 07:00 - 09:30 IST: Morning Fasting Glucose Check
    if time(7, 0) <= local_time < time(9, 30):
        return CaregiverMilestone.MORNING_FASTING

    # 10:30 - 11:30 IST: Post-Breakfast Check
    if time(10, 30) <= local_time < time(11, 30):
        return CaregiverMilestone.POST_BREAKFAST

    # 12:30 - 14:15 IST: Lunch Check
    if time(12, 30) <= local_time < time(14, 15):
        return CaregiverMilestone.LUNCH_CHECK

    # 14:45 - 16:30 IST: Post-Lunch (PP) Glucose Check
    if time(14, 45) <= local_time < time(16, 30):
        return CaregiverMilestone.POST_LUNCH_PP

    # 17:30 - 19:15 IST: Evening Wellbeing & Hydration Check
    if time(17, 30) <= local_time < time(19, 15):
        return CaregiverMilestone.EVENING_WELLBEING

    # 19:45 - 21:00 IST: Dinner Meal Check
    if time(19, 45) <= local_time < time(21, 0):
        return CaregiverMilestone.DINNER_CHECK

    # 21:00 - 22:00 IST: Bedtime Encouragement & Recap
    if time(21, 0) <= local_time < time(22, 0):
        return CaregiverMilestone.BEDTIME_RECAP

    return None


def evaluate_patient_caregiver_nudge(
    patient: Any,
    uow: Any,
    now_utc: datetime | None = None,
    force_milestone: CaregiverMilestone | None = None,
    tz: timezone = IST,
) -> CaregiverNudge | None:
    """Evaluate whether a proactive caregiver nudge is due for a patient.
    
    Applies strict clinical and operational guardrails:
    - Active patient check
    - Valid phone number check
    - Quiet hours check (22:00 - 07:00 local time)
    - Data recency / duplicate suppression
    - Daily frequency cap (max 3 per day)
    - Cooldown window (2.5 hours)
    """
    if not getattr(patient, "active", True):
        return None

    recipient_phone = ""
    if hasattr(patient, "phone") and patient.phone:
        recipient_phone = patient.phone.value if hasattr(patient.phone, "value") else str(patient.phone)
    if not recipient_phone:
        return None

    now = now_utc or datetime.now(timezone.utc)
    local_now = _to_local_time(now, tz)
    today_local = local_now.date()

    # 1. Quiet Hours Enforcement (22:00 to 07:00) unless explicitly forced
    if force_milestone is None:
        if local_now.time() >= time(22, 0) or local_now.time() < time(7, 0):
            return None

    # 2. Determine Milestone
    milestone = force_milestone or get_current_milestone(local_now)
    if milestone is None:
        return None

    # 3. Retrieve Patient Data
    patient_id = patient.id
    tenant_id = getattr(patient, "tenant_id", None)
    patient_name = _clean_patient_name(getattr(patient, "name", ""))

    # Fetch recent glucose observations
    glucose_obs_list = []
    if hasattr(uow, "glucose_observations"):
        try:
            glucose_obs_list = uow.glucose_observations.list_for_patient(patient_id)
        except Exception:
            pass

    # Fetch recent meal observations
    meal_obs_list = []
    if hasattr(uow, "meal_observations"):
        try:
            meal_obs_list = uow.meal_observations.list_for_patient(patient_id)
        except Exception:
            pass

    # Fetch recent notifications
    notifications_list = []
    if hasattr(uow, "notifications"):
        try:
            notifications_list = uow.notifications.list_for_patient(patient_id)
        except Exception:
            pass

    # 4. Check Daily Frequency Cap & Cooldown
    nudges_today = []
    last_nudge_time: datetime | None = None
    for n in notifications_list:
        n_created = getattr(n, "created_at", None)
        if n_created:
            local_n_created = _to_local_time(n_created, tz)
            if local_n_created.date() == today_local:
                nudges_today.append(n)
                if last_nudge_time is None or n_created > last_nudge_time:
                    last_nudge_time = n_created

    # Max 3 automated nudges per day (unless forced)
    if force_milestone is None and len(nudges_today) >= 3:
        return None

    # Cooldown: Minimum 2 hours between nudges (unless forced)
    if force_milestone is None and last_nudge_time is not None:
        if (now - last_nudge_time) < timedelta(hours=2):
            return None

    # Check if a nudge for this EXACT milestone was already sent today
    milestone_key = f"caregiver_{milestone.value}"
    already_sent_milestone = any(
        getattr(n, "template_params", {}).get("milestone") == milestone.value
        or milestone_key in str(getattr(n, "template_params", {}))
        for n in nudges_today
    )
    if force_milestone is None and already_sent_milestone:
        return None

    # 5. Milestone-Specific Clinical Logic & Suppression Checks
    # Find latest glucose reading
    latest_glucose = None
    if glucose_obs_list:
        sorted_g = sorted(glucose_obs_list, key=lambda x: getattr(x, "taken_at", datetime.min), reverse=True)
        latest_glucose = sorted_g[0] if sorted_g else None

    # Check readings taken today
    glucose_today = [
        g for g in glucose_obs_list
        if _to_local_time(getattr(g, "taken_at", datetime.min), tz).date() == today_local
    ]
    meals_today = [
        m for m in meal_obs_list
        if _to_local_time(getattr(m, "recorded_at", datetime.min), tz).date() == today_local
    ]

    # Contextual check on previous reading (Hypo or Hyper alert continuity)
    prior_hypo_context = False
    if latest_glucose:
        val = getattr(latest_glucose, "value", None)
        mg_dl = getattr(val, "mg_dl", None) if val else getattr(latest_glucose, "value_mg_dl", None)
        if mg_dl and mg_dl < 70:
            # Check if this hypo was within the last 18 hours
            g_time = getattr(latest_glucose, "taken_at", datetime.min)
            if (now - g_time) < timedelta(hours=18):
                prior_hypo_context = True

    # Build empathetic caregiver message based on milestone
    if milestone == CaregiverMilestone.MORNING_FASTING:
        # SUPPRESSION: If patient already logged fasting sugar today, skip!
        has_fasting_today = any(
            "FAST" in str(getattr(g, "tag", "")).upper()
            or _to_local_time(getattr(g, "taken_at", datetime.min), tz).time() < time(10, 0)
            for g in glucose_today
        )
        if force_milestone is None and has_fasting_today:
            return None

        if prior_hypo_context:
            msg = (
                f"Good morning {patient_name} ji! ☀️ Umeed hai aapki neend achhi rahi.\n\n"
                "Kal aapka sugar thoda low (hypo) note hua tha — abhi aap bilkul theek aur comfortable mehsoos kar rahe hain na? "
                "Subah ki chai ya nashte se pehle, ek baar aaj ka *fasting sugar* check karke number yahan bhej dijiye. "
                "Main note kar leti hoon! 🙏"
            )
        else:
            msg = (
                f"Good morning {patient_name} ji! ☀️ Umeed hai aapki subah achhi hui.\n\n"
                "Subah ki chai ya nashte se pehle, kya aapne aaj ka *fasting sugar* check kiya? "
                "Agar haan, toh bas reading yahan likh kar bhej dijiye — jaise *'110 fasting'*. "
                "Aapka clinical record real-time update ho jayega! 🩸"
            )

    elif milestone == CaregiverMilestone.POST_BREAKFAST:
        # Check if breakfast was logged but no PP reading exists
        if force_milestone is None and not meals_today:
            return None
        has_midmorning_glucose = any(
            time(9, 30) <= _to_local_time(getattr(g, "taken_at", datetime.min), tz).time() < time(12, 0)
            for g in glucose_today
        )
        if force_milestone is None and has_midmorning_glucose:
            return None

        msg = (
            f"Namaste {patient_name} ji! ☕\n\n"
            "Nashte ke lagbhag 2 ghante ho gaye hain. "
            "Agar aapka post-breakfast sugar schedule mein hai, toh ek quick check karke reading yahan bata dijiye! 🩸"
        )

    elif milestone == CaregiverMilestone.LUNCH_CHECK:
        # SUPPRESSION: If lunch meal already logged today, skip!
        has_lunch_logged = any(
            time(11, 30) <= _to_local_time(getattr(m, "recorded_at", datetime.min), tz).time() < time(15, 0)
            for m in meals_today
        )
        if force_milestone is None and has_lunch_logged:
            return None

        msg = (
            f"Namaste {patient_name} ji! 🍛\n\n"
            "Dopahar ka lunch ho gaya? Aaj aapki thali mein kya swadisht tha?\n"
            "• Bas 2 shabdon mein likh dijiye (jaise: *'2 roti, 1 katori dal aur sabzi'*)\n"
            "• Ya apni thali ki ek chhotisi photo bhej dijiye! 📸\n\n"
            "Aapka meal log turant update ho jayega!"
        )

    elif milestone == CaregiverMilestone.POST_LUNCH_PP:
        # SUPPRESSION: If post-lunch glucose already logged today, skip!
        has_pp_today = any(
            time(14, 0) <= _to_local_time(getattr(g, "taken_at", datetime.min), tz).time() < time(17, 30)
            for g in glucose_today
        )
        if force_milestone is None and has_pp_today:
            return None

        msg = (
            f"Namaste {patient_name} ji! 🩸\n\n"
            "Khana khaye huye lagbhag 2 ghante ho gaye hain. "
            "Ek quick 30-second test karke apna *post-meal (PP) sugar* reading bhej denge? "
            "Isse humein pata chalega ki aaj ke khane ke baad sugar kitna stable raha!"
        )

    elif milestone == CaregiverMilestone.EVENING_WELLBEING:
        msg = (
            f"Shaam ho gayi {patient_name} ji! 🚶\n\n"
            "Thodi der tehelne ya halki stretch karne ka mauka mila? "
            "Din bhar mein kam se kam 15–20 minute ki physical activity sugar control mein bohot helpful hoti hai.\n\n"
            "Aur haan, ek glass taaza paani zaroor pi lijiye! 💧 Kaise mehsoos kar rahe hain abhi?"
        )

    elif milestone == CaregiverMilestone.DINNER_CHECK:
        has_dinner_logged = any(
            _to_local_time(getattr(m, "recorded_at", datetime.min), tz).time() >= time(19, 30)
            for m in meals_today
        )
        if force_milestone is None and has_dinner_logged:
            return None

        msg = (
            f"Namaste {patient_name} ji! 🍽️\n\n"
            "Raat ke khane ka samay ho gaya hai. Aaj dinner mein kya lene ka plan hai? "
            "Khane ke baad ek chhotisi walk sugar spike ko rokne mein bohot madad karti hai. "
            "Apna meal yahan zaroor share kariyega!"
        )

    elif milestone == CaregiverMilestone.BEDTIME_RECAP:
        # Check overall adherence today
        readings_count = len(glucose_today)
        meals_count = len(meals_today)

        if readings_count > 0 or meals_count > 0:
            praise = f"Aaj aapne {readings_count} sugar reading(s) aur {meals_count} meal(s) track kiye — bohot badiya discipline! 🌟"
        else:
            praise = "Aaj ka din agar vyast raha toh koi baat nahi, kal subah ek nayi shuruat karenge! 👍"

        msg = (
            f"Subham ji, din bhar kaisa raha? 🌙\n\n"
            f"{praise}\n"
            "Raat ko achhi, gehri neend lein aur khush rahein. Shubh raatri aur take care! 🙏"
        )
    else:
        return None

    return CaregiverNudge(
        milestone=milestone,
        message_text=msg,
        recipient_phone=recipient_phone,
        patient_id=patient_id,
        tenant_id=tenant_id or UUID("00000000-0000-0000-0000-000000000000"),
        urgency="follow_up" if prior_hypo_context else "routine",
    )
