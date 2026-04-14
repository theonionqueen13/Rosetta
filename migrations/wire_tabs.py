"""One-shot migration: replace inline tab content in app.py with build() calls.

Run from project root:
    python -m migrations.wire_tabs
"""
import re, pathlib, sys

APP = pathlib.Path(__file__).resolve().parent.parent / "app.py"

# ---------- replacement blocks keyed by exact header text ----------
REPLACEMENTS = {
    "CIRCUITS TAB": """\
            # ===========================================================
            # CIRCUITS TAB
            # ===========================================================
            with ui.tab_panel(tab_circuits):
                from src.ui.tab_circuits import build as _build_cir
                _cir = _build_cir(
                    state, form,
                    rerender_active_tab=_rerender_active_tab,
                    rerender_circuits_chart_only=_rerender_circuits_chart_only,
                    on_transit_toggle=_on_transit_toggle,
                )
                cir_chart_container = _cir["cir_chart_container"]
                cir_submode_row = _cir["cir_submode_row"]
                _build_circuit_toggles = _cir["build_circuit_toggles"]
""",
    "RULERS TAB": """\
            # ===========================================================
            # RULERS TAB
            # ===========================================================
            with ui.tab_panel(tab_rulers):
                from src.ui.tab_rulers import build as _build_rul
                _rul = _build_rul(state, form)
                _render_rulers_graph = _rul["render_rulers_graph"]
""",
    "CHAT TAB": """\
            # ===========================================================
            # CHAT TAB
            # ===========================================================
            with ui.tab_panel(tab_chat):
                from src.ui.tab_chat import build as _build_chat
                _chat = _build_chat(state, form)
                chat_no_chart_notice = _chat["chat_no_chart_notice"]
""",
    "SPECS TAB  (Step 10)": """\
            # ===========================================================
            # SPECS TAB
            # ===========================================================
            with ui.tab_panel(tab_specs):
                from src.ui.tab_specs import build as _build_specs
                _specs = _build_specs(state, form)
                _refresh_specs_tab = _specs["refresh_specs_tab"]
""",
    "SETTINGS TAB  (Step 10)": """\
            # ===========================================================
            # SETTINGS TAB
            # ===========================================================
            with ui.tab_panel(tab_settings):
                from src.ui.tab_settings import build as _build_set
                _set = _build_set(state, form, rerender_active_tab=_rerender_active_tab)
                _refresh_mode_map = _set["refresh_mode_map"]
""",
    "ADMIN TAB  (Step 10)": """\
            # ===========================================================
            # ADMIN TAB
            # ===========================================================
            if _is_admin:
                with ui.tab_panel(tab_admin):
                    from src.ui.tab_admin import build as _build_adm
                    _build_adm(state, form)
""",
}

# The ordered list of tab header names as they appear top-to-bottom
TAB_ORDER = list(REPLACEMENTS.keys())

# After the last tab, the sentinel marking end-of-tabs
END_SENTINEL = "        # Re-render when tab changes"

def main():
    text = APP.read_text(encoding="utf-8")
    lines = text.split("\n")

    # Find the line index of each tab header
    header_indices: dict[str, int] = {}
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("# ="):
            for tab_name in TAB_ORDER:
                if stripped == f"# {tab_name}":
                    header_indices[tab_name] = i
                    break

    # Find end sentinel
    end_idx = None
    for i, line in enumerate(lines):
        if line.rstrip() == END_SENTINEL:
            end_idx = i
            break

    if end_idx is None:
        print("ERROR: Could not find end sentinel:", repr(END_SENTINEL))
        sys.exit(1)

    missing = [t for t in TAB_ORDER if t not in header_indices]
    if missing:
        print(f"ERROR: Missing tab headers: {missing}")
        sys.exit(1)

    print("Found tab headers at lines:")
    for name, idx in sorted(header_indices.items(), key=lambda x: x[1]):
        print(f"  {name}: L{idx + 1}")
    print(f"  END sentinel: L{end_idx + 1}")

    # Sort tabs by position
    sorted_tabs = sorted(header_indices.items(), key=lambda x: x[1])

    # Build section boundaries: each tab starts at its "# ===" line (2 lines before header)
    # and ends at the line before the next tab's "# ===" line
    sections = []
    for i, (name, header_line) in enumerate(sorted_tabs):
        # Section starts 1 line before header (the "# ======" line)
        start = header_line - 1
        if i + 1 < len(sorted_tabs):
            end = sorted_tabs[i + 1][1] - 2  # line before next "# ====="
        else:
            end = end_idx - 1  # line before end sentinel
        sections.append((name, start, end))

    # Build new file working bottom-to-top
    for name, start, end in reversed(sections):
        replacement = REPLACEMENTS[name]
        print(f"Replacing {name}: L{start + 1}-L{end + 1} ({end - start + 1} lines)")
        # Remove trailing newline from replacement to avoid double spacing
        rep_lines = replacement.rstrip("\n").split("\n")
        lines[start:end + 1] = rep_lines

    new_text = "\n".join(lines)
    APP.write_text(new_text, encoding="utf-8")
    print(f"\nDone! app.py now has {len(new_text.splitlines())} lines (was {len(text.splitlines())})")


if __name__ == "__main__":
    main()
