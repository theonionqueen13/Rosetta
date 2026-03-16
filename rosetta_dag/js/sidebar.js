/**
 * sidebar.js — Left sidebar (layer filters, module list) and
 *              right detail panel (status, notes, description, edges).
 */

const Sidebar = (() => {
    let _currentNodeId = null;

    // ──────────────────────────────────────────────────────────
    // Left sidebar
    // ──────────────────────────────────────────────────────────

    function initLeftSidebar(graphData) {
        buildLayerFilters(graphData);
        buildModuleList(graphData);
        updateStats(graphData);
        wireSearchBox();
    }

    function buildLayerFilters(graphData) {
        const container = document.getElementById("layer-filters");
        const layers = graphData.metadata.layers;
        const moduleNodes = graphData.elements.nodes.filter(n => n.data.type === "module");

        // Count per layer
        const counts = {};
        for (const node of moduleNodes) {
            const layer = node.data.layer;
            counts[layer] = (counts[layer] || 0) + 1;
        }

        container.innerHTML = "";
        for (const [layer, info] of Object.entries(layers)) {
            if (!counts[layer]) continue; // skip layers with no modules
            const div = document.createElement("div");
            div.className = "layer-filter";
            div.innerHTML = `
                <input type="checkbox" id="layer-${layer}" checked data-layer="${layer}">
                <span class="layer-dot" style="background:${info.color};"></span>
                <span class="layer-label">${layer}</span>
                <span class="layer-count">${counts[layer] || 0}</span>
            `;
            container.appendChild(div);
        }

        // Wire filter changes
        container.addEventListener("change", () => {
            const active = new Set();
            container.querySelectorAll("input:checked").forEach(cb => {
                active.add(cb.dataset.layer);
            });
            GraphRenderer.filterByLayers(active);
        });
    }

    function buildModuleList(graphData) {
        const container = document.getElementById("module-list");
        const moduleNodes = graphData.elements.nodes
            .filter(n => n.data.type === "module")
            .sort((a, b) => a.data.label.localeCompare(b.data.label));

        const userData = Persistence.loadAll();
        container.innerHTML = "";

        const countEl = document.getElementById("module-count");
        countEl.textContent = `(${moduleNodes.length})`;

        for (const node of moduleNodes) {
            const d = node.data;
            const udata = userData[d.id] || {};
            const statusColor = GraphRenderer.STATUS_COLORS[udata.status] || "transparent";

            const div = document.createElement("div");
            div.className = "module-list-item";
            div.dataset.moduleId = d.id;
            div.innerHTML = `
                <span class="status-dot" style="background:${statusColor};border:1px solid ${statusColor === 'transparent' ? 'var(--border)' : statusColor};"></span>
                <span class="layer-dot" style="background:${d.layer_color};width:6px;height:6px;"></span>
                <span class="mod-name" title="${d.id}">${d.label}</span>
                <span class="mod-lines">${d.line_count}L</span>
            `;
            div.addEventListener("click", () => {
                GraphRenderer.focusNode(d.id);
            });
            container.appendChild(div);
        }
    }

    function refreshModuleList() {
        const graphData = GraphRenderer.getGraphData();
        if (graphData) buildModuleList(graphData);
    }

    function updateStats(graphData) {
        const meta = graphData.metadata;
        document.getElementById("stat-modules").textContent = `${meta.module_count} modules`;
        document.getElementById("stat-edges").textContent = `${meta.edge_count} edges`;
        document.getElementById("stat-functions").textContent = `${meta.child_count} items`;
    }

    function wireSearchBox() {
        const searchBox = document.getElementById("search-box");
        let debounce = null;

        searchBox.addEventListener("input", () => {
            clearTimeout(debounce);
            debounce = setTimeout(() => {
                const q = searchBox.value.trim();
                if (q.length === 0) {
                    GraphRenderer.clearSearch();
                } else {
                    GraphRenderer.search(q);
                }
            }, 200);
        });

        searchBox.addEventListener("keydown", (e) => {
            if (e.key === "Escape") {
                searchBox.value = "";
                GraphRenderer.clearSearch();
            }
        });
    }

    // ──────────────────────────────────────────────────────────
    // Right detail panel
    // ──────────────────────────────────────────────────────────

    function showNode(cyNode) {
        const panel = document.getElementById("detail-panel");
        const content = document.getElementById("detail-content");
        const d = cyNode.data();
        _currentNodeId = d.id;

        panel.classList.add("open");

        const isModule = d.type === "module";
        const userData = Persistence.getNode(d.id);
        const absPath = d.abs_path || "";
        const vsCodeUri = absPath ? `vscode://file/${absPath.replace(/\\/g, "/")}` : "";
        const lineLink = d.line_start ? `${vsCodeUri}:${d.line_start}` : vsCodeUri;

        // Git badge
        let gitBadgeHtml = "";
        if (isModule && d._gitChanged === "yes") {
            const stats = d._gitStats || {};
            gitBadgeHtml = `
                <div class="git-badge">
                    ⚡ Git changed
                    ${stats.additions != null ? `<span class="git-add">+${stats.additions}</span>` : ""}
                    ${stats.deletions != null ? `<span class="git-del">-${stats.deletions}</span>` : ""}
                </div>
            `;
        }

        // Incoming / outgoing edges
        let edgesHtml = "";
        if (isModule) {
            const cy = GraphRenderer.getCy();
            const node = cy.getElementById(d.id);
            const incomers = node.incomers("node[type='module']");
            const outgoers = node.outgoers("node[type='module']");

            if (incomers.length > 0) {
                edgesHtml += `<div class="edge-list"><h4>Imported by (${incomers.length})</h4>`;
                incomers.forEach(n => {
                    edgesHtml += `<div class="edge-item" data-node-id="${n.id()}">
                        <span class="edge-arrow">←</span> ${n.data("label")}
                    </div>`;
                });
                edgesHtml += `</div>`;
            }
            if (outgoers.length > 0) {
                edgesHtml += `<div class="edge-list"><h4>Imports (${outgoers.length})</h4>`;
                outgoers.forEach(n => {
                    edgesHtml += `<div class="edge-item" data-node-id="${n.id()}">
                        <span class="edge-arrow">→</span> ${n.data("label")}
                    </div>`;
                });
                edgesHtml += `</div>`;
            }
        }

        // Children list (for modules)
        let childrenHtml = "";
        if (isModule && d.child_ids && d.child_ids.length > 0) {
            const graphData = GraphRenderer.getGraphData();
            const children = graphData.elements.nodes.filter(n => n.data.parent_module === d.id);
            const classes = children.filter(c => c.data.type === "class");
            const funcs = children.filter(c => c.data.type === "function");

            childrenHtml += `<div class="children-section">`;
            childrenHtml += `<h4>Contents (${children.length})</h4>`;

            if (classes.length > 0) {
                for (const c of classes) {
                    const methods = (c.data.methods || []).join(", ");
                    childrenHtml += `<div class="child-item" data-child-id="${c.data.id}">
                        <span class="child-icon">◆</span>
                        <span><strong>${c.data.label}</strong>${methods ? ` — ${methods}` : ""}</span>
                    </div>`;
                }
            }
            if (funcs.length > 0) {
                for (const f of funcs) {
                    const decs = (f.data.decorators || []).map(d => `@${d}`).join(" ");
                    childrenHtml += `<div class="child-item" data-child-id="${f.data.id}">
                        <span class="child-icon">●</span>
                        <span>${f.data.label}()${decs ? ` ${decs}` : ""}</span>
                    </div>`;
                }
            }
            childrenHtml += `</div>`;
        }

        // Methods list (for class child nodes)
        let methodsHtml = "";
        if (d.type === "class" && d.methods && d.methods.length > 0) {
            methodsHtml += `<div class="children-section"><h4>Methods (${d.methods.length})</h4>`;
            for (const m of d.methods) {
                methodsHtml += `<div class="child-item"><span class="child-icon">●</span><span>${m}()</span></div>`;
            }
            methodsHtml += `</div>`;
        }

        // Quick stats
        let statsHtml = "";
        if (isModule) {
            statsHtml = `
                <div class="quick-stats">
                    <div class="stat-card"><span class="stat-value">${d.line_count || 0}</span><span class="stat-label">Lines</span></div>
                    <div class="stat-card"><span class="stat-value">${d.func_count || 0}</span><span class="stat-label">Functions</span></div>
                    <div class="stat-card"><span class="stat-value">${d.class_count || 0}</span><span class="stat-label">Classes</span></div>
                    <div class="stat-card"><span class="stat-value">${(d.child_ids || []).length}</span><span class="stat-label">Total items</span></div>
                </div>
            `;
        }

        // Build the full HTML
        content.innerHTML = `
            <div class="detail-header">
                <h2>${d.label}</h2>
                <button class="detail-close" id="detail-close-btn">✕</button>
            </div>

            <div class="detail-path">
                ${isModule
                ? `<a href="${vsCodeUri}" title="Open in VS Code">${d.full_path}</a>`
                : `<a href="${lineLink}" title="Open in VS Code">${d.parent_module} : line ${d.line_start || "?"}</a>`
            }
            </div>

            <span class="layer-badge" style="background:${d.layer_color};">${d.layer}</span>

            ${gitBadgeHtml}

            ${statsHtml}

            <!-- Status selector -->
            <div class="status-selector">
                <label>Development Status</label>
                <div class="status-options">
                    ${["planned", "in-progress", "done", "needs-review", "blocked"].map(s =>
                `<button class="status-btn ${(userData.status || d._status) === s ? 'active' : ''}"
                                 data-status="${s}">${s}</button>`
            ).join("")}
                </div>
            </div>

            <!-- Notes -->
            <div class="notes-section">
                <label>Notes</label>
                <textarea id="node-notes" placeholder="Add development notes…">${userData.notes || d._notes || ""}</textarea>
            </div>

            <!-- Description -->
            <div class="desc-section">
                <label>Description</label>
                <div class="desc-text">${userData.description || d._userDesc || d.docstring || "<em>No description</em>"}</div>
            </div>

            ${edgesHtml}
            ${childrenHtml}
            ${methodsHtml}

            <!-- Copy reference button -->
            <div style="margin-top:16px;">
                <button class="btn btn-sm" id="btn-copy-ref">📋 Copy Reference for Copilot</button>
            </div>
        `;

        // Wire events
        document.getElementById("detail-close-btn").addEventListener("click", hide);

        // Status buttons
        content.querySelectorAll(".status-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                const status = btn.dataset.status;
                content.querySelectorAll(".status-btn").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                GraphRenderer.updateNodeStatus(d.id, status);
                refreshModuleList();
            });
        });

        // Notes auto-save on blur
        const notesEl = document.getElementById("node-notes");
        notesEl.addEventListener("blur", () => {
            GraphRenderer.updateNodeNotes(d.id, notesEl.value);
        });

        // Copy reference
        document.getElementById("btn-copy-ref").addEventListener("click", () => {
            const ref = isModule
                ? `[${d.full_path}] — ${d.layer} layer, ${d.line_count} lines`
                : `[${d.parent_module}] ${d.label}() — line ${d.line_start}`;
            navigator.clipboard.writeText(ref).then(() => {
                App.showToast("Copied: " + ref);
            });
        });

        // Edge items → navigate
        content.querySelectorAll(".edge-item").forEach(item => {
            item.addEventListener("click", () => {
                const targetId = item.dataset.nodeId;
                GraphRenderer.focusNode(targetId);
            });
        });

        // Child items → expand and focus (or just show info)
        content.querySelectorAll(".child-item").forEach(item => {
            item.addEventListener("click", () => {
                const childId = item.dataset.childId;
                if (childId) {
                    // Ensure module is expanded
                    GraphRenderer.expandModule(d.id);
                    setTimeout(() => GraphRenderer.focusNode(childId), 200);
                }
            });
        });
    }

    function hide() {
        document.getElementById("detail-panel").classList.remove("open");
        _currentNodeId = null;
    }

    function getCurrentNodeId() { return _currentNodeId; }

    return { initLeftSidebar, showNode, hide, getCurrentNodeId, refreshModuleList };
})();
