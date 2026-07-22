"""
Trip planner -- single-file Streamlit app.

Calls Groq directly (no separate backend needed). Uses tool-forced
structured output so responses are always valid JSON matching our schema.
Groq's free tier needs no credit card -- see README for how to get a key.

Setup:
    pip install -r requirements.txt
    copy .env.example to .env and add your GROQ_API_KEY
    streamlit run app.py
"""

import os
import json
import streamlit as st
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

st.set_page_config(page_title="Trip planner", page_icon="🧭", layout="centered")

API_KEY = os.environ.get("GROQ_API_KEY")
ITINERARY_MODEL = os.environ.get("ITINERARY_MODEL", "llama-3.3-70b-versatile")
DAY_REGEN_MODEL = os.environ.get("DAY_REGEN_MODEL", "llama-3.1-8b-instant")

if not API_KEY:
    st.error(
        "No GROQ_API_KEY found. Create a `.env` file next to app.py "
        "(copy `.env.example`), add your key from https://console.groq.com/keys, "
        "then restart the app."
    )
    st.stop()

client = Groq(api_key=API_KEY)

# ---------------- JSON schemas (forced as tools so output is always valid) ----------------

ITINERARY_SCHEMA = {
    "type": "object",
    "properties": {
        "legs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "from": {"type": "string"},
                    "to": {"type": "string"},
                    "transport": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "mode": {"type": "string"},
                                "option": {"type": "string"},
                                "duration": {"type": "string"},
                                "avg_cost_inr": {"type": "number"},
                            },
                            "required": ["mode", "option", "duration", "avg_cost_inr"],
                        },
                    },
                },
                "required": ["from", "to", "transport"],
            },
        },
        "hotels": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "city": {"type": "string"},
                    "name": {"type": "string"},
                    "area": {"type": "string"},
                    "price_per_night_inr": {"type": "number"},
                    "why": {"type": "string"},
                },
                "required": ["city", "name", "area", "price_per_night_inr", "why"],
            },
        },
        "food": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "city": {"type": "string"},
                    "dish": {"type": "string"},
                    "note": {"type": "string"},
                },
                "required": ["city", "dish", "note"],
            },
        },
        "days": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "day": {"type": "number"},
                    "city": {"type": "string"},
                    "title": {"type": "string"},
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "time": {"type": "string"},
                                "place": {"type": "string"},
                                "note": {"type": "string"},
                            },
                            "required": ["time", "place", "note"],
                        },
                    },
                },
                "required": ["day", "city", "title", "items"],
            },
        },
        "budget_breakdown": {
            "type": "object",
            "properties": {
                "transport_inr": {"type": "number"},
                "stay_inr": {"type": "number"},
                "food_inr": {"type": "number"},
                "activities_inr": {"type": "number"},
                "total_inr": {"type": "number"},
            },
            "required": ["transport_inr", "stay_inr", "food_inr", "activities_inr", "total_inr"],
        },
        "tips": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["legs", "hotels", "food", "days", "budget_breakdown", "tips"],
}

DAY_SCHEMA = {
    "type": "object",
    "properties": {
        "day": {"type": "number"},
        "city": {"type": "string"},
        "title": {"type": "string"},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "time": {"type": "string"},
                    "place": {"type": "string"},
                    "note": {"type": "string"},
                },
                "required": ["time", "place", "note"],
            },
        },
    },
    "required": ["day", "city", "title", "items"],
}


def call_groq_structured(model, system, user_message, schema, tool_name, max_tokens=4000):
    response = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": "Return data in this exact structure.",
                    "parameters": schema,
                },
            }
        ],
        tool_choice={"type": "function", "function": {"name": tool_name}},
    )
    message = response.choices[0].message
    if message.tool_calls:
        return json.loads(message.tool_calls[0].function.arguments)
    raise RuntimeError("Model did not return structured output")


# ---------------- transport ground-truth data (heuristic, not a live API) ----------------
# A live flights/trains availability API (e.g. Amadeus for flights) would need a paid key,
# IATA/station code lookups, and OAuth -- overkill for what's actually needed here, which is
# just "does this city have an airport / rail access at all". A curated list solves the real
# complaint (phantom flights to airport-less towns) without that overhead. Extend the sets
# below if you hit a city that's missing. The model is also told the exact allowed modes per
# leg, and anything it returns outside that list gets stripped out afterwards as a safety net.

