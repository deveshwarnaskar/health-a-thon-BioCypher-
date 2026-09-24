# Meta WhatsApp Cloud API Test Runbook

This runbook provides step-by-step instructions for performing manual end-to-end verification of the **THALI × P.L.A.T.E.** WhatsApp integration using Meta's Cloud API Test Number.

---

## 1. Prerequisites Checklist

- [ ] Meta App: `THALI X P.L.A.T.E.` in Developer Dashboard
- [ ] Test Phone Number ID: `1273367152534156`
- [ ] WABA ID: `1622425102928569`
- [ ] Tester Phone Number added and verified under Meta "To" phone numbers list
- [ ] Valid access token placed in `.env` under `THALI_WHATSAPP__ACCESS_TOKEN`
- [ ] Backend running (`uvicorn backend.interfaces.http.app:app --port 8000`)
- [ ] Outbox Worker running (`python -m backend.interfaces.cli.worker --poll`)
- [ ] Webhook URL registered via ngrok / tunnel and subscribed to `messages`

---

## 2. Test Scenarios

### Scenario 1: Glucose Reading Logging (Standard)
1. From your verified tester WhatsApp, send:
   ```text
   140 fasting
   ```
2. **Expected System Response**:
   ```text
   Glucose reading 140 mg/dL darz ho gayi hai.
   ```
3. **Database Verification**:
   - `glucose_observations` table contains a new row with `value_mg_dl = 140`, `tag = 'FASTING'`.
   - `audit_events` records `GLUCOSE` creation by `SYSTEM_WORKER`.
   - Mobile app timeline displays `140 mg/dL Fasting`.

---

### Scenario 2: Stated-Time Glucose Logging
1. Send:
   ```text
   aaj subah 8 am 135
   ```
2. **Expected System Response**:
   ```text
   Glucose reading 135 mg/dL darz ho gayi hai.
   ```
3. **Verification**:
   - `glucose_observations.taken_at` timestamp is set to `08:00 AM` today.
   - `glucose_observations.created_at` timestamp reflects current ingestion time.

---

### Scenario 3: Ambiguous Glucose Reading Clarification
1. Send:
   ```text
   shayad 220 ya 320 tha
   ```
2. **Expected System Response**:
   ```text
   Aapka glucose reading clear nahi hai. Kripya ek reading bhejein (jaise: 140 fasting ya 180).
   ```
3. **Verification**:
   - No row created in `glucose_observations`.
   - `audit_events` records `AMBIGUOUS_READING`.

---

### Scenario 4: Meal Logging & Interactive Confirmation Loop
1. Send:
   ```text
   2 roti and dal
   ```
2. **Expected System Response**:
   ```text
   Aapne '2 roti and dal' khaya? Kripya confirm karein (YES/Haan ya portion: Small / Medium / Large).
   ```
   *(Interactive quick buttons: `[ Yes / Haan ]` `[ Cancel / Radd ]`)*
3. **Verification**:
   - `meal_observations` contains a new row with `confirmation = 'pending'`.
   - Outbound prompt does **not** disclose calculated carbs or glycemic index.

4. Reply with:
   ```text
   haan
   ```
   *(Or click `[ Yes / Haan ]`)*
5. **Expected System Response**:
   ```text
   Dhanyawad! Aapka meal record ho gaya hai.
   ```
6. **Verification**:
   - `meal_observations.confirmation` transitions to `'confirmed'`.

---

### Scenario 5: Meal Portion Correction
1. Send:
   ```text
   rice and fish curry
   ```
2. Reply with:
   ```text
   correct s
   ```
3. **Expected System Response**:
   ```text
   Dhanyawad! Aapka meal record ho gaya hai.
   ```
4. **Verification**:
   - `meal_observations.portion` volume is adjusted to `150 ml` (Small Katori).
   - `meal_observations.confirmation` is `'corrected'`.

---

### Scenario 6: Meal Draft Cancellation
1. Send:
   ```text
   had some sweets
   ```
2. Reply with:
   ```text
   cancel
   ```
   *(Or click `[ Cancel / Radd ]`)*
3. **Expected System Response**:
   ```text
   Aapka pending meal record cancel kar diya gaya hai.
   ```
4. **Verification**:
   - `meal_observations.confirmation` is updated to `'rejected'`.
   - Meal observation will not be presented as an active confirmed entry.

---

### Scenario 7: Status Inquiry
1. Send:
   ```text
   status
   ```
2. **Expected System Response**:
   ```text
   Aapka aakhri glucose reading: 140 mg/dL (fasting) (recorded at ...).
   ```
3. **Verification**:
   - Query executes read-only; no state mutations created.

---

### Scenario 8: Help Request
1. Send:
   ```text
   help
   ```
2. **Expected System Response**:
   ```text
   Namaste! THALI × P.L.A.T.E. WhatsApp Assistant:
   • Sugar darz karein: '120 fasting' ya '160 pp'
   • Khana darz karein: '2 roti dal'
   • Confirm karein: 'haan' ya 'theek hai'
   • Cancel karein: 'cancel'

   Medical emergency ke liye turant apne doctor ya hospital se sampark karein.
   ```

---

### Scenario 9: Intent Firewall Protection (Non-Clinical Query)
1. Send:
   ```text
   can you write a poem about flowers?
   ```
2. **Expected System Response**:
   ```text
   Main aapka THALI × P.L.A.T.E. health assistant hoon. Main kewal aapke blood sugar (glucose) aur meals record karne mein madad kar sakta hoon.

   Udaharan:
   • Glucose: '140 fasting' ya '180'
   • Meal: '2 roti aur dal'
   • Help: 'help' type karein.
   ```
3. **Verification**:
   - No clinical records created.
   - LLM generation blocked.
   - `audit_events` records `UNSUPPORTED_INTENT`.

---

### Scenario 10: Unregistered Sender Safety
1. Send a message from a number not enrolled in the system and with `THALI_WHATSAPP__TEST_NUMBER_MODE=false`.
2. **Expected System Response**:
   ```text
   Namaste! Yeh phone number THALI × P.L.A.T.E. mein registered nahi hai. Kripya apne registered phone number se message karein ya clinic se sampark karein.
   ```
3. **Verification**:
   - Worker logs clean refusal.
   - Zero clinical or cross-tenant data leaked.
