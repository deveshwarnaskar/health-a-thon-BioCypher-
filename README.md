# Aahaar — Glycemic Context for the Diabetes OPD

Health-a-thon 2026 · **Diabetes Care** track · **Doctor / Care-Team facing** solution
Anchor use case: **Consultation Readiness & Patient Journey Review**

**Concept:** Aahaar turns a patient's real meal photos + real glucose readings into a one-page **"Glycemic Context"** summary the doctor reads before/at consultation. It is **assistive, not diagnostic**: it organizes real data; the doctor decides. Never a dose, never a prediction.

Plans, PPT outline, Round 1 answers, and the (private) beginner guide live in `../plan-and-ppt/` — outside this git repo.

## Stack (planned)
- Frontend: React (Vite)
- Backend: Python FastAPI
- Nutrition estimate: vision model + Indian food table (human-confirmed estimates)
- Multilingual/voice: Sarvam AI (Saaras STT, Bulbul TTS, Sarvam LLM)
- Summary: LangChain agent
- Channel: web + WhatsApp logging
- Data: SQLite -> Postgres · **fake/anonymised data only**

Build sprint: **5 Oct – 8 Nov**. This directory is where the app is built.