AIRPORT_CITIES = {
    "delhi", "new delhi", "mumbai", "bengaluru", "bangalore", "chennai", "kolkata",
    "hyderabad", "ahmedabad", "pune", "goa", "panaji", "dabolim", "mopa", "jaipur",
    "lucknow", "kochi", "cochin", "coimbatore", "thiruvananthapuram", "trivandrum",
    "kozhikode", "calicut", "guwahati", "bhubaneswar", "nagpur", "indore", "bhopal",
    "raipur", "ranchi", "patna", "varanasi", "amritsar", "chandigarh", "srinagar",
    "jammu", "leh", "dehradun", "udaipur", "jodhpur", "vadodara", "surat", "rajkot",
    "bhavnagar", "visakhapatnam", "vijayawada", "tirupati", "madurai",
    "tiruchirapalli", "trichy", "salem", "mangaluru", "mangalore", "hubli",
    "hubballi", "belagavi", "belgaum", "mysuru", "mysore", "aurangabad",
    "chhatrapati sambhajinagar", "nashik", "kolhapur", "shimla", "kullu", "manali",
    "bhuntar", "dharamshala", "kangra", "agartala", "imphal", "aizawl", "shillong",
    "dimapur", "dibrugarh", "jorhat", "silchar", "tezpur", "port blair", "agatti",
    "bagdogra", "siliguri", "gaya", "jharsuguda", "durgapur", "cooch behar",
    "puducherry", "pondicherry", "diu", "jaisalmer", "bikaner", "ajmer",
    "kishangarh", "kanpur", "prayagraj", "allahabad", "gorakhpur", "ayodhya",
    "rajahmundry", "kadapa", "kurnool", "warangal", "pantnagar", "bareilly",
    "gwalior", "jabalpur", "bilaspur", "latur", "nanded", "solapur", "sindhudurg",
    "porbandar", "kandla", "pakyong", "gangtok", "along", "pasighat", "tezu", "rupsi",
}

# Cities/regions with no meaningful mainline rail access (islands, high hill towns
# served mostly by road, etc.) -- heuristic, road/bus is usually still an option.
NO_RAIL_CITIES = {
    "leh", "ladakh", "kargil", "shimla", "manali", "kullu", "dharamshala",
    "mcleod ganj", "mussoorie", "nainital", "darjeeling", "gangtok", "munnar",
    "ooty", "coorg", "madikeri", "port blair", "andaman", "havelock island",
    "swaraj dweep", "neil island", "shaheed dweep", "lakshadweep", "agatti",
    "kavaratti", "minicoy", "diu", "daman", "spiti", "kaza", "tawang",
}

# Destinations with no *direct* access from an arbitrary source -- route via a
# gateway hub first, using whatever mode actually serves that last hop.
HUB_ROUTE = {
    "havelock island": ("Port Blair", ["ferry"]),
    "swaraj dweep": ("Port Blair", ["ferry"]),
    "neil island": ("Port Blair", ["ferry"]),
    "shaheed dweep": ("Port Blair", ["ferry"]),
    "agatti": ("Kochi", ["flight", "ship"]),
    "kavaratti": ("Kochi", ["flight", "ship"]),
    "minicoy": ("Kochi", ["flight", "ship"]),
    "spiti": ("Shimla", ["bus"]),
    "kaza": ("Shimla", ["bus"]),
    "tawang": ("Guwahati", ["bus"]),
}


def _norm(name):
    return name.strip().lower()


def _allowed_modes(a, b):
    an, bn = _norm(a), _norm(b)
    modes = []
    if an in AIRPORT_CITIES and bn in AIRPORT_CITIES:
        modes.append("flight")
    if an not in NO_RAIL_CITIES and bn not in NO_RAIL_CITIES:
        modes.append("train")
    modes.append("bus")
    return modes


