from __future__ import annotations

from pathlib import Path
import sys
import json
from typing import Any, Dict, List, Tuple

import streamlit as st
import streamlit.components.v1 as components

# Ensure the project root is on sys.path so `src` can be imported.
ROOT = Path(__file__).resolve().parent
sys.path.append(str(ROOT))

from src.core.static_data import SABIAN_SYMBOLS  # noqa: E402

ZODIAC_ORDER = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

WIZARD_TOPICS_MARKDOWN = ROOT / "docs" / "Wizard topics and sub-topics.md"
OUTPUT_JSON = ROOT / "sabian_symbol_wizard_matches.json"


def load_wizard_topics(file_path: Path) -> List[Dict[str, Any]]:
    lines = file_path.read_text(encoding="utf-8").splitlines()
    sections: List[Dict[str, Any]] = []
    current_section: Dict[str, Any] | None = None

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("##"):
            header = line.lstrip("#").strip()
            if header.startswith("**") and header.endswith("**"):
                header = header.strip("*")
            if header.lower().startswith("for each"):
                continue
            current_section = {"header": header, "items": []}
            sections.append(current_section)
        elif line.startswith("*") and current_section is not None:
            item = line.lstrip("*").strip()
            current_section["items"].append(item)

    return sections


def get_ordered_sabian_keys() -> List[Tuple[str, int]]:
    return sorted(
        SABIAN_SYMBOLS.keys(),
        key=lambda item: (ZODIAC_ORDER.index(item[0]), item[1]),
    )


def get_symbol_id(symbol_key: Tuple[str, int]) -> str:
    return f"{symbol_key[0]} {symbol_key[1]}"


