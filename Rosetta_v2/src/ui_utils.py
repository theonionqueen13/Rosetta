# src/ui_utils.py

import base64
from pathlib import Path
import streamlit as st
from typing import Optional

COMPASS_KEY = "ui_compass_overlay"

def apply_custom_css() -> None:
    """
    Applies custom CSS for expanders and sidebar profile styling.
    (This replaces two large st.markdown blocks in the original file).
    """
    st.markdown("""
<style>
/* --- Custom Expander Styling --- */
/* Full expander container */
[data-testid="stExpander"] {
    background-color: #333333 !important; /* dark gray */
    color: white !important;
    background-image: none !important;
    border-radius: 10px !important;  /* rounded corners */
    overflow: hidden !important;      /* prevents header/body corners showing square */
}

/* Expander header */
[data-testid="stExpander"] > summary {
    background-color: #333333 !important;
    color: white !important;
    border-radius: 10px !important;  /* same rounding */
}

/* Inner content area */
[data-testid="stExpander"] .st-expander-content {
    background-color: #333333 !important;
    color: white !important;
    border-radius: 0 0 10px 10px !important; /* rounded bottom corners */
}

/* --- Sidebar Profile Styling --- */
/* Wrap each profile in .profile-card when rendering below */
.profile-card {
  line-height: 1.05;               /* keeps your single-spacing feel */
  white-space: pre-wrap;            /* preserves your <br> line breaks */
  border-bottom: 1px solid rgba(255,255,255,0.18);  /* thin divider */
  padding-bottom: 10px;
  margin-bottom: 10px;
}
.profile-card:last-child { border-bottom: none; }
</style>
""", unsafe_allow_html=True)


def _encode_image_base64(path_str: str) -> str:
    """Read a local image and return a base64 data URI (jpeg/png/webp)."""
    p = Path(path_str)
    if not p.exists():
        # Prefer a hard fail so you notice wrong paths fast.
        raise FileNotFoundError(f"Background image not found: {p.resolve()}")
    ext = p.suffix.lower()
    if ext == ".png":
        mime = "image/png"
    elif ext == ".webp":
        mime = "image/webp"
    else:
        mime = "image/jpeg"  # default to jpeg for jpg/jpeg/others
    b64 = base64.b64encode(p.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{b64}"

def apply_background_base64(image_path: str, overlay: float = 0.40) -> None:
    """
    Page-wide background using a LOCAL image (base64) + adjustable dark overlay.
    """
    overlay = max(0.0, min(1.0, float(overlay)))
    data_uri = _encode_image_base64(image_path)

    st.markdown(
        f"""
        <style>
        /* Main app view container background */
        [data-testid="stAppViewContainer"] {{
            background-image:
                linear-gradient(rgba(0,0,0,{overlay}), rgba(0,0,0,{overlay})),
                url('{data_uri}');
            background-size: cover;
            background-position: center center;
            background-repeat: no-repeat;
            background-attachment: fixed;
        }}

        /* Let the background show under the main content */
        .block-container {{
            background: transparent;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

def set_background_for_theme(
    *,
    light_image_path: str,
    dark_image_path: str,
    light_overlay: float = 0.25,
    dark_overlay: float = 0.45,
    dark_mode: bool | None = None,
) -> bool:
    """
    Chooses the background based on dark_mode and applies it.
    Returns the resolved dark_mode.
    """
    # If caller didn't pass dark_mode, try to infer from session or theme:
    if dark_mode is None:
        dark_mode = bool(st.session_state.get("ui_dark_mode", False))
        try:
            # Try Streamlit theme (light/dark)
            base_theme = st.get_option("theme.base")
            if base_theme in ("light", "dark"):
                dark_mode = (base_theme == "dark")
        except Exception:
            pass

    if dark_mode:
        apply_background_base64(dark_image_path, dark_overlay)
    else:
        apply_background_base64(light_image_path, light_overlay)

    return dark_mode