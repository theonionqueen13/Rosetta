# event_lookup_v2.py

import json
from datetime import datetime
import streamlit as st

@st.cache_data
def load_events(path="events.jsonl"):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]

WINDOWS = {"eclipse": 7, "ingress": 3, "lunation": 1, "station": 2, "perigee": 2, "apogee": 2}
EXCLUDED = {"opposition"}

def _parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))

def _is_exact_time(ev: dict) -> bool:
    meta = ev.get("meta", {})
    if "time_listed" in meta:
        return bool(meta["time_listed"])
    ts = ev.get("timestamp_ut", "")
    return not ts.endswith("T00:00:00Z")

def _format_delta(delta_seconds: float, exact: bool) -> str:
    if exact:
        sign = "after" if delta_seconds > 0 else ("before" if delta_seconds < 0 else "at")
        sec = abs(int(delta_seconds))
        days = sec // 86400; sec %= 86400
        hours = sec // 3600; sec %= 3600
        minutes = sec // 60
        parts = []
        if days:   parts.append(f"{days} day{'s' if days != 1 else ''}")
        if hours:  parts.append(f"{hours} hr{'s' if hours != 1 else ''}")
        if minutes or not parts: parts.append(f"{minutes} min")
        return "at chart time" if sign == "at" else f"{' '.join(parts)} {sign} chart"
    if abs(delta_seconds) < 86400:
        return "same day"
    days = int(abs(delta_seconds) // 86400)
    sign = "after" if delta_seconds > 0 else "before"
    return f"{days} day{'s' if days != 1 else ''} {sign} chart"

def find_nearby_events(target_dt: datetime, events):
    results = []
    if not target_dt:
        return results
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
    results.sort(key=lambda x: abs(x[3]))
    return results

def build_events_html(target_dt: datetime, events_path: str = "events.jsonl", show_no_events: bool = False) -> str:
    if not target_dt:
        return ""
    events = load_events(events_path)
    matches = find_nearby_events(target_dt, events)
    if not matches:
        return "<p><em>No major events in the nearby window.</em></p>" if show_no_events else ""
    lines = []
    for ev_dt, etype, ev, delta_seconds, exact in matches:
        ts_str = ev_dt.strftime("%B %d, %Y %H:%M UTC") if exact else ev_dt.strftime("%B %d, %Y")
        label = ev.get("meta", {}).get("subtype", "") or etype.title()
        rel_str = _format_delta(delta_seconds, exact)
        lines.append(f"<p><strong>{ts_str}</strong> – {label}<br><em>({rel_str})</em></p>")
    return "\n".join(lines)

def update_events_html_state(target_dt: datetime, events_path: str = "events.jsonl", show_no_events: bool = False) -> None:
    """
    ALWAYS blanks first, then tries to compute. If anything fails, it stays blank.
    This guarantees no carry-over if the compute step is skipped or errors.
    """
    # 1) Blank first so stale content is wiped even if we crash/return early
    st.session_state["events_lookup_html"] = ""

    # 2) Compute new HTML (errors won't reintroduce old HTML)
    try:
        html = build_events_html(target_dt, events_path, show_no_events=show_no_events)
    except Exception as e:
        # Optional: record the error if you want to surface it somewhere
        st.session_state["events_lookup_error"] = str(e)
        return

    # 3) Store fresh HTML (can still be "", which is correct for 'no matches')
    st.session_state["events_lookup_html"] = html