def resolve_route_legs(route_cities):
    """Break a city-to-city route into legs. Inserts a gateway-hub leg for any
    destination with no direct access (e.g. islands), and attaches the real
    set of transport modes possible for each leg."""
    legs = []
    for i in range(len(route_cities) - 1):
        a, b = route_cities[i], route_cities[i + 1]
        bn = _norm(b)
        if bn in HUB_ROUTE:
            hub, hub_modes = HUB_ROUTE[bn]
            if _norm(hub) != _norm(a):
                legs.append({"from": a, "to": hub, "modes": _allowed_modes(a, hub)})
            legs.append({"from": hub, "to": b, "modes": hub_modes})
        else:
            legs.append({"from": a, "to": b, "modes": _allowed_modes(a, b)})
    return legs


def _filter_legs_to_allowed_modes(plan, resolved_legs):
    """Safety net: strip any transport option whose mode wasn't actually
    permitted for that leg, even if the model ignored the instruction."""
    allowed_by_pair = {(_norm(l["from"]), _norm(l["to"])): set(l["modes"]) for l in resolved_legs}
    for leg in plan.get("legs", []):
        allowed = allowed_by_pair.get((_norm(leg.get("from", "")), _norm(leg.get("to", ""))))
        if allowed:
            leg["transport"] = [
                t for t in leg.get("transport", [])
                if any(m in t.get("mode", "").lower() for m in allowed)
            ]
    return plan


def generate_itinerary(source, cities, budget_inr, group):
    total_days = sum(c["days"] for c in cities)
    route_desc = f"{source} -> " + " -> ".join(f"{c['city']} ({c['days']}d)" for c in cities)
    route_cities = [source] + [c["city"] for c in cities]
    resolved_legs = resolve_route_legs(route_cities)
    legs_desc = "\n".join(
        f"- {l['from']} -> {l['to']}: allowed modes = {', '.join(l['modes'])}" for l in resolved_legs
    )
    system = (
        "You are a travel planning engine for trips in and around India. Prices must reflect real "
        "current market rates for each option's class -- never distort a single fare or room rate "
        "just to make totals add up to the traveler's stated budget.\n\n"
        "Realistic INR anchors for one-way domestic transport (adjust for actual distance/route, "
        "and note these are illustrative, not exact -- use your best judgment for the specific route):\n"
        "- Flights (economy): ~2,500-4,500 for short hops (<500km), ~4,000-8,000 for medium "
        "(500-1500km), ~6,000-15,000 for long (1500km+). Add 20-40% for peak season or the only "
        "nonstop option.\n"
        "- Trains (AC 3-tier): ~500-1,500 short hops, ~1,200-2,500 medium, ~2,000-4,000 long. "
        "Sleeper class is roughly 40% of AC 3-tier.\n"
        "- Buses (AC/Volvo): ~300-800 short, ~800-1,800 medium; rarely used beyond ~1500km.\n"
        "- Ferries/ships (island hops): ~500-2,500 depending on distance and class.\n"
        "- Hotels per night: ~1,200-2,500 budget, ~2,500-5,000 mid-range, ~5,000-12,000+ premium, "
        "depending on city and area.\n\n"
        "To fit the stated total budget, choose which CLASS of option to feature (e.g. train + "
        "budget hotel vs flight + mid-range hotel) -- do not shrink or inflate an individual fare or "
        "room rate outside its realistic range just to hit a number. If even the cheapest realistic "
        "combination exceeds the stated budget, say so plainly in tips rather than underpricing "
        "fares to mask it.\n\n"
        "The exact legs of the journey, and which transport modes are actually possible for each, "
        "are given below -- follow this list exactly (same from/to pairs, same order, no legs "
        "added, removed, or merged). Only use modes from each leg's allowed list -- if a leg "
        "allows only train and bus, do not offer a flight for it even if a city elsewhere on the "
        "route has an airport. For each leg give 2-3 transport options within its allowed modes "
        "(e.g. different train classes/operators, or bus operators, if only one mode is allowed).\n\n"
        "One hotel per city (more for longer stays). 2-3 local food picks per city. One days[] "
        "entry per single day of the trip, in chronological order, tagged with its city. Tailor "
        "pace, hotel type, and food picks to the given group type (solo/duo/friends/family)."
    )
    user_message = (
        f"Route: {route_desc}. Total days: {total_days}. Total budget: INR {budget_inr}. "
        f"Traveling as: {group}.\n\nLegs:\n{legs_desc}"
    )
    plan = call_groq_structured(ITINERARY_MODEL, system, user_message, ITINERARY_SCHEMA, "build_itinerary")
    return _filter_legs_to_allowed_modes(plan, resolved_legs)


