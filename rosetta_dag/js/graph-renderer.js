/**
 * graph-renderer.js — Cytoscape.js setup, layout, expand/collapse, styling.
 *
 * Initializes the interactive DAG using Cytoscape with dagre layout.
 * Module nodes are compound parents; children (classes/functions) are hidden
 * by default and revealed on double-click (expand).
 */

const GraphRenderer = (() => {
    let cy = null;           // Cytoscape instance
    let graphData = null;    // raw graph_data.json
    let expandedModules = new Set();

    // Status → color mapping
    const STATUS_COLORS = {
        "planned": "#565e6b",
        "in-progress": "#d29922",
        "done": "#3fb950",
        "needs-review": "#db6d28",
        "blocked": "#f85149",
    };

    // ──────────────────────────────────────────────────────────
    // Initialization
    // ──────────────────────────────────────────────────────────

    async function init() {
        // Load graph data
        const resp = await fetch("data/graph_data.json?" + Date.now());
        graphData = await resp.json();

        // Build Cytoscape elements — only module nodes + edges initially
        const elements = buildElements();

        // Apply saved positions to elements before Cytoscape init (if available)
        const savedLayout = Persistence.loadLayout();
        if (savedLayout) {
            for (const elem of elements) {
                if (elem.group === "nodes" && savedLayout[elem.data.id]) {
                    elem.position = savedLayout[elem.data.id];
                }
            }
        }

        cy = cytoscape({
            container: document.getElementById("cy"),
            elements: elements,
            minZoom: 0.15,
            maxZoom: 4,
            wheelSensitivity: 0.3,
            boxSelectionEnabled: true,
            style: getCytoscapeStyle(),
            layout: { name: "preset" }, // positions already set above
        });

        if (savedLayout) {
            // Restore saved layout — just fit the view
            cy.fit(cy.nodes(":visible"), 40);
        } else {
            // First run — compute dagre layout
            runLayout("dagre");
        }

        // Wire events
        wireEvents();

        return graphData;
    }

    function buildElements() {
        const elems = [];
        const userData = Persistence.loadAll();
        const moduleNodes = graphData.elements.nodes.filter(n => n.data.type === "module");
        const edges = graphData.elements.edges;

        // Module nodes
        for (const node of moduleNodes) {
            const d = node.data;
            const udata = userData[d.id] || {};
            const gitChanged = GitStatus.isChanged(d.full_path);
            const nodeData = {
                ...d,
                _notes: udata.notes || "",
                _userDesc: udata.description || "",
                _expanded: false,
            };
            // Only set _status and _gitChanged when truthy so Cytoscape selectors work
            if (udata.status) nodeData._status = udata.status;
            if (gitChanged) {
                nodeData._gitChanged = "yes";
                nodeData._gitStats = GitStatus.getStats(d.full_path);
            }
            elems.push({ group: "nodes", data: nodeData });
        }

        // Edges (module → module only)
        for (const edge of edges) {
            elems.push({
                group: "edges",
                data: { ...edge.data },
            });
        }

        return elems;
    }

    // ──────────────────────────────────────────────────────────
    // Cytoscape style
    // ──────────────────────────────────────────────────────────

    function getCytoscapeStyle() {
        return [
            // ── Module nodes ──
            {
                selector: "node[type='module']",
                style: {
                    "label": "data(label)",
                    "text-valign": "center",
                    "text-halign": "center",
                    "font-size": "12px",
                    "font-family": "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
                    "font-weight": "600",
                    "color": "#000",
                    "text-outline-width": 0,
                    "background-color": "data(layer_color)",
                    "background-opacity": 0.9,
                    "shape": "roundrectangle",
                    "width": "label",
                    "height": "label",
                    "padding": "14px",
                    "border-width": 2,
                    "border-color": "data(layer_color)",
                    "border-opacity": 0.6,
                    "text-wrap": "wrap",
                    "text-max-width": "120px",
                    "min-zoomed-font-size": 8,
                },
            },
            // Module with git changes — glow border
            {
                selector: "node[type='module'][_gitChanged]",
                style: {
                    "border-width": 3,
                    "border-color": "#58a6ff",
                    "border-style": "double",
                },
            },
            // Module with status → overlay dot via border color
            {
                selector: "node[type='module'][_status='planned']",
                style: { "border-color": STATUS_COLORS["planned"], "border-width": 3 },
            },
            {
                selector: "node[type='module'][_status='in-progress']",
                style: { "border-color": STATUS_COLORS["in-progress"], "border-width": 3 },
            },
            {
                selector: "node[type='module'][_status='done']",
                style: { "border-color": STATUS_COLORS["done"], "border-width": 3 },
            },
            {
                selector: "node[type='module'][_status='needs-review']",
                style: { "border-color": STATUS_COLORS["needs-review"], "border-width": 3 },
            },
            {
                selector: "node[type='module'][_status='blocked']",
                style: { "border-color": STATUS_COLORS["blocked"], "border-width": 3 },
            },
            // ── Child nodes (class/function) ──
            {
                selector: "node[type='class']",
                style: {
                    "label": "data(label)",
                    "text-valign": "center",
                    "text-halign": "center",
                    "font-size": "10px",
                    "font-family": "'Consolas', 'Courier New', monospace",
                    "color": "#000",
                    "background-color": "data(layer_color)",
                    "background-opacity": 0.7,
                    "shape": "diamond",
                    "width": "label",
                    "height": "label",
                    "padding": "10px",
                    "border-width": 1,
                    "border-color": "#ffffff44",
                    "min-zoomed-font-size": 6,
                },
            },
            {
                selector: "node[type='function']",
                style: {
                    "label": "data(label)",
                    "text-valign": "center",
                    "text-halign": "center",
                    "font-size": "10px",
                    "font-family": "'Consolas', 'Courier New', monospace",
                    "color": "#000",
                    "background-color": "data(layer_color)",
                    "background-opacity": 0.55,
                    "shape": "ellipse",
                    "width": "label",
                    "height": "label",
                    "padding": "8px",
                    "border-width": 1,
                    "border-color": "#ffffff22",
                    "min-zoomed-font-size": 6,
                },
            },
            // ── Edges ──
            {
                selector: "edge",
                style: {
                    "width": 1.5,
                    "line-color": "#555e6b",
                    "target-arrow-color": "#555e6b",
                    "target-arrow-shape": "triangle",
                    "curve-style": "bezier",
                    "arrow-scale": 0.8,
                    "opacity": 0.6,
                },
            },
            // Highlighted edge (when node selected)
            {
                selector: "edge.highlighted",
                style: {
                    "width": 2.5,
                    "line-color": "#58a6ff",
                    "target-arrow-color": "#58a6ff",
                    "opacity": 1,
                },
            },
            // ── Selected node ──
            {
                selector: "node:selected",
                style: {
                    "border-color": "#58a6ff",
                    "border-width": 3,
                    "overlay-color": "#58a6ff",
                    "overlay-opacity": 0.15,
                },
            },
            // ── Dimmed (when searching) ──
            {
                selector: "node.dimmed",
                style: {
                    "opacity": 0.2,
                },
            },
            {
                selector: "edge.dimmed",
                style: {
                    "opacity": 0.08,
                },
            },
            // ── Highlighted node (search match) ──
            {
                selector: "node.search-match",
                style: {
                    "border-color": "#58a6ff",
                    "border-width": 3,
                    "overlay-color": "#58a6ff",
                    "overlay-opacity": 0.12,
                },
            },
            // Child-to-parent edge
            {
                selector: "edge.child-edge",
                style: {
                    "width": 1,
                    "line-color": "#3d444d",
                    "target-arrow-shape": "none",
                    "line-style": "dotted",
                    "opacity": 0.4,
                },
            },
        ];
    }

    // ──────────────────────────────────────────────────────────
    // Layout
    // ──────────────────────────────────────────────────────────

    function runLayout(type) {
        const moduleNodes = cy.nodes("[type='module']");
        let layoutOpts;

        switch (type) {
            case "dagre":
                layoutOpts = {
                    name: "dagre",
                    rankDir: "TB",
                    nodeSep: 60,
                    rankSep: 80,
                    edgeSep: 20,
                    padding: 40,
                    animate: true,
                    animationDuration: 400,
                    fit: true,
                };
                break;
            case "circle":
                layoutOpts = {
                    name: "circle",
                    padding: 60,
                    animate: true,
                    animationDuration: 400,
                    fit: true,
                };
                break;
            case "grid":
                layoutOpts = {
                    name: "grid",
                    padding: 40,
                    rows: Math.ceil(Math.sqrt(moduleNodes.length)),
                    animate: true,
                    animationDuration: 400,
                    fit: true,
                };
                break;
            default:
                layoutOpts = { name: "dagre", rankDir: "TB", padding: 40, fit: true };
        }

        // Only layout visible module nodes (not children)
        const toLayout = cy.nodes(":visible").filter("[type='module']");
        if (toLayout.length === 0) return;

        // We need to layout the whole graph including edges for dagre to work
        const layout = cy.layout({
            ...layoutOpts,
            eles: toLayout.union(cy.edges(":visible").filter(e => {
                return e.source().data("type") === "module" && e.target().data("type") === "module";
            })),
        });

        // Auto-save positions after the layout animation completes
        layout.on("layoutstop", () => saveCurrentLayout());
        layout.run();
    }

    // ──────────────────────────────────────────────────────────
    // Expand / Collapse
    // ──────────────────────────────────────────────────────────

    function expandModule(moduleId) {
        if (expandedModules.has(moduleId)) return;
        expandedModules.add(moduleId);

        const modNode = cy.getElementById(moduleId);
        if (!modNode || modNode.empty()) return;

        // Find child data from graphData
        const children = graphData.elements.nodes.filter(
            n => n.data.parent_module === moduleId
        );

        if (children.length === 0) return;

        const modPos = modNode.position();
        const userData = Persistence.loadAll();

        // Add child nodes arranged in a column near the parent
        const childElems = [];
        children.forEach((child, i) => {
            const udata = userData[child.data.id] || {};
            childElems.push({
                group: "nodes",
                data: {
                    ...child.data,
                    _status: udata.status || null,
                    _notes: udata.notes || "",
                    _userDesc: udata.description || "",
                },
                position: {
                    x: modPos.x + 160,
                    y: modPos.y - (children.length * 15) + (i * 30),
                },
            });
            // Edge from parent to child
            childElems.push({
                group: "edges",
                data: {
                    id: `${moduleId}→child→${child.data.id}`,
                    source: moduleId,
                    target: child.data.id,
                },
                classes: "child-edge",
            });
        });

        cy.add(childElems);
        modNode.data("_expanded", true);
    }

    function collapseModule(moduleId) {
        if (!expandedModules.has(moduleId)) return;
        expandedModules.delete(moduleId);

        // Remove all child nodes + their edges
        const children = cy.nodes().filter(n => n.data("parent_module") === moduleId);
        children.connectedEdges().remove();
        children.remove();

        const modNode = cy.getElementById(moduleId);
        if (modNode && modNode.nonempty()) {
            modNode.data("_expanded", false);
        }
    }

    function toggleModule(moduleId) {
        if (expandedModules.has(moduleId)) {
            collapseModule(moduleId);
        } else {
            expandModule(moduleId);
        }
    }

    function expandAll() {
        const moduleNodes = graphData.elements.nodes.filter(n => n.data.type === "module");
        for (const mod of moduleNodes) {
            expandModule(mod.data.id);
        }
    }

    function collapseAll() {
        for (const mid of [...expandedModules]) {
            collapseModule(mid);
        }
    }

    // ──────────────────────────────────────────────────────────
    // Search / Filter
    // ──────────────────────────────────────────────────────────

    function search(query) {
        cy.elements().removeClass("dimmed search-match");

        if (!query || query.trim().length === 0) return;

        const q = query.toLowerCase().trim();
        const matchIds = new Set();

        cy.nodes().forEach(node => {
            const label = (node.data("label") || "").toLowerCase();
            const id = (node.data("id") || "").toLowerCase();
            const docstring = (node.data("docstring") || "").toLowerCase();
            const methods = (node.data("methods") || []).map(m => m.toLowerCase());

            if (label.includes(q) || id.includes(q) || docstring.includes(q) ||
                methods.some(m => m.includes(q))) {
                matchIds.add(node.id());
                node.addClass("search-match");
            }
        });

        // Dim non-matching
        if (matchIds.size > 0) {
            cy.nodes().forEach(node => {
                if (!matchIds.has(node.id())) node.addClass("dimmed");
            });
            cy.edges().forEach(edge => {
                if (!matchIds.has(edge.source().id()) && !matchIds.has(edge.target().id())) {
                    edge.addClass("dimmed");
                }
            });
        }
    }

    function clearSearch() {
        cy.elements().removeClass("dimmed search-match");
    }

    function filterByLayers(activeLayers) {
        cy.nodes("[type='module']").forEach(node => {
            const layer = node.data("layer");
            if (activeLayers.has(layer)) {
                node.style("display", "element");
            } else {
                node.style("display", "none");
            }
        });
        // Also hide/show edges based on visibility
        cy.edges().forEach(edge => {
            const srcVisible = edge.source().style("display") !== "none";
            const tgtVisible = edge.target().style("display") !== "none";
            edge.style("display", (srcVisible && tgtVisible) ? "element" : "none");
        });
    }

    // ──────────────────────────────────────────────────────────
    // Events
    // ──────────────────────────────────────────────────────────

    function wireEvents() {
        // Click → select, show detail
        cy.on("tap", "node", (evt) => {
            const node = evt.target;
            highlightConnected(node);
            if (typeof Sidebar !== "undefined") {
                Sidebar.showNode(node);
            }
            if (typeof App !== "undefined") {
                App.addBreadcrumb(node.data("id"), node.data("label"));
            }
        });

        // Double-click → expand/collapse module
        cy.on("dbltap", "node[type='module']", (evt) => {
            toggleModule(evt.target.id());
        });

        // Click background → deselect
        cy.on("tap", (evt) => {
            if (evt.target === cy) {
                cy.elements().removeClass("highlighted");
                if (typeof Sidebar !== "undefined") {
                    Sidebar.hide();
                }
            }
        });

        // Right-click → context menu
        cy.on("cxttap", "node", (evt) => {
            evt.originalEvent.preventDefault();
            if (typeof App !== "undefined") {
                App.showContextMenu(evt);
            }
        });

        // Hover → tooltip (simple title approach)
        cy.on("mouseover", "node", (evt) => {
            const node = evt.target;
            const doc = node.data("docstring") || "";
            if (doc) {
                node.scratch("_prevTitle", node.style("label"));
            }
        });

        // Box selection → show selection toolbar
        cy.on("select", () => updateSelectionToolbar());
        cy.on("unselect", () => updateSelectionToolbar());

        // Drag end → auto-save positions silently
        cy.on("dragfree", "node[type='module']", () => {
            saveCurrentLayout();
        });
    }

    function highlightConnected(node) {
        cy.elements().removeClass("highlighted");
        const connected = node.connectedEdges();
        connected.addClass("highlighted");
    }

    function updateSelectionToolbar() {
        const selected = cy.nodes(":selected");
        const toolbar = document.getElementById("selection-toolbar");
        const countEl = document.getElementById("selection-count");

        if (selected.length > 1) {
            toolbar.classList.remove("hidden");
            countEl.textContent = `${selected.length} selected`;
        } else {
            toolbar.classList.add("hidden");
        }
    }

    // ──────────────────────────────────────────────────────────
    // Git status highlighting
    // ──────────────────────────────────────────────────────────

    function applyGitStatus() {
        cy.nodes("[type='module']").forEach(node => {
            const fp = node.data("full_path");
            const changed = GitStatus.isChanged(fp);
            if (changed) {
                node.data("_gitChanged", "yes");
                node.data("_gitStats", GitStatus.getStats(fp));
            } else {
                node.removeData("_gitChanged");
                node.removeData("_gitStats");
            }
        });
    }

    // ──────────────────────────────────────────────────────────
    // Update node user data (called from sidebar)
    // ──────────────────────────────────────────────────────────

    function updateNodeStatus(nodeId, status) {
        const node = cy.getElementById(nodeId);
        if (node && node.nonempty()) {
            if (status) {
                node.data("_status", status);
            } else {
                node.removeData("_status");
            }
        }
        Persistence.setNode(nodeId, { status });
    }

    function updateNodeNotes(nodeId, notes) {
        const node = cy.getElementById(nodeId);
        if (node && node.nonempty()) {
            node.data("_notes", notes);
        }
        Persistence.setNode(nodeId, { notes });
    }

    function updateNodeDescription(nodeId, description) {
        const node = cy.getElementById(nodeId);
        if (node && node.nonempty()) {
            node.data("_userDesc", description);
        }
        Persistence.setNode(nodeId, { description });
    }

    // ──────────────────────────────────────────────────────────
    // Public helpers
    // ──────────────────────────────────────────────────────────

    function focusNode(nodeId) {
        const node = cy.getElementById(nodeId);
        if (node && node.nonempty()) {
            cy.animate({ center: { eles: node }, zoom: 1.5 }, { duration: 300 });
            node.select();
            highlightConnected(node);
            if (typeof Sidebar !== "undefined") {
                Sidebar.showNode(node);
            }
        }
    }

    function zoomIn() { cy.zoom({ level: cy.zoom() * 1.3, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } }); }
    function zoomOut() { cy.zoom({ level: cy.zoom() / 1.3, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } }); }
    function fit() { cy.fit(cy.nodes(":visible"), 40); }

    function getSelectedModules() {
        return cy.nodes(":selected").filter("[type='module']").map(n => n.data());
    }

    function getGraphData() { return graphData; }
    function getCy() { return cy; }

    function getModuleNodes() {
        return cy.nodes("[type='module']");
    }

    function exportSelectionAsMarkdown() {
        const selected = cy.nodes(":selected");
        if (selected.length === 0) return "";

        let md = "## Selected Rosetta Modules\n\n";
        selected.forEach(node => {
            const d = node.data();
            md += `### ${d.label} (${d.layer})\n`;
            md += `- Path: \`${d.full_path}\`\n`;
            md += `- Lines: ${d.line_count || "?"}\n`;
            if (d._status) md += `- Status: ${d._status}\n`;
            if (d._notes) md += `- Notes: ${d._notes}\n`;
            if (d.docstring) md += `- Description: ${d.docstring}\n`;

            // Connected modules
            const incoming = node.incomers("node[type='module']").map(n => n.data("label"));
            const outgoing = node.outgoers("node[type='module']").map(n => n.data("label"));
            if (incoming.length) md += `- Imported by: ${incoming.join(", ")}\n`;
            if (outgoing.length) md += `- Imports: ${outgoing.join(", ")}\n`;
            md += "\n";
        });

        return md;
    }

    // ──────────────────────────────────────────────────────────
    // Layout save / restore
    // ──────────────────────────────────────────────────────────

    /** Capture positions of all visible module nodes and persist them. */
    function saveCurrentLayout() {
        const positions = {};
        cy.nodes("[type='module']").forEach(node => {
            const pos = node.position();
            positions[node.id()] = { x: pos.x, y: pos.y };
        });
        Persistence.saveLayout(positions);
        return positions;
    }

    /** Clear the saved layout and revert to the default dagre layout. */
    function clearSavedLayout() {
        Persistence.clearLayout();
        runLayout("dagre");
    }

    return {
        init, runLayout, expandModule, collapseModule, toggleModule,
        expandAll, collapseAll, search, clearSearch, filterByLayers,
        applyGitStatus, updateNodeStatus, updateNodeNotes, updateNodeDescription,
        focusNode, zoomIn, zoomOut, fit, getSelectedModules, getGraphData, getCy,
        getModuleNodes, exportSelectionAsMarkdown, STATUS_COLORS,
        saveCurrentLayout, clearSavedLayout,
    };
})();
