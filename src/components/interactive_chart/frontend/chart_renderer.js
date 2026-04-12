/**
 * RosettaChart — D3.js/SVG interactive astrological chart renderer
 *
 * Faithfully reproduces the geometry from drawing_v2.py:
 *   - Polar layout with Ascendant pinned to 9 o'clock (left)
 *   - Zodiac band (1.45–1.58), planet labels (1.35), degree ticks (1.0),
 *     house cusps (0→1.45), aspect chords at r=1.0
 *   - Same cluster fan-out algorithm for overlapping planet labels
 *   - Gradient aspect lines with luminary/minor-body color logic
 *
 * All chart elements get data-* attributes for hover/click interactivity.
 */
const RosettaChart = (() => {
    // -----------------------------------------------------------------------
    // Geometry constants (matching drawing_v2.py)
    // -----------------------------------------------------------------------
    const RLIM = 1.60;
    const R_ZODIAC_INNER = 1.45;
    const R_ZODIAC_OUTER = 1.58;
    const R_ZODIAC_DIV_INNER = 1.457;
    const R_ZODIAC_DIV_OUTER = 1.573;
    const R_ZODIAC_GLYPH = 1.50;
    const R_DEGREE_CIRCLE = 1.0;
    const R_PLANET_GLYPH = 1.35;
    const R_PLANET_DEGREE = 1.27;
    const R_HOUSE_CUSP = 1.45;
    const R_HOUSE_LABEL = 0.32;
    const R_ASPECT = 1.0;

    // Cluster fan-out constants (matching draw_planet_labels)
    const CLUSTER_THRESHOLD = 3;
    const MIN_SPACING = 7;
    const CLUSTER_SPREAD = 3;

    // Luminaries and planets (for gradient endpoint logic)
    const LUMINARIES_AND_PLANETS = new Set([
        "sun", "moon", "mercury", "venus", "mars",
        "jupiter", "saturn", "uranus", "neptune", "pluto",
    ]);

    // -----------------------------------------------------------------------
    // Coordinate conversion (matching drawing_primitives.deg_to_rad)
    // -----------------------------------------------------------------------
    function degToRad(deg, ascShift) {
        // Identical to drawing_primitives.deg_to_rad but WITHOUT the +90 offset.
        // The +90 in the Python version aligns theta=0 to "North" in matplotlib's
        // CW polar system. In SVG (y-down, same CW visual result), no offset is
        // needed: AC longitude == ascShift → adjusted=180 → angle=180° = π
        // → x = -r, y = 0 → left (9 o'clock) ✓   MC ≈ asc-90 → angle=270° → top ✓
        const adjusted = ((deg - ascShift + 180) % 360 + 360) % 360;
        const angle = ((360 - adjusted) % 360 + 360) % 360;
        return (angle * Math.PI) / 180;
    }

    function polarToCartesian(r, thetaRad) {
        return [r * Math.cos(thetaRad), r * Math.sin(thetaRad)];
    }

    function isLuminaryOrPlanet(name) {
        return LUMINARIES_AND_PLANETS.has((name || "").toLowerCase());
    }

    // -----------------------------------------------------------------------
    // Color utilities
    // -----------------------------------------------------------------------
    function parseColor(c) {
        // Create a temporary element to leverage browser CSS parsing
        const el = document.createElement("div");
        el.style.color = c;
        document.body.appendChild(el);
        const computed = getComputedStyle(el).color;
        document.body.removeChild(el);
        const m = computed.match(/(\d+)/g);
        if (!m) return [128, 128, 128, 1];
        return [+m[0], +m[1], +m[2], m[3] !== undefined ? +m[3] / 255 : 1];
    }

    function lightenColor(hex, blend) {
        blend = blend || 0.35;
        const [r, g, b] = parseColor(hex);
        const lr = Math.round(r + (255 - r) * blend);
        const lg = Math.round(g + (255 - g) * blend);
        const lb = Math.round(b + (255 - b) * blend);
        return `rgb(${lr},${lg},${lb})`;
    }

    function lightVariant(baseColor) {
        return lightenColor(baseColor, 0.35);
    }

    // -----------------------------------------------------------------------
    // Cluster fan-out algorithm (matching draw_planet_labels in drawing_v2.py)
    // -----------------------------------------------------------------------
    function computeClusterPositions(objects) {
        if (!objects.length) return [];

        const sorted = [...objects].sort((a, b) => a.longitude - b.longitude);

        // Build clusters
        const clusters = [];
        for (const obj of sorted) {
            let placed = false;
            for (const cluster of clusters) {
                if (Math.abs(obj.longitude - cluster[0].longitude) <= CLUSTER_THRESHOLD) {
                    cluster.push(obj);
                    placed = true;
                    break;
                }
            }
            if (!placed) {
                clusters.push([obj]);
            }
        }

        // Compute cluster base degrees (mean longitude)
        let clusterDegs = clusters.map(
            (c) => c.reduce((s, o) => s + o.longitude, 0) / c.length
        );

        // Push apart
        for (let i = 1; i < clusterDegs.length; i++) {
            if (clusterDegs[i] - clusterDegs[i - 1] < MIN_SPACING) {
                clusterDegs[i] = clusterDegs[i - 1] + MIN_SPACING;
            }
        }

        // Wrap check
        if (
            clusterDegs.length > 1 &&
            clusterDegs[0] + 360 - clusterDegs[clusterDegs.length - 1] < MIN_SPACING
        ) {
            clusterDegs[clusterDegs.length - 1] = clusterDegs[0] + 360 - MIN_SPACING;
        }

        // Fan out within clusters
        const result = [];
        for (let ci = 0; ci < clusters.length; ci++) {
            const cluster = clusters[ci];
            const base = clusterDegs[ci];
            const n = cluster.length;
            if (n === 1) {
                result.push({
                    ...cluster[0],
                    displayDegree: cluster[0].longitude,
                });
            } else {
                const start = base - (CLUSTER_SPREAD * (n - 1)) / 2;
                for (let i = 0; i < n; i++) {
                    result.push({
                        ...cluster[i],
                        displayDegree: start + i * CLUSTER_SPREAD,
                    });
                }
            }
        }

        return result;
    }

    // -----------------------------------------------------------------------
    // SVG arc path builder (sampled line segments — avoids all SVG arc/sweep
    // flag confusion and handles any angle range including wrapping).
    // startAngle and endAngle are plain radians from polarToCartesian coords.
    // The arc is drawn from startAngle → endAngle inclusive.
    // -----------------------------------------------------------------------
    function arcPath(innerR, outerR, startAngle, endAngle, scale) {
        const steps = 64;
        const ro = scale(outerR), ri = scale(innerR);
        const dTheta = (endAngle - startAngle) / steps;

        let d = "";
        // Outer arc: startAngle → endAngle
        for (let i = 0; i <= steps; i++) {
            const a = startAngle + i * dTheta;
            const x = ro * Math.cos(a), y = ro * Math.sin(a);
            d += i === 0 ? `M ${x} ${y}` : ` L ${x} ${y}`;
        }
        // Inner arc: endAngle → startAngle (reversed)
        for (let i = steps; i >= 0; i--) {
            const a = startAngle + i * dTheta;
            const x = ri * Math.cos(a), y = ri * Math.sin(a);
            d += ` L ${x} ${y}`;
        }
        return d + " Z";
    }

    // -----------------------------------------------------------------------
    // Main render function
    // -----------------------------------------------------------------------
    function render(container, data, width, height) {
        const size = Math.min(width, height);
        const margin = 10;
        const radius = (size - margin * 2) / 2;
        const cx = size / 2;
        const cy = size / 2;

        const config = data.config || {};
        const ascDeg = config.asc_degree || 0;
        const darkMode = config.dark_mode || false;
        const labelStyle = config.label_style || "glyph";
        const compassOn = config.compass_on !== false;
        const degreeMarkers = config.degree_markers !== false;
        const unknownTime = config.unknown_time || false;

        // Scale: map abstract radius (0 → RLIM) to pixel radius (0 → radius)
        const rScale = (r) => (r / RLIM) * radius;

        const svg = d3
            .select(container)
            .append("svg")
            .attr("width", size)
            .attr("height", size)
            .attr("viewBox", `0 0 ${size} ${size}`)
            .attr("class", darkMode ? "chart-svg dark" : "chart-svg");

        // Background
        svg
            .append("rect")
            .attr("width", size)
            .attr("height", size)
            .attr("fill", darkMode ? "#0E1117" : "#FFFFFF")
            .attr("class", "chart-background");

        // Main group — transform managed by D3 zoom; initial position = center
        const g = svg.append("g");

        // ── D3 Zoom ────────────────────────────────────────────────────────
        // Scroll-wheel / pinch to zoom; drag to pan.
        // Initial transform centers the chart at (cx, cy).
        const zoom = d3.zoom()
            .scaleExtent([0.4, 8])
            .on("zoom", (event) => {
                g.attr("transform", event.transform);
            });

        svg.call(zoom)
            .on("dblclick.zoom", null); // disable double-click zoom (reserved for future)

        // Apply initial centering transform
        svg.call(zoom.transform, d3.zoomIdentity.translate(cx, cy));

        // Layer groups (z-ordering)
        const layerZodiac = g.append("g").attr("class", "layer-zodiac");
        const layerHouses = g.append("g").attr("class", "layer-houses");
        const layerDegrees = g.append("g").attr("class", "layer-degrees");
        const layerAspects = g.append("g").attr("class", "layer-aspects");
        const layerCompass = g.append("g").attr("class", "layer-compass");
        const layerPlanets = g.append("g").attr("class", "layer-planets");
        const layerHighlights = g.append("g").attr("class", "layer-highlights");
        const layerSingletons = g.append("g").attr("class", "layer-singletons");

        // === Draw zodiac bands ===
        drawZodiacBands(layerZodiac, data.signs || [], ascDeg, rScale);

        // === Draw house cusps ===
        if (!unknownTime) {
            drawHouseCusps(layerHouses, data.houses || [], ascDeg, rScale, darkMode);
        }

        // === Draw degree markers ===
        if (degreeMarkers) {
            drawDegreeMarkers(layerDegrees, ascDeg, rScale, darkMode);
        }

        // === Draw aspect lines ===
        drawAspectLines(layerAspects, data.aspects || [], data.objects || [], ascDeg, rScale, darkMode);

        // === Draw compass rose ===
        if (compassOn && !unknownTime) {
            drawCompassRose(layerCompass, data.objects || [], ascDeg, rScale);
        }

        // === Draw center earth ===
        drawCenterEarth(g, rScale, darkMode);

        // === Draw chart header + moon phase (above the chart ring) ===
        drawChartHeader(svg, data.header || {}, data.moon_phase || {}, size, darkMode);

        // === Draw planet labels ===
        drawPlanetLabels(layerPlanets, data.objects || [], ascDeg, rScale, labelStyle, darkMode);

        // === Draw singleton dots ===
        const activeSingletons = data.active_singletons || [];
        if (activeSingletons.length) {
            drawSingletonDots(layerSingletons, data.objects || [], activeSingletons, ascDeg, rScale);
        }

        // === Apply highlights ===
        if (data.highlights && Object.keys(data.highlights).length) {
            applyHighlights(svg, data.highlights);
        }

        // Tooltip wiring is handled by index.html after render() returns
    }

    // -----------------------------------------------------------------------
    // Zodiac band drawing
    // -----------------------------------------------------------------------
    function drawZodiacBands(layer, signs, ascDeg, rScale) {
        const sectorWidth = (30 * Math.PI) / 180;  // π/6 radians = 30°

        signs.forEach((sign) => {
            const startRad = degToRad(sign.start_degree, ascDeg);
            // degToRad DECREASES as longitude increases, so the sector sweeps
            // in the negative (CCW) direction — endRad = startRad - sectorWidth.
            const endRad = startRad - sectorWidth;

            // Draw the band as a path
            layer
                .append("path")
                .attr("d", arcPath(R_ZODIAC_INNER, R_ZODIAC_OUTER, startRad, endRad, rScale))
                .attr("fill", sign.band_color)
                .attr("fill-opacity", 0.85)
                .attr("stroke", "none")
                .attr("class", "zodiac-band")
                .attr("data-sign", sign.name)
                .attr("data-element", sign.element);

            // Draw divider line at the start of each sign
            const [x1, y1] = polarToCartesian(rScale(R_ZODIAC_DIV_INNER), startRad);
            const [x2, y2] = polarToCartesian(rScale(R_ZODIAC_DIV_OUTER), startRad);
            layer
                .append("line")
                .attr("x1", x1).attr("y1", y1)
                .attr("x2", x2).attr("y2", y2)
                .attr("stroke", "#000000")
                .attr("stroke-width", 1)
                .attr("class", "zodiac-divider");

            // Draw glyph at the center of the segment
            // Strip U+FE0F (emoji variation selector) so the codepoints render
            // as plain text glyphs, not colour emoji in the browser.
            const midRad = degToRad(sign.start_degree + 15, ascDeg);
            const [gx, gy] = polarToCartesian(rScale(R_ZODIAC_GLYPH), midRad);
            layer
                .append("text")
                .attr("x", gx).attr("y", gy)
                .attr("text-anchor", "middle")
                .attr("dominant-baseline", "central")
                .attr("font-size", "10px")
                .attr("font-weight", "bold")
                .attr("font-family", "\"Segoe UI Symbol\", \"Apple Symbols\", \"Arial Unicode MS\", \"DejaVu Sans\", sans-serif")
                .attr("fill", sign.glyph_color)
                .attr("class", "zodiac-glyph")
                .attr("data-sign", sign.name)
                .text((sign.glyph || "").replace(/\uFE0F/g, ""));
        });
    }

    // -----------------------------------------------------------------------
    // House cusps
    // -----------------------------------------------------------------------
    function drawHouseCusps(layer, houses, ascDeg, rScale, darkMode) {
        const lineColor = darkMode ? "#333333" : "#A0A0A0";
        const lblColor = darkMode ? "#FFFFFF" : "#000000";

        houses.forEach((house, i) => {
            const rad = degToRad(house.cusp_degree, ascDeg);
            const [x1, y1] = polarToCartesian(0, rad);
            const [x2, y2] = polarToCartesian(rScale(R_HOUSE_CUSP), rad);

            layer
                .append("line")
                .attr("x1", x1).attr("y1", y1)
                .attr("x2", x2).attr("y2", y2)
                .attr("stroke", lineColor)
                .attr("stroke-width", 3.6)
                .attr("class", "house-cusp")
                .attr("data-house", house.number);

            // House number label (at 90% into the house span)
            const nextHouse = houses[(i + 1) % 12];
            const span = ((nextHouse.cusp_degree - house.cusp_degree) % 360 + 360) % 360;
            const labelDeg = (house.cusp_degree + span * 0.9) % 360;
            const labelRad = degToRad(labelDeg, ascDeg);
            const [lx, ly] = polarToCartesian(rScale(R_HOUSE_LABEL), labelRad);

            layer
                .append("text")
                .attr("x", lx).attr("y", ly)
                .attr("text-anchor", "middle")
                .attr("dominant-baseline", "central")
                .attr("font-size", "20px")
                .attr("fill", lblColor)
                .attr("class", "house-number")
                .attr("data-house", house.number)
                .text(house.number);
        });
    }

    // -----------------------------------------------------------------------
    // Degree markers
    // -----------------------------------------------------------------------
    function drawDegreeMarkers(layer, ascDeg, rScale, darkMode) {
        const color = darkMode ? "#FFFFFF" : "#000000";

        // Circle at r=1.0
        layer
            .append("circle")
            .attr("cx", 0).attr("cy", 0)
            .attr("r", rScale(R_DEGREE_CIRCLE))
            .attr("fill", "none")
            .attr("stroke", color)
            .attr("stroke-width", 4)
            .attr("class", "degree-circle");

        // Tick marks
        for (let deg = 0; deg < 360; deg++) {
            const rad = degToRad(deg, ascDeg);
            let tickLen = 0.015;
            let tickWidth = 1.0;
            if (deg % 10 === 0) {
                tickLen = 0.05;
                tickWidth = 2.4;
            } else if (deg % 5 === 0) {
                tickLen = 0.03;
                tickWidth = 1.2;
            }

            const [x1, y1] = polarToCartesian(rScale(R_DEGREE_CIRCLE), rad);
            const [x2, y2] = polarToCartesian(rScale(R_DEGREE_CIRCLE + tickLen), rad);

            layer
                .append("line")
                .attr("x1", x1).attr("y1", y1)
                .attr("x2", x2).attr("y2", y2)
                .attr("stroke", color)
                .attr("stroke-width", tickWidth)
                .attr("class", "degree-tick");
        }
    }

    // -----------------------------------------------------------------------
    // Aspect lines (gradient chords)
    // -----------------------------------------------------------------------
    function drawAspectLines(layer, aspects, objects, ascDeg, rScale, darkMode) {
        // Build position lookup
        const posMap = {};
        objects.forEach((o) => {
            posMap[o.name] = o.longitude;
        });

        // Define gradient defs
        const defs = layer.append("defs");
        let gradIdx = 0;

        aspects.forEach((asp) => {
            const d1 = posMap[asp.obj_a];
            const d2 = posMap[asp.obj_b];
            if (d1 === undefined || d2 === undefined) return;

            const r1 = degToRad(d1, ascDeg);
            const r2 = degToRad(d2, ascDeg);
            const [x1, y1] = polarToCartesian(rScale(R_ASPECT), r1);
            const [x2, y2] = polarToCartesian(rScale(R_ASPECT), r2);

            // Color logic: luminary/planet gets full color, others get light variant
            let baseColor = asp.color || "gray";
            if (asp.is_approx) {
                baseColor = lightenColor(baseColor, 0.35);
            }
            const startColor = isLuminaryOrPlanet(asp.obj_a) ? baseColor : lightVariant(baseColor);
            const endColor = isLuminaryOrPlanet(asp.obj_b) ? baseColor : lightVariant(baseColor);

            // Line style
            const isMajor = asp.is_major !== false;
            let lw = isMajor ? 8 : 4;
            const aspectName = (asp.aspect || "").toLowerCase();
            if (aspectName === "quincunx" || aspectName === "sesquisquare") {
                lw = 4;
            }

            let dashArray = "none";
            const style = asp.style || "solid";
            if (style === "dotted") dashArray = "3,3";
            else if (style === "dashed") dashArray = "6,3";

            // Create gradient
            const gradId = `asp-grad-${gradIdx++}`;
            const grad = defs
                .append("linearGradient")
                .attr("id", gradId)
                .attr("x1", x1).attr("y1", y1)
                .attr("x2", x2).attr("y2", y2)
                .attr("gradientUnits", "userSpaceOnUse");
            grad.append("stop").attr("offset", "0%").attr("stop-color", startColor);
            grad.append("stop").attr("offset", "100%").attr("stop-color", endColor);

            // Draw the line
            layer
                .append("line")
                .attr("x1", x1).attr("y1", y1)
                .attr("x2", x2).attr("y2", y2)
                .attr("stroke", `url(#${gradId})`)
                .attr("stroke-width", lw)
                .attr("stroke-dasharray", dashArray === "none" ? null : dashArray)
                .attr("class", "aspect-line")
                .attr("data-aspect", asp.aspect)
                .attr("data-obj-a", asp.obj_a)
                .attr("data-obj-b", asp.obj_b)
                .attr("data-is-major", isMajor)
                .attr("data-original-width", lw)
                .attr("data-conductance", asp.conductance || "")
                .attr("data-transmitted-power", asp.transmitted_power || "")
                .attr("data-friction-heat", asp.friction_heat || "")
                .attr("data-is-arc-hazard", asp.is_arc_hazard || false);
        });
    }

    // -----------------------------------------------------------------------
    // Compass rose
    // -----------------------------------------------------------------------
    function drawCompassRose(layer, objects, ascDeg, rScale, compassRadius, markerSizeOverride) {
        const posMap = {};
        objects.forEach((o) => {
            posMap[o.name] = o.longitude;
        });

        const nodal = "#800080";
        const axisColor = "#4E83AF";
        // Unique marker ID per compass instance to avoid SVG ID collisions
        const markerId = "arrow-nn-" + (compassRadius || "default").toString().replace(".", "_");
        const r = rScale(compassRadius !== undefined ? compassRadius : R_ASPECT);

        // Compass visual sizing (matches original proven values)
        const axisStroke = 2;
        const nodalStroke = 4;
        const markerSize = markerSizeOverride !== undefined ? markerSizeOverride : 8;
        const snDotR = 4;

        // AC–DC line
        const acDeg = posMap["Ascendant"] ?? posMap["AC"];
        const dcDeg = posMap["Descendant"] ?? posMap["DC"];
        if (acDeg !== undefined) {
            const effDc = dcDeg !== undefined ? dcDeg : (acDeg + 180) % 360;
            const r1 = degToRad(acDeg, ascDeg);
            const r2 = degToRad(effDc, ascDeg);
            const [x1, y1] = polarToCartesian(r, r1);
            const [x2, y2] = polarToCartesian(r, r2);
            layer.append("line")
                .attr("x1", x1).attr("y1", y1)
                .attr("x2", x2).attr("y2", y2)
                .attr("stroke", axisColor).attr("stroke-width", axisStroke)
                .attr("class", "compass-axis");
        }

        // MC–IC line
        const mcDeg = posMap["Midheaven"] ?? posMap["MC"];
        const icDeg = posMap["Imum Coeli"] ?? posMap["IC"];
        if (mcDeg !== undefined) {
            const effIc = icDeg !== undefined ? icDeg : (mcDeg + 180) % 360;
            const r1 = degToRad(mcDeg, ascDeg);
            const r2 = degToRad(effIc, ascDeg);
            const [x1, y1] = polarToCartesian(r, r1);
            const [x2, y2] = polarToCartesian(r, r2);
            layer.append("line")
                .attr("x1", x1).attr("y1", y1)
                .attr("x2", x2).attr("y2", y2)
                .attr("stroke", axisColor).attr("stroke-width", axisStroke)
                .attr("class", "compass-axis");
        }

        // Nodal axis (SN → NN arrow)
        const snDeg = posMap["South Node"];
        const nnDeg = posMap["North Node"];
        if (snDeg !== undefined && nnDeg !== undefined) {
            const snRad = degToRad(snDeg, ascDeg);
            const nnRad = degToRad(nnDeg, ascDeg);
            const [sx, sy] = polarToCartesian(r, snRad);
            const [nx, ny] = polarToCartesian(r, nnRad);

            // Arrow marker
            const defs = layer.select("defs").empty()
                ? layer.append("defs")
                : layer.select("defs");
            defs.append("marker")
                .attr("id", markerId)
                .attr("viewBox", "0 0 10 10")
                .attr("refX", 10).attr("refY", 5)
                .attr("markerWidth", markerSize).attr("markerHeight", markerSize)
                .attr("orient", "auto-start-reverse")
                .append("path")
                .attr("d", "M 0 0 L 10 5 L 0 10 Z")
                .attr("fill", nodal);

            layer.append("line")
                .attr("x1", sx).attr("y1", sy)
                .attr("x2", nx).attr("y2", ny)
                .attr("stroke", nodal).attr("stroke-width", nodalStroke)
                .attr("marker-end", `url(#${markerId})`)
                .attr("class", "compass-nodal");

            // SN dot
            layer.append("circle")
                .attr("cx", sx).attr("cy", sy)
                .attr("r", snDotR)
                .attr("fill", nodal)
                .attr("class", "compass-sn-dot");
        }
    }

    // -----------------------------------------------------------------------
    // Center earth icon
    // -----------------------------------------------------------------------
    function drawCenterEarth(g, rScale, darkMode) {
        const r = rScale(0.08);
        const color = darkMode ? "#555555" : "#888888";

        // Simple earth circle with cross
        g.append("circle")
            .attr("cx", 0).attr("cy", 0)
            .attr("r", r)
            .attr("fill", "none")
            .attr("stroke", color)
            .attr("stroke-width", 6)
            .attr("class", "center-earth");
        g.append("line")
            .attr("x1", -r).attr("y1", 0)
            .attr("x2", r).attr("y2", 0)
            .attr("stroke", color).attr("stroke-width", 3)
            .attr("class", "center-earth");
        g.append("line")
            .attr("x1", 0).attr("y1", -r)
            .attr("x2", 0).attr("y2", r)
            .attr("stroke", color).attr("stroke-width", 3)
            .attr("class", "center-earth");
    }

    // -----------------------------------------------------------------------
    // Chart header (name, date, time, city) + moon phase label/icon
    // Drawn in SVG-root (screen) coordinates, NOT inside the zoomable group.
    // -----------------------------------------------------------------------
    function drawChartHeader(svg, header, moonPhase, size, darkMode) {
        if (!header || !header.name) return;
        const color = darkMode ? "#FFFFFF" : "#000000";
        const subColor = darkMode ? "#CCCCCC" : "#333333";
        const x0 = 14;        // left padding
        let y = 40;           // start y
        const lineHeight = 30;

        // Chart name (bold, larger)
        svg.append("text")
            .attr("x", x0).attr("y", y)
            .attr("font-size", "24px")
            .attr("font-weight", "bold")
            .attr("fill", color)
            .attr("class", "chart-header-name")
            .text(header.name);
        y += lineHeight;

        // Date line
        if (header.date_line) {
            svg.append("text")
                .attr("x", x0).attr("y", y)
                .attr("font-size", "16px")
                .attr("fill", subColor)
                .attr("class", "chart-header-date")
                .text(header.date_line);
            y += lineHeight;
        }

        // Time line
        if (header.time_line) {
            svg.append("text")
                .attr("x", x0).attr("y", y)
                .attr("font-size", "16px")
                .attr("fill", subColor)
                .attr("class", "chart-header-time")
                .text(header.time_line);
            y += lineHeight;
        }

        // City
        if (header.city) {
            svg.append("text")
                .attr("x", x0).attr("y", y)
                .attr("font-size", "16px")
                .attr("fill", subColor)
                .attr("class", "chart-header-city")
                .text(header.city);
        }

        // Moon phase label + SVG icon (upper-right)
        if (moonPhase && moonPhase.label) {
            const rightX = size - 14;
            const moonY = 26;

            // SVG moon icon (drawn first, label to its left)
            const iconR = 24;
            const iconCx = rightX - iconR;
            const iconCy = moonY + iconR + 4;
            _drawMoonIcon(svg, iconCx, iconCy, iconR, moonPhase.phase_delta || 0, darkMode);

            // Label to the left of the icon
            svg.append("text")
                .attr("x", iconCx - iconR - 8).attr("y", iconCy + 5)
                .attr("text-anchor", "end")
                .attr("font-size", "20px")
                .attr("font-weight", "bold")
                .attr("fill", color)
                .attr("class", "chart-moon-label")
                .text(moonPhase.label);
        }
    }

    // -----------------------------------------------------------------------
    // SVG moon phase icon
    // phase_delta: 0 = new, 90 = first quarter, 180 = full, 270 = last quarter
    // Uses a clip-path approach for reliability: draw a full lit circle,
    // then clip it to the illuminated half using a cubic Bézier terminator.
    // -----------------------------------------------------------------------
    function _drawMoonIcon(svg, cx, cy, r, phaseDelta, darkMode) {
        const bgFill = darkMode ? "#444" : "#BBB";
        const litFill = darkMode ? "#EEE" : "#FFFDE7";
        const strokeColor = darkMode ? "#888" : "#777";

        // Background circle (shadow side)
        svg.append("circle")
            .attr("cx", cx).attr("cy", cy).attr("r", r)
            .attr("fill", bgFill)
            .attr("stroke", strokeColor).attr("stroke-width", 1.5)
            .attr("class", "moon-icon-bg");

        const p = ((phaseDelta % 360) + 360) % 360;

        // Full moon or very close: just fill the whole circle
        if (p >= 170 && p <= 190) {
            svg.append("circle")
                .attr("cx", cx).attr("cy", cy).attr("r", r - 0.5)
                .attr("fill", litFill)
                .attr("class", "moon-icon-lit");
            return;
        }
        // New moon or very close: no lit area
        if (p <= 10 || p >= 350) {
            return;
        }

        // Determine which half is lit and the terminator bulge.
        // Waxing (0-180): lit on the RIGHT side
        // Waning (180-360): lit on the LEFT side
        const waxing = p < 180;
        // Normalised phase within the half-cycle (0..180)
        const hp = waxing ? p : (p - 180);
        // Terminator curvature: 0 at quarter (straight), ±r at new/full
        // k < 0 → concave (crescent), k > 0 → convex (gibbous)
        const k = r * Math.cos(hp * Math.PI / 180);

        const top = cy - r;
        const bot = cy + r;

        // Terminator is an S-curve from top to bottom through cx.
        // Control points offset horizontally by k.
        // Outer edge is a semicircle arc on the lit side.
        const litSide = waxing ? 1 : -1; // +1 = right, -1 = left

        // Outer semicircle arc on the lit side: top→bottom via cx±r
        // large-arc=1, sweep depends on direction
        const outerSweep = waxing ? 0 : 1;

        // Build path:
        // M top-center → cubic Bézier terminator → bottom-center → semicircle back
        const d = [
            `M ${cx} ${top}`,
            `C ${cx + k} ${cy - r * 0.4}, ${cx + k} ${cy + r * 0.4}, ${cx} ${bot}`,
            `A ${r} ${r} 0 0 ${outerSweep} ${cx} ${top}`,
            "Z",
        ].join(" ");

        svg.append("path")
            .attr("d", d)
            .attr("fill", litFill)
            .attr("class", "moon-icon-lit");
    }

    // -----------------------------------------------------------------------
    // Planet labels (with cluster fan-out)
    // -----------------------------------------------------------------------
    function drawPlanetLabels(layer, objects, ascDeg, rScale, labelStyle, darkMode) {
        if (!objects.length) return;

        const color = darkMode ? "#FFFFFF" : "#000000";
        const useGlyphs = (labelStyle || "glyph").toLowerCase() === "glyph";

        // Compute display positions with cluster fan-out
        const positioned = computeClusterPositions(objects);

        positioned.forEach((obj) => {
            const displayRad = degToRad(obj.displayDegree % 360, ascDeg);
            const [gx, gy] = polarToCartesian(rScale(R_PLANET_GLYPH), displayRad);
            const [dx, dy] = polarToCartesian(rScale(R_PLANET_DEGREE), displayRad);

            const label = useGlyphs ? (obj.glyph || obj.name) : obj.name;
            const degInSign = obj.degree_in_sign !== undefined ? obj.degree_in_sign : Math.floor(obj.longitude % 30);
            let degLabel = `${degInSign}°`;
            if (obj.retrograde) degLabel += " Rx";

            // Planet glyph/name
            layer
                .append("text")
                .attr("x", gx).attr("y", gy)
                .attr("text-anchor", "middle")
                .attr("dominant-baseline", "central")
                .attr("font-weight", "bold")
                .attr("font-size", "20px")
                .attr("fill", color)
                .attr("class", "planet-glyph")
                .attr("data-object", obj.name)
                .text(label);

            // Degree label
            layer
                .append("text")
                .attr("x", dx).attr("y", dy)
                .attr("text-anchor", "middle")
                .attr("dominant-baseline", "central")
                .attr("font-size", "14px")
                .attr("fill", color)
                .attr("class", "planet-degree")
                .attr("data-object", obj.name)
                .text(degLabel);

            // Invisible hit area for easier hover/click (planets are small text)
            layer
                .append("circle")
                .attr("cx", gx).attr("cy", gy)
                .attr("r", 12)
                .attr("fill", "transparent")
                .attr("class", "planet-hitarea")
                .attr("data-object", obj.name)
                .style("cursor", "pointer");
        });
    }

    // -----------------------------------------------------------------------
    // Singleton dots  (drawn on the degree circle for lone-planet toggles)
    // Matches drawing_v2.draw_singleton_dots: a solid-filled circle on the
    // outer edge of the degree ring at the planet's exact longitude.
    // -----------------------------------------------------------------------
    function drawSingletonDots(layer, objects, activeSingletons, ascDeg, rScale) {
        const singletonSet = new Set(
            (activeSingletons || []).map((s) => (s || "").toLowerCase())
        );
        const posMap = {};
        objects.forEach((o) => { posMap[(o.name || "").toLowerCase()] = o.longitude; });

        // Cycle through a small palette for multiple singletons
        const palette = ["#9B59B6", "#1ABC9C", "#E67E22", "#E74C3C", "#3498DB"];
        let colorIdx = 0;
        singletonSet.forEach((name) => {
            const lon = posMap[name];
            if (lon === undefined) return;
            const rad = degToRad(lon, ascDeg);
            const r = rScale(R_DEGREE_CIRCLE);
            const [cx, cy] = polarToCartesian(r, rad);
            const color = palette[colorIdx % palette.length];
            colorIdx++;

            // Outer ring dot
            layer.append("circle")
                .attr("cx", cx).attr("cy", cy)
                .attr("r", 5)
                .attr("fill", color)
                .attr("stroke", "#fff")
                .attr("stroke-width", 1.8)
                .attr("class", "singleton-dot")
                .attr("data-object", name);
        });
    }

    // -----------------------------------------------------------------------
    // Highlight system
    // -----------------------------------------------------------------------
    function applyHighlights(svg, highlights) {
        if (!highlights || highlights.clear) {
            svg.selectAll(".highlight-dim").classed("highlight-dim", false);
            svg.selectAll(".highlight-glow").classed("highlight-glow", false);
            return;
        }

        const hlObjects = new Set(highlights.objects || []);
        const hlHouses = new Set((highlights.houses || []).map(String));
        const hlAspects = new Set(
            (highlights.aspects || []).map((a) =>
                typeof a === "string" ? a : `${a[0]}-${a[1]}-${a[2]}`
            )
        );

        const anyHighlight = hlObjects.size > 0 || hlHouses.size > 0 || hlAspects.size > 0;
        if (!anyHighlight) return;

        // Dim everything first
        svg.selectAll(".planet-glyph, .planet-degree, .planet-hitarea").classed("highlight-dim", (d, i, nodes) => {
            const name = nodes[i].getAttribute("data-object");
            return name && !hlObjects.has(name);
        });

        svg.selectAll(".aspect-line").classed("highlight-dim", (d, i, nodes) => {
            const a = nodes[i].getAttribute("data-obj-a");
            const b = nodes[i].getAttribute("data-obj-b");
            const asp = nodes[i].getAttribute("data-aspect");
            // Highlight if either endpoint is highlighted or the aspect is directly highlighted
            if (hlObjects.has(a) || hlObjects.has(b)) return false;
            if (hlAspects.has(`${a}-${b}-${asp}`) || hlAspects.has(`${b}-${a}-${asp}`)) return false;
            return true;
        });

        svg.selectAll(".house-cusp, .house-number").classed("highlight-dim", (d, i, nodes) => {
            const h = nodes[i].getAttribute("data-house");
            return h && !hlHouses.has(h);
        });

        // Glow highlighted objects
        svg.selectAll(".planet-glyph").classed("highlight-glow", (d, i, nodes) => {
            const name = nodes[i].getAttribute("data-object");
            return name && hlObjects.has(name);
        });

        svg.selectAll(".aspect-line").classed("highlight-glow", (d, i, nodes) => {
            const a = nodes[i].getAttribute("data-obj-a");
            const b = nodes[i].getAttribute("data-obj-b");
            return hlObjects.has(a) || hlObjects.has(b);
        });
    }

    // -----------------------------------------------------------------------
    // Biwheel geometry constants (matching drawing_v2.py render_biwheel_chart)
    // -----------------------------------------------------------------------
    const BIWHEEL = {
        INNER_CIRCLE_R: 0.9,      // Inner degree circle
        OUTER_CIRCLE_R: 1.2,      // Outer degree circle
        INNER_LABEL_R: 1.1,       // Inner chart planet glyphs
        INNER_DEGREE_R: 1.0,      // Inner chart degree numbers
        OUTER_LABEL_R: 1.4,       // Outer chart planet glyphs
        OUTER_DEGREE_R: 1.31,     // Outer chart degree numbers
        OUTER_CUSP_R: 1.45,       // Where outer house cusps end
    };

    // -----------------------------------------------------------------------
    // Biwheel render function
    // -----------------------------------------------------------------------
    function renderBiwheel(container, data, width, height) {
        const size = Math.min(width, height);
        const margin = 10;
        const radius = (size - margin * 2) / 2;
        const cx = size / 2;
        const cy = size / 2;

        const config = data.config || {};
        const ascDeg = config.asc_degree || 0;
        const darkMode = config.dark_mode || false;
        const labelStyle = config.label_style || "glyph";
        const compassOnInner = config.compass_on_inner !== false;
        const compassOnOuter = config.compass_on_outer !== false;
        const degreeMarkers = config.degree_markers !== false;
        const unknownTimeInner = config.unknown_time_inner || false;
        const unknownTimeOuter = config.unknown_time_outer || false;

        // Scale: map abstract radius (0 → RLIM) to pixel radius
        const rScale = (r) => (r / RLIM) * radius;

        const svg = d3
            .select(container)
            .append("svg")
            .attr("width", size)
            .attr("height", size)
            .attr("viewBox", `0 0 ${size} ${size}`)
            .attr("class", darkMode ? "chart-svg dark biwheel" : "chart-svg biwheel");

        // Background
        svg
            .append("rect")
            .attr("width", size)
            .attr("height", size)
            .attr("fill", darkMode ? "#0E1117" : "#FFFFFF")
            .attr("class", "chart-background");

        // Main group — transform managed by D3 zoom
        const g = svg.append("g");

        // D3 Zoom
        const zoom = d3.zoom()
            .scaleExtent([0.4, 8])
            .on("zoom", (event) => {
                g.attr("transform", event.transform);
            });

        svg.call(zoom)
            .on("dblclick.zoom", null);

        svg.call(zoom.transform, d3.zoomIdentity.translate(cx, cy));

        // Layer groups
        const layerZodiac = g.append("g").attr("class", "layer-zodiac");
        const layerDegrees = g.append("g").attr("class", "layer-degrees");
        const layerHousesInner = g.append("g").attr("class", "layer-houses-inner");
        const layerHousesOuter = g.append("g").attr("class", "layer-houses-outer");
        const layerAspectsInternal = g.append("g").attr("class", "layer-aspects-internal");
        const layerAspectsInter = g.append("g").attr("class", "layer-aspects-inter");
        const layerCompassInner = g.append("g").attr("class", "layer-compass-inner");
        const layerCompassOuter = g.append("g").attr("class", "layer-compass-outer");
        const layerPlanetsInner = g.append("g").attr("class", "layer-planets-inner");
        const layerPlanetsOuter = g.append("g").attr("class", "layer-planets-outer");
        const layerHighlights = g.append("g").attr("class", "layer-highlights");

        // === Draw zodiac bands (outermost ring) ===
        drawZodiacBands(layerZodiac, data.signs || [], ascDeg, rScale);

        // === Draw TWO degree marker circles ===
        if (degreeMarkers) {
            drawBiwheelDegreeMarkers(layerDegrees, ascDeg, rScale, darkMode);
        }

        // === Draw inner chart house cusps (between inner and outer circles) ===
        if (!unknownTimeInner) {
            drawBiwheelHouseCusps(
                layerHousesInner,
                data.houses_inner || [],
                ascDeg,
                rScale,
                darkMode,
                BIWHEEL.INNER_CIRCLE_R,
                BIWHEEL.OUTER_CIRCLE_R,
                true
            );
        }

        // === Draw outer chart house cusps (between outer circle and zodiac) ===
        if (!unknownTimeOuter) {
            drawBiwheelHouseCusps(
                layerHousesOuter,
                data.houses_outer || [],
                ascDeg,
                rScale,
                darkMode,
                BIWHEEL.OUTER_CIRCLE_R,
                BIWHEEL.OUTER_CUSP_R,
                true
            );
        }

        // === Draw chart 1 internal aspects (if enabled) ===
        const aspectsChart1 = data.aspects_chart1 || [];
        if (aspectsChart1.length) {
            drawBiwheelAspectLines(
                layerAspectsInternal,
                aspectsChart1,
                data.objects_inner || [],
                ascDeg,
                rScale,
                darkMode,
                BIWHEEL.INNER_CIRCLE_R,
                data.colors?.chart1_group_color
            );
        }

        // === Draw chart 2 internal aspects (if enabled) ===
        const aspectsChart2 = data.aspects_chart2 || [];
        if (aspectsChart2.length) {
            drawBiwheelAspectLines(
                layerAspectsInternal,
                aspectsChart2,
                data.objects_outer || [],
                ascDeg,
                rScale,
                darkMode,
                BIWHEEL.INNER_CIRCLE_R,
                data.colors?.chart2_group_color
            );
        }

        // === Draw inter-chart aspects (connecting inner to outer wheel) ===
        const aspectsInter = data.aspects_inter || [];
        if (aspectsInter.length) {
            drawBiwheelInterAspects(
                layerAspectsInter,
                aspectsInter,
                data.objects_inner || [],
                data.objects_outer || [],
                ascDeg,
                rScale,
                darkMode
            );
        }

        // === Draw circuit mode aspects (using circuit_data if present) ===
        const circuitData = data.circuit_data;
        if (circuitData && circuitData.aspects && circuitData.aspects.length) {
            drawBiwheelCircuitAspects(
                layerAspectsInternal,
                circuitData.aspects,
                data.objects_inner || [],
                data.objects_outer || [],
                ascDeg,
                rScale,
                darkMode
            );
        }

        // === Draw compass rose for inner chart ===
        if (compassOnInner && !unknownTimeInner) {
            drawCompassRose(layerCompassInner, data.objects_inner || [], ascDeg, rScale, BIWHEEL.INNER_CIRCLE_R, 8);
        }

        // === Draw compass rose for outer chart ===
        if (compassOnOuter && !unknownTimeOuter) {
            drawCompassRose(layerCompassOuter, data.objects_outer || [], ascDeg, rScale, BIWHEEL.INNER_CIRCLE_R, 6);
        }

        // === Draw singleton dots ===
        if (circuitData && circuitData.singleton_toggles) {
            const activeSingletonsBi = Object.entries(circuitData.singleton_toggles)
                .filter(([, on]) => on)
                .map(([name]) => name);
            if (activeSingletonsBi.length) {
                const layerSingletons = g.append("g").attr("class", "layer-singletons");
                drawSingletonDots(layerSingletons, data.objects_inner || [], activeSingletonsBi, ascDeg, rScale);
            }
        }

        // === Draw center earth ===
        drawCenterEarth(g, rScale, darkMode);

        // === Draw biwheel chart header ===
        drawBiwheelHeader(
            svg,
            data.header_inner || {},
            data.header_outer || {},
            size,
            darkMode
        );

        // === Draw planet labels for inner chart (between the circles) ===
        drawBiwheelPlanetLabels(
            layerPlanetsInner,
            data.objects_inner || [],
            ascDeg,
            rScale,
            labelStyle,
            darkMode,
            BIWHEEL.INNER_LABEL_R,
            BIWHEEL.INNER_DEGREE_R,
            "inner"
        );

        // === Draw planet labels for outer chart (outside outer circle) ===
        drawBiwheelPlanetLabels(
            layerPlanetsOuter,
            data.objects_outer || [],
            ascDeg,
            rScale,
            labelStyle,
            darkMode,
            BIWHEEL.OUTER_LABEL_R,
            BIWHEEL.OUTER_DEGREE_R,
            "outer"
        );

        // === Apply highlights ===
        if (data.highlights && Object.keys(data.highlights).length) {
            applyHighlights(svg, data.highlights);
        }
    }

    // -----------------------------------------------------------------------
    // Biwheel-specific drawing functions
    // -----------------------------------------------------------------------

    function drawBiwheelDegreeMarkers(layer, ascDeg, rScale, darkMode) {
        const color = darkMode ? "#FFFFFF" : "#000000";

        // Inner degree circle
        layer
            .append("circle")
            .attr("cx", 0).attr("cy", 0)
            .attr("r", rScale(BIWHEEL.INNER_CIRCLE_R))
            .attr("fill", "none")
            .attr("stroke", color)
            .attr("stroke-width", 3)
            .attr("class", "degree-circle-inner");

        // Inner circle tick marks
        for (let deg = 0; deg < 360; deg++) {
            const rad = degToRad(deg, ascDeg);
            let tickLen = 0.015;
            let tickWidth = 0.5;
            if (deg % 10 === 0) {
                tickLen = 0.05;
                tickWidth = 1.2;
            } else if (deg % 5 === 0) {
                tickLen = 0.03;
                tickWidth = 0.8;
            }

            const [x1, y1] = polarToCartesian(rScale(BIWHEEL.INNER_CIRCLE_R), rad);
            const [x2, y2] = polarToCartesian(rScale(BIWHEEL.INNER_CIRCLE_R + tickLen), rad);

            layer
                .append("line")
                .attr("x1", x1).attr("y1", y1)
                .attr("x2", x2).attr("y2", y2)
                .attr("stroke", color)
                .attr("stroke-width", tickWidth)
                .attr("class", "degree-tick-inner");
        }

        // Outer degree circle
        layer
            .append("circle")
            .attr("cx", 0).attr("cy", 0)
            .attr("r", rScale(BIWHEEL.OUTER_CIRCLE_R))
            .attr("fill", "none")
            .attr("stroke", color)
            .attr("stroke-width", 3)
            .attr("class", "degree-circle-outer");

        // Outer circle tick marks
        for (let deg = 0; deg < 360; deg++) {
            const rad = degToRad(deg, ascDeg);
            let tickLen = 0.015;
            let tickWidth = 0.5;
            if (deg % 10 === 0) {
                tickLen = 0.05;
                tickWidth = 1.2;
            } else if (deg % 5 === 0) {
                tickLen = 0.03;
                tickWidth = 0.8;
            }

            const [x1, y1] = polarToCartesian(rScale(BIWHEEL.OUTER_CIRCLE_R), rad);
            const [x2, y2] = polarToCartesian(rScale(BIWHEEL.OUTER_CIRCLE_R + tickLen), rad);

            layer
                .append("line")
                .attr("x1", x1).attr("y1", y1)
                .attr("x2", x2).attr("y2", y2)
                .attr("stroke", color)
                .attr("stroke-width", tickWidth)
                .attr("class", "degree-tick-outer");
        }
    }

    function drawBiwheelHouseCusps(layer, houses, ascDeg, rScale, darkMode, rInner, rOuter, drawLabels) {
        const lineColor = darkMode ? "#444444" : "#A0A0A0";
        const lblColor = darkMode ? "#FFFFFF" : "#000000";

        houses.forEach((house, i) => {
            const rad = degToRad(house.cusp_degree, ascDeg);
            const [x1, y1] = polarToCartesian(rScale(rInner), rad);
            const [x2, y2] = polarToCartesian(rScale(rOuter), rad);

            layer
                .append("line")
                .attr("x1", x1).attr("y1", y1)
                .attr("x2", x2).attr("y2", y2)
                .attr("stroke", lineColor)
                .attr("stroke-width", 2)
                .attr("class", "house-cusp")
                .attr("data-house", house.number);

            // House number label (midway through the house span)
            if (drawLabels) {
                const nextHouse = houses[(i + 1) % 12];
                const span = ((nextHouse.cusp_degree - house.cusp_degree) % 360 + 360) % 360;
                const labelDeg = (house.cusp_degree + span * 0.5) % 360;
                const labelRad = degToRad(labelDeg, ascDeg);
                const midR = (rInner + rOuter) / 2;
                const [lx, ly] = polarToCartesian(rScale(midR), labelRad);

                layer
                    .append("text")
                    .attr("x", lx).attr("y", ly)
                    .attr("text-anchor", "middle")
                    .attr("dominant-baseline", "central")
                    .attr("font-size", "16px")
                    .attr("fill", lblColor)
                    .attr("class", "house-number")
                    .attr("data-house", house.number)
                    .text(house.number);
            }
        });
    }

    function drawBiwheelAspectLines(layer, aspects, objects, ascDeg, rScale, darkMode, aspectRadius, groupColor) {
        const posMap = {};
        objects.forEach((o) => {
            posMap[o.name] = o.longitude;
        });

        const defs = layer.select("defs").empty()
            ? layer.append("defs")
            : layer.select("defs");
        let gradIdx = 0;

        aspects.forEach((asp) => {
            const d1 = posMap[asp.obj_a];
            const d2 = posMap[asp.obj_b];
            if (d1 === undefined || d2 === undefined) return;

            const r1 = degToRad(d1, ascDeg);
            const r2 = degToRad(d2, ascDeg);
            const [x1, y1] = polarToCartesian(rScale(aspectRadius), r1);
            const [x2, y2] = polarToCartesian(rScale(aspectRadius), r2);

            // Use group color if provided, otherwise use standard aspect colors
            let baseColor = groupColor || asp.color || "gray";
            if (asp.is_approx && !groupColor) {
                baseColor = lightenColor(baseColor, 0.35);
            }

            const lw = 6;
            let dashArray = "none";
            const style = asp.style || "solid";
            if (style === "dotted") dashArray = "3,3";
            else if (style === "dashed") dashArray = "6,3";

            layer
                .append("line")
                .attr("x1", x1).attr("y1", y1)
                .attr("x2", x2).attr("y2", y2)
                .attr("stroke", baseColor)
                .attr("stroke-width", lw)
                .attr("stroke-dasharray", dashArray === "none" ? null : dashArray)
                .attr("class", "aspect-line internal")
                .attr("data-aspect", asp.aspect)
                .attr("data-obj-a", asp.obj_a)
                .attr("data-obj-b", asp.obj_b)
                .attr("data-aspect-group", asp.aspect_group || "internal");
        });
    }

    function drawBiwheelInterAspects(layer, aspects, objectsInner, objectsOuter, ascDeg, rScale, darkMode) {
        // Build position lookup for both charts
        const posInner = {};
        objectsInner.forEach((o) => {
            posInner[o.name] = o.longitude;
        });
        const posOuter = {};
        objectsOuter.forEach((o) => {
            posOuter[o.name] = o.longitude;
        });

        const defs = layer.select("defs").empty()
            ? layer.append("defs")
            : layer.select("defs");
        let gradIdx = 0;

        aspects.forEach((asp) => {
            // obj_a is from inner chart, obj_b is from outer chart
            const d1 = posInner[asp.obj_a];
            const d2 = posOuter[asp.obj_b];
            if (d1 === undefined || d2 === undefined) return;

            const r1 = degToRad(d1, ascDeg);
            const r2 = degToRad(d2, ascDeg);
            // Inner object at inner circle, outer object at inner circle too
            // (aspects drawn inside the inner circle for clarity)
            const [x1, y1] = polarToCartesian(rScale(BIWHEEL.INNER_CIRCLE_R), r1);
            const [x2, y2] = polarToCartesian(rScale(BIWHEEL.INNER_CIRCLE_R), r2);

            let baseColor = asp.color || "gray";
            if (asp.is_approx) {
                baseColor = lightenColor(baseColor, 0.35);
            }
            const startColor = isLuminaryOrPlanet(asp.obj_a) ? baseColor : lightVariant(baseColor);
            const endColor = isLuminaryOrPlanet(asp.obj_b) ? baseColor : lightVariant(baseColor);

            const lw = 8;
            let dashArray = "none";
            const style = asp.style || "solid";
            if (style === "dotted") dashArray = "3,3";
            else if (style === "dashed") dashArray = "6,3";

            // Create gradient
            const gradId = `biwheel-asp-grad-${gradIdx++}`;
            const grad = defs
                .append("linearGradient")
                .attr("id", gradId)
                .attr("x1", x1).attr("y1", y1)
                .attr("x2", x2).attr("y2", y2)
                .attr("gradientUnits", "userSpaceOnUse");
            grad.append("stop").attr("offset", "0%").attr("stop-color", startColor);
            grad.append("stop").attr("offset", "100%").attr("stop-color", endColor);

            layer
                .append("line")
                .attr("x1", x1).attr("y1", y1)
                .attr("x2", x2).attr("y2", y2)
                .attr("stroke", `url(#${gradId})`)
                .attr("stroke-width", lw)
                .attr("stroke-dasharray", dashArray === "none" ? null : dashArray)
                .attr("class", "aspect-line inter-chart")
                .attr("data-aspect", asp.aspect)
                .attr("data-obj-a", asp.obj_a)
                .attr("data-obj-b", asp.obj_b)
                .attr("data-aspect-group", "inter");
        });
    }

    function drawBiwheelCircuitAspects(layer, aspects, objectsInner, objectsOuter, ascDeg, rScale, darkMode) {
        // Build position lookup for both charts
        const posInner = {};
        objectsInner.forEach((o) => {
            posInner[o.name] = o.longitude;
        });
        const posOuter = {};
        objectsOuter.forEach((o) => {
            posOuter[o.name] = o.longitude;
        });
        // Combined positions: inner objects + outer objects with _2 suffix
        const posCombined = { ...posInner };
        for (const [name, lon] of Object.entries(posOuter)) {
            posCombined[name + "_2"] = lon;
        }

        const defs = layer.select("defs").empty()
            ? layer.append("defs")
            : layer.select("defs");
        let gradIdx = 0;

        aspects.forEach((asp) => {
            // obj_a and obj_b may have _2 suffix for outer chart objects
            let d1 = posCombined[asp.obj_a];
            let d2 = posCombined[asp.obj_b];

            // Fallback: try without _2 suffix in inner, with _2 in outer
            if (d1 === undefined) d1 = posInner[asp.obj_a] || posOuter[asp.obj_a];
            if (d2 === undefined) d2 = posInner[asp.obj_b] || posOuter[asp.obj_b];

            if (d1 === undefined || d2 === undefined) return;

            const r1 = degToRad(d1, ascDeg);
            const r2 = degToRad(d2, ascDeg);

            // Always draw circuit aspect lines to the inner circle
            const [x1, y1] = polarToCartesian(rScale(BIWHEEL.INNER_CIRCLE_R), r1);
            const [x2, y2] = polarToCartesian(rScale(BIWHEEL.INNER_CIRCLE_R), r2);

            // Circuit aspects use the color from the serializer (group color)
            let baseColor = asp.color || "gray";
            if (asp.is_approx) {
                baseColor = lightenColor(baseColor, 0.35);
            }

            // For circuit mode, use the circuit group color directly
            const objA = asp.obj_a.replace(/_2$/, "");
            const objB = asp.obj_b.replace(/_2$/, "");
            const startColor = isLuminaryOrPlanet(objA) ? baseColor : lightVariant(baseColor);
            const endColor = isLuminaryOrPlanet(objB) ? baseColor : lightVariant(baseColor);

            const lw = 8;
            let dashArray = "none";
            const style = asp.style || "solid";
            if (style === "dotted") dashArray = "3,3";
            else if (style === "dashed") dashArray = "6,3";

            // Create gradient
            const gradId = `circuit-asp-grad-${gradIdx++}`;
            const grad = defs
                .append("linearGradient")
                .attr("id", gradId)
                .attr("x1", x1).attr("y1", y1)
                .attr("x2", x2).attr("y2", y2)
                .attr("gradientUnits", "userSpaceOnUse");
            grad.append("stop").attr("offset", "0%").attr("stop-color", startColor);
            grad.append("stop").attr("offset", "100%").attr("stop-color", endColor);

            layer
                .append("line")
                .attr("x1", x1).attr("y1", y1)
                .attr("x2", x2).attr("y2", y2)
                .attr("stroke", `url(#${gradId})`)
                .attr("stroke-width", lw)
                .attr("stroke-dasharray", dashArray === "none" ? null : dashArray)
                .attr("class", "aspect-line circuit")
                .attr("data-aspect", asp.aspect)
                .attr("data-obj-a", asp.obj_a)
                .attr("data-obj-b", asp.obj_b)
                .attr("data-circuit", "true");
        });
    }

    function drawBiwheelPlanetLabels(layer, objects, ascDeg, rScale, labelStyle, darkMode, labelR, degreeR, chartId) {
        if (!objects.length) return;

        const color = darkMode ? "#FFFFFF" : "#000000";
        const useGlyphs = (labelStyle || "glyph").toLowerCase() === "glyph";

        // Compute display positions with cluster fan-out
        const positioned = computeClusterPositions(objects);

        positioned.forEach((obj) => {
            const displayRad = degToRad(obj.displayDegree % 360, ascDeg);
            const [gx, gy] = polarToCartesian(rScale(labelR), displayRad);
            const [dx, dy] = polarToCartesian(rScale(degreeR), displayRad);

            const label = useGlyphs ? (obj.glyph || obj.name) : obj.name;
            const degInSign = obj.degree_in_sign !== undefined ? obj.degree_in_sign : Math.floor(obj.longitude % 30);
            let degLabel = `${degInSign}°`;
            if (obj.retrograde) degLabel += " Rx";

            // Planet glyph/name
            layer
                .append("text")
                .attr("x", gx).attr("y", gy)
                .attr("text-anchor", "middle")
                .attr("dominant-baseline", "central")
                .attr("font-size", chartId === "outer" ? "26px" : "28px")
                .attr("fill", color)
                .attr("class", `planet-glyph ${chartId}`)
                .attr("data-object", obj.name)
                .attr("data-chart", chartId)
                .text(label);

            // Degree label
            layer
                .append("text")
                .attr("x", dx).attr("y", dy)
                .attr("text-anchor", "middle")
                .attr("dominant-baseline", "central")
                .attr("font-size", chartId === "outer" ? "20px" : "22px")
                .attr("fill", color)
                .attr("class", `planet-degree ${chartId}`)
                .attr("data-object", obj.name)
                .attr("data-chart", chartId)
                .text(degLabel);

            // Invisible hit area
            layer
                .append("circle")
                .attr("cx", gx).attr("cy", gy)
                .attr("r", 12)
                .attr("fill", "transparent")
                .attr("class", `planet-hitarea ${chartId}`)
                .attr("data-object", obj.name)
                .attr("data-chart", chartId)
                .style("cursor", "pointer");
        });
    }

    function drawBiwheelHeader(svg, headerInner, headerOuter, size, darkMode) {
        const color = darkMode ? "#FFFFFF" : "#000000";
        const subColor = darkMode ? "#CCCCCC" : "#333333";
        const x0 = 14;
        let y = 40;
        const lineHeight = 22;

        // Inner chart name (bold, larger)
        if (headerInner.name) {
            svg.append("text")
                .attr("x", x0).attr("y", y)
                .attr("font-size", "32px")
                .attr("font-weight", "bold")
                .attr("fill", color)
                .attr("class", "chart-header-name inner")
                .text(headerInner.name);
            y += lineHeight;
        }

        // Inner chart date
        if (headerInner.date_line) {
            svg.append("text")
                .attr("x", x0).attr("y", y)
                .attr("font-size", "20px")
                .attr("fill", subColor)
                .attr("class", "chart-header-date inner")
                .text(headerInner.date_line);
            y += lineHeight;
        }

        // Inner chart time
        if (headerInner.time_line) {
            svg.append("text")
                .attr("x", x0).attr("y", y)
                .attr("font-size", "20px")
                .attr("fill", subColor)
                .attr("class", "chart-header-time inner")
                .text(headerInner.time_line);
            y += lineHeight;
        }

        // Inner chart city
        if (headerInner.city) {
            svg.append("text")
                .attr("x", x0).attr("y", y)
                .attr("font-size", "20px")
                .attr("fill", subColor)
                .attr("class", "chart-header-city inner")
                .text(headerInner.city);
        }

        // Outer chart info (on the right side)
        const rightX = size - 14;
        let yRight = 40;

        if (headerOuter.name) {
            svg.append("text")
                .attr("x", rightX).attr("y", yRight)
                .attr("text-anchor", "end")
                .attr("font-size", "32px")
                .attr("font-weight", "bold")
                .attr("fill", color)
                .attr("class", "chart-header-name outer")
                .text(headerOuter.name);
            yRight += lineHeight;
        }

        if (headerOuter.date_line) {
            svg.append("text")
                .attr("x", rightX).attr("y", yRight)
                .attr("text-anchor", "end")
                .attr("font-size", "20px")
                .attr("fill", subColor)
                .attr("class", "chart-header-date outer")
                .text(headerOuter.date_line);
            yRight += lineHeight;
        }

        // Outer chart time
        if (headerOuter.time_line) {
            svg.append("text")
                .attr("x", rightX).attr("y", yRight)
                .attr("text-anchor", "end")
                .attr("font-size", "20px")
                .attr("fill", subColor)
                .attr("class", "chart-header-time outer")
                .text(headerOuter.time_line);
            yRight += lineHeight;
        }

        // Outer chart city
        if (headerOuter.city) {
            svg.append("text")
                .attr("x", rightX).attr("y", yRight)
                .attr("text-anchor", "end")
                .attr("font-size", "20px")
                .attr("fill", subColor)
                .attr("class", "chart-header-city outer")
                .text(headerOuter.city);
        }
    }

    // -----------------------------------------------------------------------
    // Public API
    // -----------------------------------------------------------------------
    return { render, renderBiwheel, degToRad, polarToCartesian, computeClusterPositions, applyHighlights };
})();