def regenerate_day(source, cities, group, day):
    route_desc = f"{source} -> " + " -> ".join(f"{c['city']} ({c['days']}d)" for c in cities)
    system = (
        "You are a travel planning engine. Regenerate a single day of an existing trip with a "
        "genuinely different plan than the one given -- different places, same city, same day "
        "number, same group type, similar budget level."
    )
    user_message = (
        f"Trip route: {route_desc}. Group type: {group}. Regenerate day {day['day']} in {day['city']}. "
        f"Previous plan for this day: {json.dumps(day)}. Give a fresh alternative."
    )
    return call_groq_structured(DAY_REGEN_MODEL, system, user_message, DAY_SCHEMA, "build_day", max_tokens=1200)


# ---------------- session state ----------------
# Each destination row has a stable id (not just its list position), so removing
# any one row -- first, middle, or last -- doesn't corrupt the widget state of
# the rows around it. Using list position as the widget key is what caused
# deletes to misbehave: after a row is removed everything below it shifts, but
# leftover session_state entries for the old positions confuse the next render.
if "city_ids" not in st.session_state:
    st.session_state.city_ids = [1]
    st.session_state.next_city_id = 2
    st.session_state["city_1"] = "Goa"
    st.session_state["days_1"] = 3
if "plan" not in st.session_state:
    st.session_state.plan = None
if "trip_ctx" not in st.session_state:
    st.session_state.trip_ctx = None
if "error" not in st.session_state:
    st.session_state.error = None
if "budget" not in st.session_state:
    st.session_state.budget = 25000


def add_city():
    cid = st.session_state.next_city_id
    st.session_state.next_city_id += 1
    st.session_state.city_ids.append(cid)
    st.session_state[f"city_{cid}"] = ""
    st.session_state[f"days_{cid}"] = 2


def remove_city(cid):
    if len(st.session_state.city_ids) > 1 and cid in st.session_state.city_ids:
        st.session_state.city_ids.remove(cid)
        st.session_state.pop(f"city_{cid}", None)
        st.session_state.pop(f"days_{cid}", None)


def _budget_step(v):
    if v < 50000:
        return 1000
    elif v < 100000:
        return 5000
    return 10000


# ---------------- UI ----------------
st.title("🧭 AI Trip planner")
st.caption("Source, stops, budget and who you're traveling with")

with st.form("trip_form", border=False):
    source = st.text_input("From", value="",placeholder="Enter Source City")

    st.markdown("**Destinations**")
    h1, h2, h3 = st.columns([3, 1, 0.6])
    h1.caption("City")
    h2.caption("Days")

    for cid in st.session_state.city_ids:
        col1, col2, col3 = st.columns([3, 1, 0.6])
        with col1:
            st.text_input(
                "City", key=f"city_{cid}", label_visibility="collapsed",value="",
                placeholder="Enter Destination City",
            )
        with col2:
            st.number_input(
                "Days", min_value=1, max_value=20, key=f"days_{cid}", label_visibility="collapsed",
            )
        with col3:
            st.form_submit_button(
                "✕", on_click=remove_city, args=(cid,),
                disabled=len(st.session_state.city_ids) <= 1,
                use_container_width=True, key=f"remove_city_{cid}",
            )

    st.form_submit_button("+ Add city", on_click=add_city)

    col_a, col_b = st.columns(2)
    with col_a:
        budget = st.number_input(
            "Total budget (INR)", min_value=2000, max_value=500000,
            step=_budget_step(st.session_state.budget), key="budget",
        )
    with col_b:
        group = st.selectbox(
            "Traveling as",
            options=["solo", "duo", "friends", "family"],
            format_func=lambda g: {
                "solo": "Solo", "duo": "Duo (couple / 2 friends)",
                "friends": "Group of friends", "family": "Family (with kids/elders)",
            }[g],
        )

    generate = st.form_submit_button("Generate itinerary", type="primary")

