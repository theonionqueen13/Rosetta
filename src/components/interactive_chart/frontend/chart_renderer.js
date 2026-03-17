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
            const midRad = degToRad(sign.start_degree + 15, ascDeg);
            const [gx, gy] = polarToCartesian(rScale(R_ZODIAC_GLYPH), midRad);
            layer
                .append("text")
                .attr("x", gx).attr("y", gy)
                .attr("text-anchor", "middle")
                .attr("dominant-baseline", "central")
                .attr("font-size", "14px")
                .attr("font-weight", "bold")
                .attr("fill", sign.glyph_color)
                .attr("class", "zodiac-glyph")
                .attr("data-sign", sign.name)
                .text(sign.glyph);
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
                .attr("stroke-width", 1.2)
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
                .attr("font-size", "8px")
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
            .attr("stroke-width", 1)
            .attr("class", "degree-circle");

        // Tick marks
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
            let lw = isMajor ? 2 : 1;
            const aspectName = (asp.aspect || "").toLowerCase();
            if (aspectName === "quincunx" || aspectName === "sesquisquare") {
                lw = 1;
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
                .attr("data-conductance", asp.conductance || "")
                .attr("data-transmitted-power", asp.transmitted_power || "")
                .attr("data-friction-heat", asp.friction_heat || "")
                .attr("data-is-arc-hazard", asp.is_arc_hazard || false);
        });
    }

    // -----------------------------------------------------------------------
    // Compass rose
    // -----------------------------------------------------------------------
    function drawCompassRose(layer, objects, ascDeg, rScale) {
        const posMap = {};
        objects.forEach((o) => {
            posMap[o.name] = o.longitude;
        });

        const nodal = "#800080";
        const axisColor = "#4E83AF";
        const r = rScale(R_ASPECT);

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
                .attr("stroke", axisColor).attr("stroke-width", 2)
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
                .attr("stroke", axisColor).attr("stroke-width", 2)
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
                .attr("id", "arrow-nn")
                .attr("viewBox", "0 0 10 10")
                .attr("refX", 10).attr("refY", 5)
                .attr("markerWidth", 8).attr("markerHeight", 8)
                .attr("orient", "auto-start-reverse")
                .append("path")
                .attr("d", "M 0 0 L 10 5 L 0 10 Z")
                .attr("fill", nodal);

            layer.append("line")
                .attr("x1", sx).attr("y1", sy)
                .attr("x2", nx).attr("y2", ny)
                .attr("stroke", nodal).attr("stroke-width", 4)
                .attr("marker-end", "url(#arrow-nn)")
                .attr("class", "compass-nodal");

            // SN dot
            layer.append("circle")
                .attr("cx", sx).attr("cy", sy)
                .attr("r", 4)
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
            .attr("stroke-width", 1.5)
            .attr("class", "center-earth");
        g.append("line")
            .attr("x1", -r).attr("y1", 0)
            .attr("x2", r).attr("y2", 0)
            .attr("stroke", color).attr("stroke-width", 1)
            .attr("class", "center-earth");
        g.append("line")
            .attr("x1", 0).attr("y1", -r)
            .attr("x2", 0).attr("y2", r)
            .attr("stroke", color).attr("stroke-width", 1)
            .attr("class", "center-earth");
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
                .attr("font-size", "11px")
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
                .attr("font-size", "7px")
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
                .attr("stroke-width", 1.2)
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
    // Public API
    // -----------------------------------------------------------------------
    return { render, degToRad, polarToCartesian, computeClusterPositions, applyHighlights };
})();
