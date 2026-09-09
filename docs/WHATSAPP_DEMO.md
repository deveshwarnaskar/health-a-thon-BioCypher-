# Real WhatsApp demo — guided walkthrough (Phase 5)

Goal: make a **real WhatsApp number** receive Aahaar's confirm-loop messages and replies,
using Meta's free **WhatsApp Cloud API test environment**. You will do the clicking (it needs
your identity + a one-time SMS); every step is spelled out below. The code side is already
done — `app/server/whatsapp.py` ships a `CloudBackend`, and `scripts/seed_real.py` re-seeds
the demo patient against your real number.

What this costs: **₹0**. What it needs: a phone you can receive an SMS on, and ~30–45 min.

---

## Big picture

```
your (hidden) Aahaar server ──webhook──► Meta WhatsApp Cloud API ("test number")
        ▲ replies                                           │
   cloudflared HTTPS tunnel                                 ▼
        ▲                                        WhatsApp on YOUR phone
   uvicorn :8000
```

1. Aahaar sends an outbound message → Meta delivers it to the patient's WhatsApp.
2. The patient's reply is delivered by Meta to your **webhook** → Aahaar processes it
   (confirm loop, reading guard, etc.) exactly like the simulator.

---

## Part A — create the free Meta developer environment (once)

1. Open **https://developers.facebook.com** in a browser. Log in with a Facebook account
   (a spare/old one is fine).
2. Click **My Apps → Create App** → use case: **Other**, then choose
   **Business → Manage Business Assets**. (Do NOT pick "Explore Business
   Platform / messaging" — that path wants business verification; the test env does not.)
3. Add a name (e.g. "Aahaar Demo"). Create.
4. On the app dashboard, find the **WhatsApp** product tile → **Set up**.
5. **Manage test number**: Meta gives you a phone number like `+1 (555) 123-4567` and a
   **temporary access token** (valid ~24 h — you will refresh it before the live demo).
6. Copy two things to a scratchpad:
   - **Phone number ID** (in the "Phone numbers" tile) → this is `META_PHONE_ID`
   - The **access token** → this is `META_TOKEN`
7. **Add recipients** (up to 5 numbers): add your own WhatsApp number and the test
   patient's number, each in international format without `+`/spaces.
   The token needs reissue after 24h — just click **Regenerate token** back in the
   test-number tile before each live session.

That's the whole Meta side until Part C.

---

## Part B — expose your Aahaar server to the internet (webhook)

Meta must be able to reach your server over public HTTPS. The free, no-install way is a
cloudflared quick-tunnel:

```bash
# terminal 1 — the aahaar server, pointed at the demo db and the CLOUD channel
cd /home/dev/health-a-thon-diabetes/code
AAHAAR_WHATSAPP=cloud \
AAHAAR_DB=aahaar-demo.db \
META_PHONE_ID=<FROM_PART_A_STEP_6> \
META_TOKEN=<FROM_PART_A_STEP_6> \
META_VERIFY=aahaar-verify \
python3 -m uvicorn app.server.main:app --host 0.0.0.0 --port 8000
```

```bash
# terminal 2 — public tunnel
cloudflared tunnel --url http://localhost:8000
# it prints something like: https://adjective-word-words.trycloudflare.com
# NOTE: if cloudflared isn't installed, ask me and I'll give you an alternative.
```

Now confirm it's public: open `https://<your-tunnel>.trycloudflare.com/healthz` in a
browser → should show `{"ok": true, ... "channel": "cloud"}`.

---

## Part C — register the webhook with Meta

Back in the Meta dashboard (WhatsApp tile → **Configuration**):

1. Under **Webhook → Callback URL** paste:
   `https://<your-tunnel>.trycloudflare.com/api/v1/webhooks/whatsapp`
2. Set **Verify token** to exactly `aahaar-verify`.
3. Click **Verify and save**. Meta calls our `/GET` verify route; the server checks
   `hub.verify_token` and echoes the challenge → it saves.
4. Under **Webhook fields**, subscribe to **messages** (and optionally
   `message_deliveries`).
5. Status must read **Active**.

---

## Part D — live test

1. Re-issue the token if you regenerated it (copy the new `META_TOKEN` into terminal 1 and
   restart uvicorn).
2. Make sure the demo database has a window for a patient whose **seed phone matches your
   real number**:
   ```bash
   python3 -m scripts.seed_real --phone +9198XXXXXXX --window 14
   ```
3. From your own WhatsApp, send a message to the **Meta test number**:
   - `fasting 128` → expect Aahaar's reading-confirm reply.
   - `2 roti, dal, sabzi` → expect the detected-plate + portion confirm → reply `yes`
     (or `correct l`) → "confirmed, it's in the report".
   - try a random/unknown number → expect the "ask the clinic to link your number" guard.
4. Optional true photo test: send a photo → in the webhook we download it and run the
   **mock vision** (no ML yet) — expect a "Detected: …" propose reply.

---

## Security + housekeeping reminders

- The token and phone-number ID MUST stay out of git (`AAHAAR_*`/`META_*` are runtime env
  vars, never committed). Secrets are already git-ignored.
- The test token dies in ~24 h — regenerate before any live demo.
- Only up to **5 real numbers** can be whitelisted; keep it to you + 1–2 "patients".
- Meta free tier only allows business-initiated messages inside a 24-hour window after the
  user messages you — that matches our flow (we only ever reply to / prompt loggers).
- Keep the tunnel URL fresh at demo time (regenerate if it changed; re-save the webhook).

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Callback URL verification failed" | Tunnel down? Check `/healthz` first. Then re-save webhook (a new tunnel = new URL) |
| Messages not arriving | Token expired → regenerate; restart uvicorn with the new value |
| Receiver can't message the test number | Number not in **Recipients list** (max 5) |
| `cloud send failed:` printed in terminal | Wrong `META_PHONE_ID`/`META_TOKEN`, token expired, or rate limit |
| Everything works but sender refused | The phone isn't a bound patient/caregiver — reseed with that number |

## Fallback if Meta blocks anything

The `simulator` channel (the dashboard's Messages tab) runs the exact same pipeline in the
browser, so the demo never dies — real WhatsApp is the "wow" layer, not the only layer.