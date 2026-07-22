## AI Trip Planner

## Get a free API key
Go to https://console.groq.com/keys

## Run 

```bash
pip install -r requirements.txt
cp .env.example .env      # then edit .env and paste your real key
streamlit run app.py
```

## Models used

- **Itinerary generation**: `llama-3.3-70b-versatile` -- best quality on the
  free tier for the full multi-day plan.
- **Day regeneration**: `llama-3.1-8b-instant` -- fast and cheap, good enough
  for regenerating a single day.

## Free tier limits to know

Groq's free tier is rate-limited per model, tracked on both requests/minute
and tokens/minute -- whichever you hit first stops you. As of mid-2026,
`llama-3.3-70b-versatile` gets roughly 30 requests/minute and 1,000
requests/day; `llama-3.1-8b-instant` is more generous on both. If you hit a
`429` error, wait a minute and retry -- generating a full itinerary is a
single request, so this app rarely gets close to the caps.

Groq's free-tier model lineup changes fairly often (models get swapped in
and out, e.g. Kimi K2 disappeared from the free catalog earlier in 2026).
If you hit a `404` or "model decommissioned" error, check
https://console.groq.com/docs/models for the current lineup and update
`ITINERARY_MODEL` / `DAY_REGEN_MODEL` in your `.env` -- no other code
changes needed.


Author ~ Saroj Mandal

