/**
 * flow-renderer.js — Cytoscape flowchart renderer for thought_flow.json.
 *
 * Key features:
 * - Tabs (flows) driven by "tabs" in the JSON
 * - Chart mode filtering (dimming irrelevant nodes/edges)
 * - Status coloring (not-built/in-progress/done)
 * - Click node to open source file via vscode:// deep link
 */

const FlowRenderer = (() => {
    let cy = null;
    let graphData = null;
    let activeTab = null;
    let activeModes = new Set();

    const STATUS_COLORS = {
        "planned": "#565e6b",
        "not-built": "#565e6b",
        "in-progress": "#d29922",
        "done": "#3fb950",
        "needs-review": "#db6d28",
        "blocked": "#f85149",
    };

    const TYPE_SHAPES = {
        "process": "roundrectangle",
        "decision": "diamond",
        "input": "roundrectangle",
        "output": "roundrectangle",
        "gate": "hexagon",
        "terminal": "ellipse",
    };

    function getStyle() {
        return [
            {
                selector: "node",
                style: {
                    "background-color": "#ffffff",
                    "border-width": 1,
                    "border-color": "#555",
                    "label": "data(label)",
                    "text-wrap": "wrap",
                    "text-max-width": 260,
                    "text-margin-x": 10,
                    "text-margin-y": 8,
                    "font-size": 12,
                    "font-weight": "bold",
                    "text-valign": "center",
                    "text-halign": "center",
                    "width": "label",
                    "height": "label",
                    "min-width": 220,
                    "shape": "data(shape)",
                    "padding": "14px",
                    "pie-size": "32%",
                    "pie-1-background-color": "data(statusColor)",
                    "pie-1-background-size": "20%",
                    "pie-1-background-opacity": 0.9,
                    "pie-2-background-color": "#ffffff",
                    "pie-2-background-size": "0%",
                },
            },
            {
                selector: "edge",
                style: {
                    "curve-style": "bezier",
                    "target-arrow-shape": "triangle",
                    "line-color": "#999",
                    "target-arrow-color": "#999",
                    "width": 2,
                    "label": "data(label)",
                    "font-size": 9,
                    "text-rotation": "autorotate",
                },
            },
            {
                selector: ".dimmed",
                style: {
                    "opacity": 0.2,
                },
            },
            {
                selector: ".hidden",
                style: {
                    "display": "none",
                },
            },
        ];
    }

    function loadData() {
        // fetch() fails on file:// protocol — fall back to sync XHR
        if (window.location.protocol === "file:") {
            return new Promise((resolve, reject) => {
                const xhr = new XMLHttpRequest();
                xhr.open("GET", "data/thought_flow.json", true);
                xhr.onload = () => {
                    if (xhr.status === 0 || xhr.status === 200) {
                        try { resolve(JSON.parse(xhr.responseText)); }
                        catch (e) { reject(e); }
                    } else { reject(new Error("XHR status " + xhr.status)); }
                };
                xhr.onerror = () => reject(new Error("XHR failed — try serving with: python -m http.server 8080"));
                xhr.send();
            });
        }
        return fetch("data/thought_flow.json?" + Date.now()).then((resp) => resp.json());
    }

    function buildElements() {
        const nodes = graphData.nodes.map((n) => {
            const modeList = Array.isArray(n.chart_modes) ? n.chart_modes : [];
            const status = n.status || "planned";
            const shape = TYPE_SHAPES[n.type] || "roundrectangle";
            return {
                group: "nodes",
                data: {
                    id: n.id,
                    label: n.label,
                    tabs: n.tabs || [],
                    chart_modes: modeList,
                    status: status,
                    statusColor: STATUS_COLORS[status] || STATUS_COLORS.planned,
                    source_file: n.source_file || null,
                    source_line: n.source_line || null,
                    description: n.description || "",
                    shape: shape,
                },
            };
        });

        const edges = graphData.edges.map((e) => ({
            group: "edges",
            data: {
                id: e.id,
                source: e.source,
                target: e.target,
                label: e.label || "",
                chart_modes: Array.isArray(e.chart_modes) ? e.chart_modes : [],
            },
        }));

        return nodes.concat(edges);
    }

    function applyTabFilter() {
        if (!activeTab) return;

        const tabNodes = new Set();
        graphData.nodes.forEach((n) => {
            if (Array.isArray(n.tabs) && n.tabs.includes(activeTab)) {
                tabNodes.add(n.id);
            }
        });

        cy.nodes().forEach((node) => {
            const shouldShow = tabNodes.has(node.id());
            node.toggleClass("hidden", !shouldShow);
        });

        cy.edges().forEach((edge) => {
            const srcVisible = !cy.getElementById(edge.data("source")).hasClass("hidden");
            const tgtVisible = !cy.getElementById(edge.data("target")).hasClass("hidden");
            edge.toggleClass("hidden", !(srcVisible && tgtVisible));
        });

        applyModeFilter();
    }

    function applyModeFilter() {
        if (!activeTab) return;
        if (activeModes.size === 0) {
            cy.nodes().removeClass("dimmed");
            cy.edges().removeClass("dimmed");
            return;
        }

        cy.nodes().forEach((node) => {
            if (node.hasClass("hidden")) return;
            const chartModes = node.data("chart_modes") || [];
            const matches = chartModes.length === 0 || chartModes.some((m) => activeModes.has(m));
            node.toggleClass("dimmed", !matches);
        });

        cy.edges().forEach((edge) => {
            if (edge.hasClass("hidden")) return;
            const chartModes = edge.data("chart_modes") || [];
            const matches = chartModes.length === 0 || chartModes.some((m) => activeModes.has(m));
            edge.toggleClass("dimmed", !matches);
        });
    }

    function layoutGraph() {
        cy.layout({
            name: "dagre",
            rankDir: graphData.tabs.find((t) => t.id === activeTab)?.layout_direction || "TB",
            nodeSep: 50,
            edgeSep: 20,
            rankSep: 80,
            animate: true,
            animationDuration: 300,
        }).run();
    }

    function initCytoscape(elements) {
        cy = cytoscape({
            container: document.getElementById("cy"),
            elements,
            style: getStyle(),
            minZoom: 0.15,
            maxZoom: 3,
            wheelSensitivity: 0.3,
            boxSelectionEnabled: true,
        });

        cy.on("tap", "node", (evt) => {
            const node = evt.target;
            const file = node.data("source_file");
            const line = node.data("source_line");
            if (file) {
                const link = `vscode://file/${file}:${line || 1}`;
                window.open(link, "_blank");
            }
            FlowRenderer.showNodeDetails(node.data());
        });

        cy.on("tap", (evt) => {
            if (evt.target === cy) {
                document.getElementById("node-detail-panel").innerHTML = '<p style="color:var(--text-muted);">Click a node to view details and source link.</p>';
            }
        });
    }

    function setActiveTab(tabId) {
        activeTab = tabId;
        applyTabFilter();
        layoutGraph();
    }

    function toggleMode(mode) {
        if (activeModes.has(mode)) {
            activeModes.delete(mode);
        } else {
            activeModes.add(mode);
        }
        applyModeFilter();
    }

    function saveLayout() {
        const positions = {};
        cy.nodes().forEach((node) => {
            positions[node.id()] = node.position();
        });
        Persistence.saveLayout(positions);
    }

    function resetLayout() {
        Persistence.clearLayout();
        layoutGraph();
    }

    function showNodeDetails(data) {
        const details = document.getElementById("node-detail-panel");
        const lines = [];
        lines.push(`<strong>${data.label}</strong>`);
        lines.push(`<div style="margin-top:0.4em;font-size:10px;color:#888;">status: <span style="color:${STATUS_COLORS[data.status] || '#888'}">${data.status}</span></div>`);
        if (data.description) {
            lines.push(`<div style="margin-top:0.5em;">${data.description}</div>`);
        }
        if (data.source_file) {
            const line = data.source_line || 1;
            const link = `vscode://file/${data.source_file}:${line}`;
            lines.push(`<div style="margin-top:0.75em;font-size:11px;">Source: <a href="${link}" target="_blank">${data.source_file}:${line}</a></div>`);
        }
        details.innerHTML = lines.join("");
    }

    function init() {
        loadData().then((data) => {
            graphData = data;
            console.log("[ThoughtFlow] Loaded", data.nodes.length, "nodes,", data.edges.length, "edges,", data.tabs.length, "tabs");
            const elements = buildElements();
            initCytoscape(elements);

            const tabContainer = document.getElementById("tab-container");
            tabContainer.innerHTML = "";
            graphData.tabs.forEach((tab) => {
                const button = document.createElement("button");
                button.className = "btn btn-sm";
                button.innerText = tab.label;
                button.addEventListener("click", () => {
                    setActiveTab(tab.id);
                    document.querySelectorAll("#tab-container .btn").forEach((b) => b.classList.remove("btn-primary"));
                    button.classList.add("btn-primary");
                });
                tabContainer.appendChild(button);
            });

            const modeContainer = document.getElementById("mode-container");
            const modes = ["natal", "transit", "synastry", "solar_return", "relocation", "cycle", "timing_predict"];
            modes.forEach((mode) => {
                const btn = document.createElement("button");
                btn.className = "btn btn-sm";
                btn.innerText = mode;
                btn.addEventListener("click", () => {
                    btn.classList.toggle("btn-primary");
                    toggleMode(mode);
                });
                modeContainer.appendChild(btn);
            });

            document.getElementById("btn-refresh").addEventListener("click", () => {
                window.location.reload();
            });

            document.getElementById("btn-save-layout").addEventListener("click", saveLayout);
            document.getElementById("btn-reset-layout").addEventListener("click", resetLayout);

            const tb = document.getElementById("search-box");
            tb.addEventListener("input", () => {
                const q = tb.value.toLowerCase().trim();
                cy.nodes().forEach((node) => {
                    const matches = node.data("label").toLowerCase().includes(q);
                    node.toggleClass("dimmed", q.length > 0 && !matches);
                });
            });

            // Activate first tab by default
            if (graphData.tabs.length > 0) {
                setActiveTab(graphData.tabs[0].id);
                document.querySelectorAll("#tab-container .btn")[0].classList.add("btn-primary");
            }
        }).catch((err) => {
            console.error("[ThoughtFlow] Failed to load data:", err);
            const cy_el = document.getElementById("cy");
            if (cy_el) cy_el.innerHTML = '<p style="padding:2em;color:red;">Failed to load thought_flow.json.<br>Try: <code>cd rosetta_dag && python -m http.server 8080</code><br>Then open http://localhost:8080/thought_flow.html</p>';
        });
    }

    return {
        init,
        showNodeDetails,
    };
})();

window.addEventListener("load", () => {
    FlowRenderer.init();
});