def load_saved_data() -> Dict[str, Any]:
    if OUTPUT_JSON.exists():
        try:
            return json.loads(OUTPUT_JSON.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_saved_data(data: Dict[str, Any]) -> None:
    OUTPUT_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def render_read_aloud(text: str) -> None:
    safe_text = json.dumps(text)
    html = """
        <div style='font-family:sans-serif; border:1px solid #ddd; padding:12px; border-radius:8px;'>
            <div style='display:flex; flex-wrap:wrap; gap:8px; margin-bottom:12px;'>
                <button id='play_button' style='padding:8px 14px; font-size:14px;'>Play</button>
                <button id='pause_button' style='padding:8px 14px; font-size:14px;'>Pause</button>
                <button id='stop_button' style='padding:8px 14px; font-size:14px;'>Stop</button>
                <button id='back_button' style='padding:8px 14px; font-size:14px;'><< Prev</button>
                <button id='forward_button' style='padding:8px 14px; font-size:14px;'>Next >></button>
            </div>
            <div style='display:flex; flex-wrap:wrap; gap:16px; align-items:center; margin-bottom:12px;'>
                <label style='font-size:14px;'>Speed: <span id='rate_label'>1.0</span></label>
                <input id='rate_slider' type='range' min='0.5' max='2.0' step='0.1' value='1.0' style='width:180px;' />
                <label style='font-size:14px;'>Volume: <span id='volume_label'>1.0</span></label>
                <input id='volume_slider' type='range' min='0.1' max='1.0' step='0.1' value='1.0' style='width:180px;' />
            </div>
            <div style='font-size:14px; color:#444; margin-bottom:8px;'>Paragraph <span id='paragraph_index'>1</span> / <span id='paragraph_total'>1</span></div>
            <div id='tts_status' style='font-size:13px; color:#555;'>Ready to read aloud.</div>
        </div>
        <script>
            const text = {SAFE_TEXT};
            const paragraphs = text.split(/\\n\\s*\\n/).filter(p => p.trim());
            let currentParagraph = 0;
            let utterance = null;
            const playButton = document.getElementById('play_button');
            const pauseButton = document.getElementById('pause_button');
            const stopButton = document.getElementById('stop_button');
            const backButton = document.getElementById('back_button');
            const forwardButton = document.getElementById('forward_button');
            const rateSlider = document.getElementById('rate_slider');
            const volumeSlider = document.getElementById('volume_slider');
            const rateLabel = document.getElementById('rate_label');
            const volumeLabel = document.getElementById('volume_label');
            const status = document.getElementById('tts_status');
            const paragraphIndex = document.getElementById('paragraph_index');
            const paragraphTotal = document.getElementById('paragraph_total');

            paragraphTotal.textContent = paragraphs.length;
            paragraphIndex.textContent = currentParagraph + 1;

            function createUtterance(textSegment) {
                const u = new SpeechSynthesisUtterance(textSegment);
                u.rate = parseFloat(rateSlider.value);
                u.volume = parseFloat(volumeSlider.value);
                u.onend = () => {
                    if (currentParagraph < paragraphs.length - 1) {
                        currentParagraph += 1;
                        paragraphIndex.textContent = currentParagraph + 1;
                        speakCurrentParagraph();
                    } else {
                        status.textContent = 'Finished reading.';
                    }
                };
                u.onerror = () => {
                    status.textContent = 'Speech error occurred.';
                };
                return u;
            }

            function speakCurrentParagraph() {
                window.speechSynthesis.cancel();
                utterance = createUtterance(paragraphs[currentParagraph]);
                window.speechSynthesis.speak(utterance);
                status.textContent = `Playing paragraph ${currentParagraph + 1} of ${paragraphs.length}`;
            }

            playButton.addEventListener('click', () => {
                if (window.speechSynthesis.speaking && window.speechSynthesis.paused) {
                    window.speechSynthesis.resume();
                    status.textContent = 'Resumed reading.';
                    return;
                }
                if (!window.speechSynthesis.speaking) {
                    speakCurrentParagraph();
                }
            });

            pauseButton.addEventListener('click', () => {
                if (window.speechSynthesis.speaking) {
                    window.speechSynthesis.pause();
                    status.textContent = 'Paused.';
                }
            });

            stopButton.addEventListener('click', () => {
                window.speechSynthesis.cancel();
                currentParagraph = 0;
                paragraphIndex.textContent = currentParagraph + 1;
                status.textContent = 'Stopped.';
            });

            backButton.addEventListener('click', () => {
                if (currentParagraph > 0) {
                    currentParagraph -= 1;
                    paragraphIndex.textContent = currentParagraph + 1;
                    speakCurrentParagraph();
                }
            });

            forwardButton.addEventListener('click', () => {
                if (currentParagraph < paragraphs.length - 1) {
                    currentParagraph += 1;
                    paragraphIndex.textContent = currentParagraph + 1;
                    speakCurrentParagraph();
                }
            });

            rateSlider.addEventListener('input', () => {
                rateLabel.textContent = rateSlider.value;
            });
            volumeSlider.addEventListener('input', () => {
                volumeLabel.textContent = volumeSlider.value;
            });
        </script>
    """
    html = html.replace("{SAFE_TEXT}", safe_text)
    components.html(html, height=240)


def get_topic_key(symbol_id: str, topic: str) -> str:
    return f"topic__{symbol_id}__{topic}"


def get_subtopic_key(symbol_id: str, subtopic: str) -> str:
    return f"subtopic__{symbol_id}__{subtopic}"


def initialize_state(symbol_keys: List[Tuple[str, int]]) -> None:
    if "sabian_index" not in st.session_state:
        st.session_state.sabian_index = 0
    if "save_clicked" not in st.session_state:
        st.session_state.save_clicked = False
    if "saved_symbols" not in st.session_state:
        st.session_state.saved_symbols = load_saved_data()
    if "selected_sign" not in st.session_state:
        st.session_state.selected_sign = ZODIAC_ORDER[0]
    if "selected_degree" not in st.session_state:
        st.session_state.selected_degree = 1


def main() -> None:
    st.set_page_config(
        page_title="Sabian Symbol Wizard Matcher",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    global WIZARD_TOPICS
    WIZARD_TOPICS = load_wizard_topics(WIZARD_TOPICS_MARKDOWN)
    symbol_keys = get_ordered_sabian_keys()
    initialize_state(symbol_keys)

    st.title("Sabian Symbol Matcher")
    st.markdown("Use the navigation buttons to browse symbols. Wizard topics and sub-topics are available in the sidebar for independent scrolling.")

    with st.container():
        st.subheader("Sabian Symbol Viewer")
        nav_col1, nav_col2, nav_col3, nav_col4 = st.columns([1, 1, 1, 1])

        current_key = symbol_keys[st.session_state.sabian_index]
        current_sign, current_degree = current_key
        st.session_state.selected_sign = current_sign
        st.session_state.selected_degree = current_degree

        if nav_col1.button("Previous"):
            st.session_state.sabian_index = max(0, st.session_state.sabian_index - 1)
            current_key = symbol_keys[st.session_state.sabian_index]
            st.session_state.selected_sign, st.session_state.selected_degree = current_key
            st.session_state.save_clicked = False
        if nav_col2.button("Next"):
            st.session_state.sabian_index = min(len(symbol_keys) - 1, st.session_state.sabian_index + 1)
            current_key = symbol_keys[st.session_state.sabian_index]
            st.session_state.selected_sign, st.session_state.selected_degree = current_key
            st.session_state.save_clicked = False

        selected_sign = nav_col3.selectbox(
            "Sign",
            ZODIAC_ORDER,
            key="selected_sign",
        )
        selected_degree = nav_col4.selectbox(
            "Degree",
            list(range(1, 31)),
            key="selected_degree",
        )

        selected_key = (selected_sign, selected_degree)
        if selected_key in symbol_keys and selected_key != current_key:
            st.session_state.sabian_index = symbol_keys.index(selected_key)
            current_key = selected_key
            st.session_state.save_clicked = False

        key = current_key
        symbol_data = SABIAN_SYMBOLS[key]

        sign, degree = key
        st.markdown(f"### {sign} {degree}")
        st.markdown(f"**Sabian Symbol:** {symbol_data['sabian_symbol']}")
        st.markdown("---")
        st.write(symbol_data.get("long_meaning", ""))

        read_text = f"{sign} {degree}. {symbol_data['sabian_symbol']}. {symbol_data.get('long_meaning', '')}"
        render_read_aloud(read_text)

        st.caption(f"Symbol {st.session_state.sabian_index + 1} of {len(symbol_keys)}")

    symbol_id = get_symbol_id(key)
    saved_entry = st.session_state.saved_symbols.get(symbol_id, {})
    saved_topics = set(saved_entry.get("wizard_topics", symbol_data.get("wizard_topics", [])))
    saved_subtopics = set(saved_entry.get("wizard_subtopics", symbol_data.get("wizard_subtopics", [])))

    with st.sidebar:
        st.subheader("Wizard Topics & Sub-Topics")
        st.markdown("Scroll this sidebar independently while you browse symbols.")

        for section in WIZARD_TOPICS:
            topic_key = get_topic_key(symbol_id, section["header"])
            default_topic = section["header"] in saved_topics
            if topic_key not in st.session_state:
                st.session_state[topic_key] = default_topic

            header_col, checkbox_col = st.columns([0.85, 0.15])
            header_col.markdown(
                f"<div style='font-weight:bold; font-size:16px; margin-top:12px; margin-bottom:4px;'>{section['header']}</div>",
                unsafe_allow_html=True,
            )
            checkbox_col.checkbox("", key=topic_key)

            for item in section["items"]:
                subtopic_key = get_subtopic_key(symbol_id, item)
                default_subtopic = item in saved_subtopics
                if subtopic_key not in st.session_state:
                    st.session_state[subtopic_key] = default_subtopic
                subtopic_col1, subtopic_col2 = st.columns([0.1, 0.9])
                subtopic_col2.checkbox(item, key=subtopic_key)

        st.markdown("---")
        if st.button("Save"):
            wizard_topics = [
                section["header"]
                for section in WIZARD_TOPICS
                if st.session_state[get_topic_key(symbol_id, section["header"])]
            ]
            wizard_subtopics = [
                item
                for section in WIZARD_TOPICS
                for item in section["items"]
                if st.session_state[get_subtopic_key(symbol_id, item)]
            ]

            st.session_state.saved_symbols[symbol_id] = {
                "sign": sign,
                "degree": degree,
                "sabian_symbol": symbol_data["sabian_symbol"],
                "short_meaning": symbol_data["short_meaning"],
                "long_meaning": symbol_data.get("long_meaning", ""),
                "wizard_topics": wizard_topics,
                "wizard_subtopics": wizard_subtopics,
            }
            save_saved_data(st.session_state.saved_symbols)
            st.session_state.save_clicked = True
            st.success(f"Saved {symbol_id} to {OUTPUT_JSON.name}.")

        if st.session_state.save_clicked:
            st.info("Manual selections are ready for the next integration step.")

        st.markdown("---")
        st.write(f"Saved symbols: {len(st.session_state.saved_symbols)}")
        st.download_button(
            label="Download saved JSON",
            data=json.dumps(st.session_state.saved_symbols, indent=2, ensure_ascii=False),
            file_name=OUTPUT_JSON.name,
            mime="application/json",
        )


if __name__ == "__main__":
    main()
