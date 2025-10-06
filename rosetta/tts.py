# rosetta/tts.py
def tts_controls(text: str, key: str, label: str = "🔊 Read"):
    import json
    import uuid
    from streamlit.components.v1 import html as st_html

    uid = f"tts-{key}-{uuid.uuid4().hex[:8]}"
    payload = json.dumps(text or "")

    st_html(
        f"""
<div id="{uid}" style="display:flex;flex-wrap:wrap;gap:.5rem;align-items:center;margin:.25rem 0 .75rem;">
  <!-- main controls -->
  <button id="{uid}-play">{label}</button>
  <button id="{uid}-pause">Pause</button>
  <button id="{uid}-resume">Resume</button>
  <button id="{uid}-stop">Stop</button>

  <!-- speed -->
  <span style="margin-left:.5rem;">Speed:</span>
  <button id="{uid}-rate-down" title="Slower">–</button>
  <span id="{uid}-rate" style="min-width:3ch;text-align:center;">1.0</span>
  <button id="{uid}-rate-up" title="Faster">+</button>

  <!-- paragraph jump -->
  <span style="margin-left:.5rem;">Jump to ¶:</span>
  <select id="{uid}-jump" style="max-width:22rem;"></select>
  <button id="{uid}-jump-go">Go</button>
</div>

<script>
(function() {{
  const id = "{uid}";
  const synth = window.speechSynthesis;
  const fullText = {payload};

  // --- split into paragraphs, then chunk each paragraph by sentence/length ---
  const paragraphs = fullText.split(/\\n\\s*\\n/).map(p => p.trim()).filter(p => p.length > 0);

  function chunkBySentence(t, max=1800) {{
    const out = [];
    let s = 0;
    while (s < t.length) {{
      let e = Math.min(s + max, t.length);
      const slice = t.slice(s, e);
      let cut = Math.max(slice.lastIndexOf(". "), slice.lastIndexOf("! "), slice.lastIndexOf("? "));
      if (cut > 200) e = s + cut + 1;  // keep sentences intact when possible
      out.push(t.slice(s, e));
      s = e;
    }}
    return out;
  }}

  const partsByPara = paragraphs.map(p => chunkBySentence(p));
  let pIdx = 0;   // paragraph index
  let cIdx = 0;   // chunk index within paragraph
  let u = null;   // current utterance
  let rate = 1.0; // 0.6 .. 1.6

  // --- populate paragraph dropdown with first few words for context ---
  const jumpSel = document.getElementById(id+"-jump");
  if (paragraphs.length === 0) {{
    const opt = document.createElement("option");
    opt.textContent = "(no paragraphs)";
    opt.value = "0";
    jumpSel.appendChild(opt);
  }} else {{
    paragraphs.forEach((p, i) => {{
      const label = (i+1) + ": " + p.replace(/\\s+/g, " ").split(" ").slice(0, 6).join(" ");
      const opt = document.createElement("option");
      opt.value = String(i);
      opt.textContent = label + (p.split(" ").length > 6 ? "…" : "");
      jumpSel.appendChild(opt);
    }});
  }}

  function speakNext() {{
    // done?
    if (pIdx >= partsByPara.length) return;

    // paragraph exhausted? advance paragraph
    if (cIdx >= partsByPara[pIdx].length) {{
      pIdx++; cIdx = 0;
      if (pIdx >= partsByPara.length) return;
    }}

    const part = partsByPara[pIdx][cIdx];
    u = new SpeechSynthesisUtterance(part);
    u.rate = rate;
    u.pitch = 1.0;
    u.onend = () => {{
      cIdx++;
      speakNext();
    }};
    synth.speak(u);
  }}

  function stopAll() {{
    try {{ synth.cancel(); }} catch (e) {{}}
  }}

  function playFrom(startPara=0) {{
    stopAll();
    pIdx = Math.max(0, Math.min(startPara, partsByPara.length - 1));
    cIdx = 0;
    speakNext();
  }}

  // --- wire controls ---
  document.getElementById(id+"-play").onclick = () => playFrom(0);
  document.getElementById(id+"-pause").onclick = () => synth.pause();
  document.getElementById(id+"-resume").onclick = () => synth.resume();
  document.getElementById(id+"-stop").onclick = stopAll;

  // speed buttons
  const rateSpan = document.getElementById(id+"-rate");
  function setRate(r) {{
    rate = Math.max(0.6, Math.min(1.6, Math.round(r*10)/10));
    rateSpan.textContent = rate.toFixed(1);
  }}
  document.getElementById(id+"-rate-down").onclick = () => setRate(rate - 0.1);
  document.getElementById(id+"-rate-up").onclick = () => setRate(rate + 0.1);

  // jump-to paragraph
  document.getElementById(id+"-jump-go").onclick = () => {{
    const to = parseInt(jumpSel.value || "0", 10);
    playFrom(to);
  }};

  // Safari voices quirk
  if (synth && synth.getVoices().length === 0) {{
    synth.onvoiceschanged = () => {{}};
  }}
}})();
</script>
""",
        height=110,
    )
