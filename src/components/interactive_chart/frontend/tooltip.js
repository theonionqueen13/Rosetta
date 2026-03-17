/**
 * RosettaTooltip — Hover tooltips and click events for the interactive chart.
 *
 * Shows rich metadata panels for planets, aspects, and houses on hover.
 * Sends click events back to Streamlit via Streamlit.setComponentValue().
 */
const RosettaTooltip = (() => {
    let _data = null; // chart data reference
    let _tooltip = null;
    let _objectMap = {}; // name → object data
    let _aspectList = []; // flat list of aspect data
    let _houseMap = {}; // number → house data

    // -----------------------------------------------------------------------
    // Build lookup maps
    // -----------------------------------------------------------------------
    function _buildMaps(data) {
        _data = data;
        _objectMap = {};
        _aspectList = data.aspects || [];
        _houseMap = {};

        (data.objects || []).forEach((o) => {
            _objectMap[o.name] = o;
        });
        (data.houses || []).forEach((h) => {
            _houseMap[String(h.number)] = h;
        });
    }

    // -----------------------------------------------------------------------
    // Format helpers
    // -----------------------------------------------------------------------
    function _fmt(val, digits) {
        if (val === null || val === undefined || val === "") return "—";
        const n = Number(val);
        if (isNaN(n)) return String(val);
        return n.toFixed(digits !== undefined ? digits : 2);
    }

    function _badge(label, value, cls) {
        cls = cls || "";
        return `<span class="tt-badge ${cls}">${label}: <strong>${value}</strong></span>`;
    }

    function _dignityLabel(ed) {
        if (!ed) return "—";
        if (ed.domicile) return "Domicile ✦";
        if (ed.exaltation) return "Exaltation ✦";
        if (ed.triplicity) return "Triplicity";
        if (ed.term) return "Term";
        if (ed.face) return "Face";
        if (ed.detriment) return "Detriment ✘";
        if (ed.fall) return "Fall ✘";
        if (ed.peregrine) return "Peregrine";
        return ed.primary_dignity || "—";
    }

    // -----------------------------------------------------------------------
    // Tooltip content builders
    // -----------------------------------------------------------------------
    function _objectTooltip(obj) {
        if (!obj) return "";
        const ps = obj.planetary_state || {};
        const cn = obj.circuit_node || {};
        const ed = ps.essential_dignity || {};

        let html = `<div class="tt-header">${obj.glyph} <strong>${obj.name}</strong></div>`;
        html += `<div class="tt-row">${obj.sign || "?"} · House ${obj.house || "?"} · ${obj.degree_in_sign}°${obj.minute_in_sign ? obj.minute_in_sign + "'" : ""}</div>`;

        if (obj.retrograde) html += `<div class="tt-row tt-warn">☿ Retrograde</div>`;
        if (obj.station) html += `<div class="tt-row tt-warn">${obj.station}</div>`;

        // Dignity
        html += `<div class="tt-section">Essential Dignity</div>`;
        html += `<div class="tt-row">${_dignityLabel(ed)}</div>`;

        // Power metrics
        if (ps.power_index !== undefined) {
            html += `<div class="tt-section">Strength</div>`;
            html += `<div class="tt-badges">`;
            html += _badge("Power", _fmt(ps.power_index));
            html += _badge("Authority", _fmt(ps.raw_authority));
            html += _badge("Quality", _fmt(ps.quality_index));
            html += _badge("Potency", _fmt(ps.potency_score));
            html += `</div>`;

            if (ps.motion_label) {
                html += `<div class="tt-row">Motion: ${ps.motion_label} (${_fmt(ps.motion_score)})</div>`;
            }
            if (ps.solar_proximity_label) {
                html += `<div class="tt-row">Solar: ${ps.solar_proximity_label} (${_fmt(ps.solar_proximity_score)})</div>`;
            }
        }

        // Circuit node
        if (cn.effective_power !== undefined) {
            html += `<div class="tt-section">Circuit</div>`;
            html += `<div class="tt-badges">`;
            html += _badge("Effective", _fmt(cn.effective_power));
            html += _badge("Received", _fmt(cn.received_power));
            html += _badge("Emitted", _fmt(cn.emitted_power));
            html += _badge("Friction", _fmt(cn.friction_load), "tt-friction");
            html += `</div>`;
            const roles = [];
            if (cn.is_source) roles.push("Source");
            if (cn.is_sink) roles.push("Sink");
            if (cn.is_mutual_reception) roles.push("Mutual Reception");
            if (roles.length) html += `<div class="tt-row">Role: ${roles.join(", ")}</div>`;
        }

        // Meaning
        if (obj.meaning_short) {
            html += `<div class="tt-section">Meaning</div>`;
            html += `<div class="tt-meaning">${obj.meaning_short}</div>`;
        }

        if (obj.keywords && obj.keywords.length) {
            html += `<div class="tt-keywords">${obj.keywords.slice(0, 8).join(" · ")}</div>`;
        }

        return html;
    }

    function _aspectTooltip(aspData) {
        if (!aspData) return "";

        let html = `<div class="tt-header"><strong>${aspData.obj_a}</strong> ${aspData.aspect} <strong>${aspData.obj_b}</strong></div>`;
        html += `<div class="tt-row">${aspData.angle}° · Orb ${aspData.orb}°${aspData.is_approx ? " (approx)" : ""}</div>`;
        html += `<div class="tt-row">${aspData.is_major ? "Major" : "Minor"} aspect</div>`;

        // Circuit edge data
        if (aspData.conductance !== undefined) {
            html += `<div class="tt-section">Circuit</div>`;
            html += `<div class="tt-badges">`;
            html += _badge("Conductance", _fmt(aspData.conductance));
            html += _badge("Transmitted", _fmt(aspData.transmitted_power));
            html += _badge("Friction", _fmt(aspData.friction_heat), "tt-friction");
            html += `</div>`;
            if (aspData.flow_direction) {
                html += `<div class="tt-row">Flow: ${aspData.flow_direction}</div>`;
            }
            if (aspData.is_arc_hazard) {
                html += `<div class="tt-row tt-warn">⚠ Arc Hazard (Quincunx)</div>`;
                if (aspData.is_rerouted && aspData.reroute_path && aspData.reroute_path.length) {
                    html += `<div class="tt-row">Reroute: ${aspData.reroute_path.join(" → ")}</div>`;
                } else if (aspData.is_open_arc) {
                    html += `<div class="tt-row tt-warn">Open arc — no reroute found</div>`;
                }
            }
        }

        return html;
    }

    function _houseTooltip(house) {
        if (!house) return "";
        let html = `<div class="tt-header">House <strong>${house.number}</strong></div>`;
        html += `<div class="tt-row">Cusp: ${_fmt(house.cusp_degree, 1)}° · ${house.sign} ${house.degree_in_sign}°</div>`;
        if (house.life_domain) html += `<div class="tt-row">${house.life_domain}</div>`;
        if (house.short_meaning) html += `<div class="tt-meaning">${house.short_meaning}</div>`;
        return html;
    }

    function _signTooltip(signName) {
        const signs = (_data && _data.signs) || [];
        const sign = signs.find((s) => s.name === signName);
        if (!sign) return "";
        let html = `<div class="tt-header">${sign.glyph} <strong>${sign.name}</strong></div>`;
        html += `<div class="tt-row">Element: ${sign.element}</div>`;
        return html;
    }

    // -----------------------------------------------------------------------
    // Show / hide tooltip
    // -----------------------------------------------------------------------
    function _show(evt, html) {
        if (!_tooltip) return;

        // Set content first so we can measure real dimensions
        _tooltip.innerHTML = html;
        _tooltip.style.visibility = "hidden";
        _tooltip.style.left = "0px";
        _tooltip.style.top = "0px";
        _tooltip.classList.remove("hidden");

        // Measure after layout (offsetWidth/offsetHeight force reflow)
        const tw = _tooltip.offsetWidth;
        const th = _tooltip.offsetHeight;
        const pad = 14;
        const vw = window.innerWidth || document.documentElement.clientWidth;
        const vh = window.innerHeight || document.documentElement.clientHeight;

        // Use clientX/clientY — works correctly with position:fixed
        let x = evt.clientX + pad;
        let y = evt.clientY + pad;

        // Flip left if overflows right edge
        if (x + tw > vw - pad) x = evt.clientX - tw - pad;
        // Flip up if overflows bottom (most common clip case)
        if (y + th > vh - pad) y = evt.clientY - th - pad;

        // Hard clamp so it never goes off-screen
        x = Math.max(pad, Math.min(x, vw - tw - pad));
        y = Math.max(pad, Math.min(y, vh - th - pad));

        _tooltip.style.left = x + "px";
        _tooltip.style.top = y + "px";
        _tooltip.style.visibility = "visible";
    }

    function _hide() {
        if (!_tooltip) return;
        _tooltip.classList.add("hidden");
    }

    // Reposition tooltip on mousemove — called from every handler
    function _move(evt) {
        if (!_tooltip || _tooltip.classList.contains("hidden")) return;
        const tw = _tooltip.offsetWidth;
        const th = _tooltip.offsetHeight;
        const pad = 14;
        const vw = window.innerWidth || document.documentElement.clientWidth;
        const vh = window.innerHeight || document.documentElement.clientHeight;
        let x = evt.clientX + pad;
        let y = evt.clientY + pad;
        if (x + tw > vw - pad) x = evt.clientX - tw - pad;
        if (y + th > vh - pad) y = evt.clientY - th - pad;
        x = Math.max(pad, Math.min(x, vw - tw - pad));
        y = Math.max(pad, Math.min(y, vh - th - pad));
        _tooltip.style.left = x + "px";
        _tooltip.style.top = y + "px";
    }

    // -----------------------------------------------------------------------
    // Wire events
    // -----------------------------------------------------------------------
    function wire(svg, data) {
        _buildMaps(data);
        _tooltip = document.getElementById("tooltip");

        // --- Planet hover/click ---
        svg.selectAll(".planet-glyph, .planet-degree, .planet-hitarea").on("mouseenter", function (evt) {
            const name = this.getAttribute("data-object");
            const obj = _objectMap[name];
            if (obj) _show(evt, _objectTooltip(obj));
        }).on("mousemove", function (evt) { _move(evt); })
            .on("mouseleave", _hide).on("click", function () {
                const name = this.getAttribute("data-object");
                Streamlit.setComponentValue({
                    type: "click",
                    element_type: "object",
                    element: name,
                    data: _objectMap[name] || {},
                });
            });

        // --- Aspect hover/click ---
        svg.selectAll(".aspect-line").on("mouseenter", function (evt) {
            const a = this.getAttribute("data-obj-a");
            const b = this.getAttribute("data-obj-b");
            const asp = this.getAttribute("data-aspect");
            const aspData = _aspectList.find(
                (e) =>
                    (e.obj_a === a && e.obj_b === b && e.aspect === asp) ||
                    (e.obj_a === b && e.obj_b === a && e.aspect === asp)
            );
            if (aspData) _show(evt, _aspectTooltip(aspData));

            // Thicken on hover
            d3.select(this).attr("stroke-width", parseFloat(d3.select(this).attr("stroke-width")) + 2);
        }).on("mousemove", function (evt) { _move(evt); })
            .on("mouseleave", function () {
                _hide();
                // Restore width
                const isMajor = this.getAttribute("data-is-major") === "true";
                const asp = (this.getAttribute("data-aspect") || "").toLowerCase();
                let lw = isMajor ? 2 : 1;
                if (asp === "quincunx" || asp === "sesquisquare") lw = 1;
                d3.select(this).attr("stroke-width", lw);
            }).on("click", function () {
                const a = this.getAttribute("data-obj-a");
                const b = this.getAttribute("data-obj-b");
                const asp = this.getAttribute("data-aspect");
                Streamlit.setComponentValue({
                    type: "click",
                    element_type: "aspect",
                    element: `${a}-${b}-${asp}`,
                    data: { obj_a: a, obj_b: b, aspect: asp },
                });
            });

        // --- House hover/click ---
        svg.selectAll(".house-cusp, .house-number").on("mouseenter", function (evt) {
            const h = this.getAttribute("data-house");
            const house = _houseMap[h];
            if (house) _show(evt, _houseTooltip(house));
        }).on("mousemove", function (evt) { _move(evt); })
            .on("mouseleave", _hide).on("click", function () {
                const h = this.getAttribute("data-house");
                Streamlit.setComponentValue({
                    type: "click",
                    element_type: "house",
                    element: h,
                    data: _houseMap[h] || {},
                });
            });

        // --- Zodiac sign hover ---
        svg.selectAll(".zodiac-band, .zodiac-glyph").on("mouseenter", function (evt) {
            const name = this.getAttribute("data-sign");
            if (name) _show(evt, _signTooltip(name));
        }).on("mousemove", function (evt) { _move(evt); })
            .on("mouseleave", _hide);
    }

    return { wire };
})();