if generate:
    cities_payload = [
        {"city": st.session_state[f"city_{cid}"].strip(), "days": int(st.session_state[f"days_{cid}"])}
        for cid in st.session_state.city_ids if st.session_state[f"city_{cid}"].strip()
    ]
    if not source.strip() or not cities_payload:
        st.session_state.error = "Enter a source and at least one destination city."
        st.session_state.plan = None
    else:
        with st.spinner(f"Planning your trip from {source} through "
                         f"{', '.join(c['city'] for c in cities_payload)}..."):
            try:
                plan = generate_itinerary(source.strip(), cities_payload, int(budget), group)
                st.session_state.plan = plan
                st.session_state.trip_ctx = {
                    "source": source.strip(), "cities": cities_payload,
                    "budgetInr": int(budget), "group": group,
                }
                st.session_state.error = None
            except Exception as e:
                st.session_state.error = f"Failed to generate itinerary: {e}"
                st.session_state.plan = None

if st.session_state.error:
    st.error(st.session_state.error)

plan = st.session_state.plan
ctx = st.session_state.trip_ctx

if plan and ctx:
    total_days = sum(c["days"] for c in ctx["cities"])
    route = ctx["source"] + " → " + " → ".join(c["city"] for c in ctx["cities"])
    st.subheader(route)
    st.caption(f"{ctx['group'].capitalize()} trip · {total_days} days")

    if plan.get("legs"):
        st.markdown("### Getting there")
        for leg in plan["legs"]:
            st.markdown(f"**{leg['from']} → {leg['to']}**")
            cols = st.columns(len(leg["transport"]) or 1)
            for col, t in zip(cols, leg["transport"]):
                with col:
                    icon = "✈️" if "flight" in t["mode"].lower() or "air" in t["mode"].lower() \
                        else "🚆" if "train" in t["mode"].lower() else "🚌"
                    st.markdown(f"{icon} **{t['mode']}**")
                    st.caption(t["option"])
                    st.caption(t["duration"])
                    st.markdown(f"**₹{t['avg_cost_inr']:,.0f}**")

    if plan.get("hotels"):
        st.markdown("### Where to stay")
        for h in plan["hotels"]:
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(f"**{h['name']}** · {h['city']}")
                st.caption(f"{h['area']} — {h['why']}")
            with c2:
                st.markdown(f"₹{h['price_per_night_inr']:,.0f}/night")
        st.divider()

    if plan.get("food"):
        st.markdown("### Food to try")
        for f in plan["food"]:
            st.markdown(
                f"🍽️ **{f['dish']}** · {f['city']}  \n"
                f"<span style='color:gray;font-size:0.85em'>{f['note']}</span>",
                unsafe_allow_html=True,
            )
        st.divider()

    if plan.get("days"):
        st.markdown("### Day by day")
        for idx, d in enumerate(plan["days"]):
            with st.expander(f"Day {d['day']} · {d['city']} · {d['title']}", expanded=True):
                for it in d.get("items", []):
                    st.markdown(
                        f"**{it['time']}** — {it['place']}  \n"
                        f"<span style='color:gray;font-size:0.85em'>{it['note']}</span>",
                        unsafe_allow_html=True,
                    )
                if st.button("🔄 Regenerate this day", key=f"regen_{idx}"):
                    with st.spinner("Coming up with an alternative..."):
                        try:
                            new_day = regenerate_day(ctx["source"], ctx["cities"], ctx["group"], d)
                            st.session_state.plan["days"][idx] = new_day
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to regenerate day: {e}")

    if plan.get("budget_breakdown"):
        b = plan["budget_breakdown"]
        st.markdown("### Budget breakdown")
        cols = st.columns(4)
        for col, (label, key) in zip(
            cols,
            [("Transport", "transport_inr"), ("Stay", "stay_inr"),
             ("Food", "food_inr"), ("Activities", "activities_inr")],
        ):
            col.metric(label, f"₹{b[key]:,.0f}")
        st.markdown(f"**Total: ₹{b['total_inr']:,.0f}**")

    if plan.get("tips"):
        st.markdown("### Tips")
        for t in plan["tips"]:  
            st.markdown(f"- {t}")
