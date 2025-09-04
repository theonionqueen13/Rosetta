from rosetta.lookup import GLYPHS, OBJECT_MEANINGS
from rosetta.helpers import calculate_oob_status

def format_planet_profile(row):
    """Format planet information for display (single-spaced, skip empty values)."""
    name = row["Object"]
    meaning = OBJECT_MEANINGS.get(name, "")
    dignity = row.get("Dignity", "")
    retro = row.get("Retrograde", "")
    sabian = row.get("Sabian Symbol", "")
    fixed_star = row.get("Fixed Star Conjunction", "")

    # Safe OOB calculation
    declination = row.get("Declination", "")
    try:
        oob = calculate_oob_status(declination)
    except Exception:
        oob = None

    sign = row.get("Sign", "")
    lon = row.get("Longitude", "")

    # --- build profile lines ---
    lines = []

    # header (glyph + name)
    header = f"{GLYPHS.get(name, '')} {name}".strip()
    if str(dignity).strip().lower() not in ["none", "nan", ""]:
        header += f" ({dignity})"
    if str(retro).strip().lower() == "rx":
        header += " Rx"
    lines.append(header)

    # meaning
    if meaning:
        lines.append(meaning)

    # sabian symbol
    if sabian and str(sabian).strip().lower() not in ["none", "nan", ""]:
        lines.append(f"“{sabian}”")

    # position line
    if sign and lon:
        pos_line = f"{sign} {lon}"
        if str(retro).strip().lower() == "rx":
            pos_line += " Rx"
        lines.append(pos_line)

    # details (skip empty)
    for label, value in [
        ("Out Of Bounds", oob),
        ("Conjunct Fixed Star", fixed_star),
        ("Speed", row.get("Speed", "")),
        ("Latitude", row.get("Latitude", "")),
        ("Declination", declination),
    ]:
        if value and str(value).strip().lower() not in ["none", "nan", "", "no", "no data"]:
            if label == "Out Of Bounds" and value == "No":
                # Skip "No" to save space
                continue
            lines.append(f"{label}: {value}")

    # join lines with <div> single spacing
    html = "".join(f"<div>{line}</div>" for line in lines)
    return html
