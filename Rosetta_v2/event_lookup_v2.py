# event_lookup_v2.py
# ------------------------------------------------------------
# Streamlit block: shows major astro events near a chart date
# - Relative time in days / hours / minutes
# - Fallback when exact event time isn't listed (days-only + note)
# - No zodiac degree/sign display
# ------------------------------------------------------------

import json
import streamlit as st
from datetime import datetime

if "chart_dt_utc" not in st.session_state:
    st.session_state["chart_dt_utc"] = None

# --- Load events.jsonl once ---
@st.cache_data
def load_events(path="events.jsonl"):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]

# --- Event-specific search windows (days) ---
WINDOWS = {
    "eclipse": 7,
    "ingress": 3,
    "lunation": 1,
    "station": 2,
    "perigee": 2,
    "apogee": 2,
}
EXCLUDED = {"opposition"}


def _parse_ts(ts: str) -> datetime:
    """ISO '...Z' -> aware datetime (UTC)."""
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _is_exact_time(ev: dict) -> bool:
    """
    Decide whether the event has an exact time.
    Prefer explicit flag if present; otherwise use a safe heuristic:
    treat '...T00:00:00Z' as not listed.
    """
    meta = ev.get("meta", {})
    if "time_listed" in meta:
        return bool(meta["time_listed"])
    ts = ev.get("timestamp_ut", "")
    return not ts.endswith("T00:00:00Z")

def _format_delta(delta_seconds: float, exact: bool) -> str:
    """
    Human-friendly 'before/after' string.
    - exact=True  -> days / hours / minutes
    - exact=False -> 'same day' if within 24h; otherwise whole days only
    """
    if exact:
        sign = "after" if delta_seconds > 0 else ("before" if delta_seconds < 0 else "at")
        sec = abs(int(delta_seconds))
        days = sec // 86400
        sec %= 86400
        hours = sec // 3600
        sec %= 3600
        minutes = sec // 60

        parts = []
        if days:
            parts.append(f"{days} day{'s' if days != 1 else ''}")
        if hours:
            parts.append(f"{hours} hr{'s' if hours != 1 else ''}")
        if minutes or not parts:
            parts.append(f"{minutes} min")
        if sign == "at":
            return "at chart time"
        return f"{' '.join(parts)} {sign} chart"

    # Not exact time: treat anything <24h as "same day"
    if abs(delta_seconds) < 86400:
        return "same day"

    # Otherwise show whole days only (floor)
    days = int(abs(delta_seconds) // 86400)
    sign = "after" if delta_seconds > 0 else "before"
    return f"{days} day{'s' if days != 1 else ''} {sign} chart"


def find_nearby_events(target_dt: datetime, events):
    """Return list of (event_dt, type, event, delta_seconds, exact_time) within type-specific windows."""
    results = []
    for ev in events:
        etype = (ev.get("type") or "").lower()
        if etype in EXCLUDED:
            continue
        window_days = WINDOWS.get(etype)
        if not window_days:
            continue

        ev_dt = _parse_ts(ev["timestamp_ut"])
        exact = _is_exact_time(ev)
        delta_seconds = (ev_dt - target_dt).total_seconds()

        if abs(delta_seconds) <= window_days * 86400:
            results.append((ev_dt, etype, ev, delta_seconds, exact))

    results.sort(key=lambda x: abs(x[3]))  # by |delta|
    return results


def render_event_lookup(target_dt: datetime, events_path="events.jsonl"):
    """
    Streamlit renderer: show major events around a given chart datetime.
    - target_dt must be timezone-aware (UTC preferred)
    - displays the event time (or date), not the chart time
    """
    st.subheader("🌟 Major Events Around This Date")
    events = load_events(events_path)
    matches = find_nearby_events(target_dt, events)

    if not matches:
        st.info("No major events in the nearby window.")
        return

    for ev_dt, etype, ev, delta_seconds, exact in matches:
        # Timestamp string: full UTC time if exact; otherwise date-only
        ts_str = ev_dt.strftime("%B %d, %Y %H:%M UTC") if exact else ev_dt.strftime("%B %d, %Y")

        # Label
        subtype = ev.get("meta", {}).get("subtype", "")
        label = subtype or etype.title()

        # Relative time string
        rel_str = _format_delta(delta_seconds, exact)

        # Render (no degree/sign)
        st.markdown(f"**{ts_str}** – {label}")
        st.markdown(f"*({rel_str})*")
