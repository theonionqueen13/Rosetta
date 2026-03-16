/**
 * app.js — Main orchestrator.
 *
 * Boots up all subsystems, wires header buttons, keyboard shortcuts,
 * context menu, breadcrumb trail, and theme toggling.
 */

const App = (() => {
    let breadcrumbs = [];

    // ──────────────────────────────────────────────────────────
    // Boot
    // ──────────────────────────────────────────────────────────

    async function boot() {
        console.log("Rosetta DAG: booting…");

        // Apply saved theme
        const theme = Persistence.getTheme();
        if (theme === "light") document.documentElement.classList.add("light-theme");

        // Load git status (non-blocking, best-effort)
        await GitStatus.load();

        // Initialize graph
        const graphData = await GraphRenderer.init();

        // Apply git highlights
        GraphRenderer.applyGitStatus();

        // Build left sidebar
        Sidebar.initLeftSidebar(graphData);

        // Wire all buttons & shortcuts
        wireHeaderButtons();
        wireKeyboardShortcuts();
        wireSelectionToolbar();

        console.log("Rosetta DAG: ready ✓");
    }

    // ──────────────────────────────────────────────────────────
    // Header buttons
    // ──────────────────────────────────────────────────────────

    function wireHeaderButtons() {
        // Theme toggle
        document.getElementById("btn-toggle-theme").addEventListener("click", () => {
            document.documentElement.classList.toggle("light-theme");
            const isLight = document.documentElement.classList.contains("light-theme");
            Persistence.setTheme(isLight ? "light" : "dark");
        });

        // Sidebar toggle
        document.getElementById("btn-toggle-sidebar").addEventListener("click", () => {
            document.getElementById("left-sidebar").classList.toggle("collapsed");
        });

        // Zoom controls
        document.getElementById("btn-zoom-in").addEventListener("click", () => GraphRenderer.zoomIn());
        document.getElementById("btn-zoom-out").addEventListener("click", () => GraphRenderer.zoomOut());
        document.getElementById("btn-fit").addEventListener("click", () => GraphRenderer.fit());

        // Layout controls
        document.getElementById("btn-layout-dagre").addEventListener("click", () => GraphRenderer.runLayout("dagre"));
        document.getElementById("btn-layout-circle").addEventListener("click", () => GraphRenderer.runLayout("circle"));
        document.getElementById("btn-layout-grid").addEventListener("click", () => GraphRenderer.runLayout("grid"));
        document.getElementById("btn-expand-all").addEventListener("click", () => GraphRenderer.expandAll());
        document.getElementById("btn-collapse-all").addEventListener("click", () => GraphRenderer.collapseAll());

        // Export / Import / Reset
        document.getElementById("btn-export-data").addEventListener("click", () => {
            Persistence.exportToFile();
            showToast("User data exported ✓");
        });

        document.getElementById("btn-import-data").addEventListener("click", () => {
            document.getElementById("import-file-input").click();
        });

        document.getElementById("import-file-input").addEventListener("change", async (e) => {
            const file = e.target.files[0];
            if (!file) return;
            try {
                await Persistence.importFromFile(file);
                showToast("User data imported ✓ — refreshing…");
                setTimeout(() => location.reload(), 500);
            } catch (err) {
                showToast("Import failed: " + err.message);
            }
            e.target.value = ""; // reset
        });

        document.getElementById("btn-reset-data").addEventListener("click", () => {
            if (confirm("Reset all user data (statuses, notes, descriptions)? This cannot be undone.")) {
                Persistence.resetAll();
                showToast("All user data cleared ✓");
                setTimeout(() => location.reload(), 500);
            }
        });

        // Git refresh
        document.getElementById("btn-refresh-git").addEventListener("click", async () => {
            showToast("Refreshing git status…");
            await GitStatus.load();
            GraphRenderer.applyGitStatus();
            showToast("Git status refreshed ✓");
        });

        // Save layout
        document.getElementById("btn-save-layout").addEventListener("click", () => {
            GraphRenderer.saveCurrentLayout();
            showToast("Layout saved ✓ — will restore on next open");
        });

        // Reset layout
        document.getElementById("btn-reset-layout").addEventListener("click", () => {
            if (confirm("Clear saved layout and revert to auto dagre arrangement?")) {
                GraphRenderer.clearSavedLayout();
                showToast("Layout reset to dagre ✓");
            }
        });

        // Copy trail
        document.getElementById("btn-copy-trail").addEventListener("click", () => {
            if (breadcrumbs.length === 0) {
                showToast("No trail to copy");
                return;
            }
            const trailText = breadcrumbs.map(b => b.label).join(" → ");
            navigator.clipboard.writeText(trailText).then(() => {
                showToast("Trail copied: " + trailText);
            });
        });
    }

    // ──────────────────────────────────────────────────────────
    // Keyboard shortcuts
    // ──────────────────────────────────────────────────────────

    function wireKeyboardShortcuts() {
        document.addEventListener("keydown", (e) => {
            // Don't fire shortcuts when typing in inputs
            if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;

            switch (e.key) {
                case "+":
                case "=":
                    GraphRenderer.zoomIn();
                    break;
                case "-":
                    GraphRenderer.zoomOut();
                    break;
                case "f":
                case "F":
                    GraphRenderer.fit();
                    break;
                case "g":
                case "G":
                    GitStatus.load().then(() => {
                        GraphRenderer.applyGitStatus();
                        showToast("Git status refreshed ✓");
                    });
                    break;
                case "Escape":
                    Sidebar.hide();
                    hideContextMenu();
                    GraphRenderer.clearSearch();
                    document.getElementById("search-box").value = "";
                    break;
                case "/":
                    e.preventDefault();
                    document.getElementById("search-box").focus();
                    break;
                case "1":
                    GraphRenderer.runLayout("dagre");
                    break;
                case "2":
                    GraphRenderer.runLayout("circle");
                    break;
                case "3":
                    GraphRenderer.runLayout("grid");
                    break;
            }
        });
    }

    // ──────────────────────────────────────────────────────────
    // Selection toolbar
    // ──────────────────────────────────────────────────────────

    function wireSelectionToolbar() {
        document.getElementById("btn-export-selection").addEventListener("click", () => {
            const md = GraphRenderer.exportSelectionAsMarkdown();
            if (md) {
                navigator.clipboard.writeText(md).then(() => {
                    showToast("Selection exported to clipboard as Markdown ✓");
                });
            }
        });

        document.getElementById("btn-clear-selection").addEventListener("click", () => {
            const cy = GraphRenderer.getCy();
            cy.nodes().unselect();
            document.getElementById("selection-toolbar").classList.add("hidden");
        });
    }

    // ──────────────────────────────────────────────────────────
    // Context menu
    // ──────────────────────────────────────────────────────────

    function showContextMenu(evt) {
        const node = evt.target;
        const d = node.data();
        const menu = document.getElementById("context-menu");
        const isModule = d.type === "module";

        let items = [];

        // Copy reference
        items.push({
            label: "📋 Copy Reference",
            action: () => {
                const ref = isModule
                    ? `[${d.full_path}] — ${d.layer} layer, ${d.line_count} lines`
                    : `[${d.parent_module}] ${d.label}() — line ${d.line_start}`;
                navigator.clipboard.writeText(ref).then(() => showToast("Copied: " + ref));
            }
        });

        // Open in VS Code
        if (d.abs_path) {
            items.push({
                label: "📂 Open in VS Code",
                action: () => {
                    const uri = `vscode://file/${d.abs_path.replace(/\\/g, "/")}${d.line_start ? ":" + d.line_start : ""}`;
                    window.open(uri, "_blank");
                }
            });
        }

        items.push({ separator: true });

        // Expand / collapse
        if (isModule) {
            const expanded = node.data("_expanded");
            items.push({
                label: expanded ? "⊟ Collapse" : "⊞ Expand Functions",
                action: () => GraphRenderer.toggleModule(d.id),
            });
        }

        // Focus neighbors
        items.push({
            label: "🔍 Focus Neighbors",
            action: () => {
                const cy = GraphRenderer.getCy();
                const n = cy.getElementById(d.id);
                const neighborhood = n.neighborhood().add(n);
                cy.fit(neighborhood, 60);
            }
        });

        items.push({ separator: true });

        // Status quick-set
        for (const status of ["planned", "in-progress", "done", "needs-review", "blocked"]) {
            const color = GraphRenderer.STATUS_COLORS[status];
            items.push({
                label: `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${color};margin-right:6px;"></span>${status}`,
                action: () => {
                    GraphRenderer.updateNodeStatus(d.id, status);
                    Sidebar.refreshModuleList();
                    showToast(`${d.label} → ${status}`);
                }
            });
        }

        // Build menu HTML
        menu.innerHTML = items.map(item => {
            if (item.separator) return `<div class="context-menu-sep"></div>`;
            return `<div class="context-menu-item">${item.label}</div>`;
        }).join("");

        // Wire click handlers
        const menuItems = menu.querySelectorAll(".context-menu-item");
        let idx = 0;
        for (const item of items) {
            if (!item.separator) {
                menuItems[idx].addEventListener("click", () => {
                    item.action();
                    hideContextMenu();
                });
                idx++;
            }
        }

        // Position
        const renderedPos = evt.renderedPosition || evt.originalEvent;
        const x = renderedPos.x != null ? renderedPos.x : renderedPos.clientX;
        const y = renderedPos.y != null ? renderedPos.y : renderedPos.clientY;

        // Offset by cy-container position
        const cyRect = document.getElementById("cy-container").getBoundingClientRect();
        menu.style.left = (cyRect.left + x) + "px";
        menu.style.top = (cyRect.top + y) + "px";
        menu.style.display = "block";

        // Close on click outside
        setTimeout(() => {
            document.addEventListener("click", _hideContextMenuOnce, { once: true });
        }, 50);
    }

    function hideContextMenu() {
        document.getElementById("context-menu").style.display = "none";
    }

    function _hideContextMenuOnce() {
        hideContextMenu();
    }

    // ──────────────────────────────────────────────────────────
    // Breadcrumb trail
    // ──────────────────────────────────────────────────────────

    function addBreadcrumb(nodeId, label) {
        // Avoid duplicating the last entry
        if (breadcrumbs.length > 0 && breadcrumbs[breadcrumbs.length - 1].id === nodeId) return;

        breadcrumbs.push({ id: nodeId, label: label });
        // Keep max 15
        if (breadcrumbs.length > 15) breadcrumbs.shift();
        renderBreadcrumbs();
    }

    function renderBreadcrumbs() {
        const container = document.getElementById("breadcrumbs");
        container.innerHTML = breadcrumbs.map((b, i) =>
            `<span class="crumb" data-idx="${i}" data-id="${b.id}">${b.label}</span>`
        ).join("");

        container.querySelectorAll(".crumb").forEach(el => {
            el.addEventListener("click", () => {
                const id = el.dataset.id;
                GraphRenderer.focusNode(id);
            });
        });
    }

    // ──────────────────────────────────────────────────────────
    // Toast
    // ──────────────────────────────────────────────────────────

    let _toastTimeout = null;

    function showToast(message) {
        const toast = document.getElementById("toast");
        toast.textContent = message;
        toast.classList.add("visible");
        clearTimeout(_toastTimeout);
        _toastTimeout = setTimeout(() => toast.classList.remove("visible"), 2500);
    }

    // ──────────────────────────────────────────────────────────
    // Init on DOM ready
    // ──────────────────────────────────────────────────────────

    document.addEventListener("DOMContentLoaded", boot);

    return { addBreadcrumb, showContextMenu, showToast };
})();
