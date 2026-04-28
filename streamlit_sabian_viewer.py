from __future__ import annotations

from pathlib import Path
import sys
import json
from typing import List, Tuple

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


def get_ordered_sabian_keys() -> List[Tuple[str, int]]:
    return sorted(
        SABIAN_SYMBOLS.keys(),
        key=lambda item: (ZODIAC_ORDER.index(item[0]), item[1]),
    )


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


def get_five_fold_path(symbol_key: Tuple[str, int]) -> List[Tuple[str, int]]:
    """Get the five-fold path (5 consecutive symbols in the same sign) for a given symbol."""
    sign, degree = symbol_key
    # Determine which group of 5 this degree belongs to (1-5, 6-10, 11-15, etc.)
    group = (degree - 1) // 5
    start_degree = group * 5 + 1
    # Return the 5 symbols in this path
    return [(sign, i) for i in range(start_degree, start_degree + 5)]


def initialize_state(symbol_keys: List[Tuple[str, int]]) -> None:
    if "sabian_index" not in st.session_state:
        st.session_state.sabian_index = 0
    if "selected_sign" not in st.session_state:
        st.session_state.selected_sign = ZODIAC_ORDER[0]
    if "selected_degree" not in st.session_state:
        st.session_state.selected_degree = 1


def main() -> None:
    st.set_page_config(
        page_title="Sabian Symbol Wizard Matcher",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    symbol_keys = get_ordered_sabian_keys()
    initialize_state(symbol_keys)

    with st.container():
        nav_col1, nav_col2, nav_col3, nav_col4 = st.columns([1, 1, 1, 1])

        current_key = symbol_keys[st.session_state.sabian_index]
        current_sign, current_degree = current_key

        if nav_col1.button("Previous"):
            st.session_state.sabian_index = max(0, st.session_state.sabian_index - 1)
            current_key = symbol_keys[st.session_state.sabian_index]
            st.session_state.selected_sign, st.session_state.selected_degree = current_key
        if nav_col2.button("Next"):
            st.session_state.sabian_index = min(len(symbol_keys) - 1, st.session_state.sabian_index + 1)
            current_key = symbol_keys[st.session_state.sabian_index]
            st.session_state.selected_sign, st.session_state.selected_degree = current_key

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

        key = current_key
        symbol_data = SABIAN_SYMBOLS[key]

        sign, degree = key
        st.markdown(f"### {sign} {degree}")
        st.markdown(f"**Sabian Symbol:** {symbol_data['sabian_symbol']}")
        st.markdown("---")
        st.write(symbol_data.get("long_meaning", ""))

        st.markdown(f"### {sign} {degree}: {symbol_data['sabian_symbol']}")

        read_text = f"{sign} {degree}. {symbol_data['sabian_symbol']}. {symbol_data.get('long_meaning', '')}"
        render_read_aloud(read_text)

        st.caption(f"Symbol {st.session_state.sabian_index + 1} of {len(symbol_keys)}")

    with st.sidebar:
        st.markdown("### Five-Fold Path")
        five_fold_path = get_five_fold_path(key)
        for path_symbol_key in five_fold_path:
            path_sign, path_degree = path_symbol_key
            if path_symbol_key in SABIAN_SYMBOLS:
                path_symbol_data = SABIAN_SYMBOLS[path_symbol_key]
                title = f"{path_sign} {path_degree}: {path_symbol_data['sabian_symbol']}"
                short_meaning = path_symbol_data.get('short_meaning', '')

                if path_symbol_key == key:
                    # Highlight current symbol
                    st.markdown(f"**{title}**")
                    st.markdown(f"**{short_meaning}**")
                else:
                    st.markdown(title)
                    st.markdown(short_meaning)
                st.divider()

if __name__ == "__main__":
    main()
