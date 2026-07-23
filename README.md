## AI Trip Planner

A single-file Streamlit web app that generates a complete, realistic India
trip itinerary — route, transport, hotels, food, day-by-day plan, and
budget breakdown — from a simple form. Powered by Groq's free Llama
inference API, with schema-enforced JSON output so the app never has to
parse messy text.

## Features

- **Multi-city itinerary generation** — enter a source city, any number of
  destination cities with days per stop, a total budget, and a group type
  (solo/duo/friends/family); get back a full trip plan
- **Grounded transport suggestions** — flight/train/bus options are
  validated against a real dataset of which Indian cities actually have
  airports or rail access, so the app won't invent a flight to a town with
  no airport. Islands and remote destinations with no direct access are
  automatically routed through their real gateway hub (e.g. a ferry from
  Port Blair to Havelock Island)
- **Realistic budget-aware pricing** — the model is anchored to real INR
  price bands by distance/class, so costs reflect market rates rather than
  being distorted to artificially match your stated budget
- **Day-by-day plan with regeneration** — expandable daily itinerary; each
  day can be regenerated independently for a fresh alternative without
  re-running the whole trip
- **Budget breakdown** — transport / stay / food / activities split with a
  total, plus trip tips
- **Guaranteed valid output** — uses Groq's tool-calling (forced JSON
  schema) so every response is structured data, never freeform text that
  needs parsing
- **Dynamic destination list** — add/remove destination rows freely; each
  row has a stable identity so deleting one never corrupts the others

## Prerequisites

- Python 3.9+
- A free Groq API key (no credit card required) — get one at
  https://console.groq.com/keys

## Setup & Run

```bash
# 1. Clone the repo
git clone https://github.com/sarojmandal6354/AI-Trip-Planner.git
cd AI-Trip-Planner

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure your API key
cp .env.example .env
# then open .env and paste your real GROQ_API_KEY

# 4. Run the app
streamlit run app.py
```

The app will open at `http://localhost:8501`.

### Environment variables (`.env`)

| Variable | Required | Default | Description |
|---|---|---|---|
| `GROQ_API_KEY` | Yes | — | Your Groq API key |
| `ITINERARY_MODEL` | No | `llama-3.3-70b-versatile` | Model used for full itinerary generation |
| `DAY_REGEN_MODEL` | No | `llama-3.1-8b-instant` | Faster/cheaper model used for single-day regeneration |

## Project Structure

```
AI-Trip-Planner/
├── app.py             # Entire application: UI, transport data, prompts, API calls
├── requirements.txt   # Python dependencies (streamlit, groq, python-dotenv)
├── .env.example        # Template for required environment variables
├── .gitignore
└── README.md
```

`app.py` is organized top to bottom as:

1. **Setup** — env loading, Groq client init
2. **JSON schemas** (`ITINERARY_SCHEMA`, `DAY_SCHEMA`) — enforced via
   tool-calling so responses are always valid, structured JSON
3. **`call_groq_structured()`** — shared helper that forces a tool call and
   returns its parsed arguments
4. **Transport ground-truth data** — `AIRPORT_CITIES`, `NO_RAIL_CITIES`,
   `HUB_ROUTE`, plus `resolve_route_legs()` / `_filter_legs_to_allowed_modes()`,
   which compute which transport modes are physically possible per leg
   *before* calling the model, and strip any invalid mode the model returns
   anyway
5. **`generate_itinerary()` / `regenerate_day()`** — build prompts and call
   the model
6. **Streamlit UI** — the trip form (source, dynamic destination rows,
   budget, group type) and the rendered itinerary output

## Notes

- **This is a heuristic transport dataset, not a live flights/trains API.**
  It's a curated list of major Indian cities with commercial airports and
  known rail-access gaps — accurate for common routes and popular
  destinations, but not exhaustive. If a city is missing, add it to
  `AIRPORT_CITIES` / `NO_RAIL_CITIES` / `HUB_ROUTE` in `app.py`. A true
  live-availability integration (e.g. Amadeus for flights) would require a
  paid API, IATA code lookups, and OAuth — out of scope for this project.
- **Groq's free tier is rate-limited** (requests/minute and tokens/minute).
  A `429` error just means you've briefly hit the limit — wait a minute and
  retry. Generating one itinerary is a single request, so normal use rarely
  gets close to the caps.
- **Groq's free-tier model lineup changes periodically.** If you hit a
  `404` / "model decommissioned" error, check
  https://console.groq.com/docs/models for the current list and update
  `ITINERARY_MODEL` / `DAY_REGEN_MODEL` in `.env` — no code changes needed.
- **This app is a persistent Streamlit server, not a serverless function**
  — it won't deploy on platforms built for stateless functions (e.g.
  Vercel's Python runtime). Use a host that runs a long-lived process
  instead: Streamlit Community Cloud, Hugging Face Spaces, Render, or
  Railway.
- All prices shown are AI-generated estimates for planning purposes, not
  live fares — always verify actual prices before booking.

---
Author — Saroj Mandal