# Handover

## 27.11.2026

- **0.3.0 released** (GitHub release v0.3.0) and deployed on eng-ai. **Break timer**: ☕ Break on the attendance list (pops up over the list, not the class screen),
  countdown, +/−1 min, End break, chime at zero (needs one click on the class screen to allow sound).
  Not yet seen in a real browser: check it on the projector before class.
- On campus network no VPN is needed; this Mac has no `eng-ai` ssh alias, use `eng-ai.buu.ac.th`.

## 26.11.2026

**State**
- 0.2.0 released (GitHub release v0.2.0) and deployed on eng-ai (https://eng-ai.buu.ac.th/attendance/, healthy).
- New in 0.2.0: votes (bar/pie) and short answers (grouped answer cloud) via **Ask the class**; sessions open on
  the attendance list instead of the QR code; **Close session** only on the list page; class screen "List" → "← Back".
- Live questions are held in memory only (`app/live.py`); nothing is saved, and a container restart clears them.
- Branches: work on `dev`, fast-forward into `main`. Both pushed and identical.

**Deploy** (needs NetBird VPN: `netbird up`)
`git archive HEAD | ssh eng-ai tar -x -C ~/dockers/production/attendance-check`, then on eng-ai
`cd ~/dockers/production/attendance-check && docker compose up -d --build`. Server `.env` and data stay in place.

**Local testing without SMTP**
Run uvicorn with `PUBLIC_URL=http://<LAN-IP>:8000/attendance`, `SECRET_KEY`, `DATA_DIR`, `ADMIN_EMAILS`,
`STUDENT_DOMAINS`; sign-in codes are printed in the server log ("would send to …").

**Open**
- Not yet tried in a real class (phones on campus Wi-Fi, many students at once).
- Thai and English answers to the same idea are not grouped together (by design; no AI matching).
