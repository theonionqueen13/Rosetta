/**
 * persistence.js — localStorage + JSON import/export for user data.
 *
 * User data includes: node statuses, notes, custom descriptions.
 * Stored in localStorage under key "rosetta_dag_user_data".
 */

const Persistence = (() => {
    const STORAGE_KEY = "rosetta_dag_user_data";
    const THEME_KEY = "rosetta_dag_theme";

    /**
     * Get all user data as an object keyed by node ID.
     * Shape: { [nodeId]: { status, notes, description } }
     */
    function loadAll() {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            return raw ? JSON.parse(raw) : {};
        } catch (e) {
            console.warn("Persistence: failed to load", e);
            return {};
        }
    }

    /** Save entire user data object. */
    function saveAll(data) {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
        } catch (e) {
            console.warn("Persistence: failed to save", e);
        }
    }

    /** Get data for a single node. */
    function getNode(nodeId) {
        const all = loadAll();
        return all[nodeId] || { status: null, notes: "", description: "" };
    }

    /** Update data for a single node (merges with existing). */
    function setNode(nodeId, patch) {
        const all = loadAll();
        all[nodeId] = { ...(all[nodeId] || {}), ...patch };
        saveAll(all);
    }

    /** Delete all user data. */
    function resetAll() {
        localStorage.removeItem(STORAGE_KEY);
    }

    /** Export user data AND saved layout as a single downloadable JSON file. */
    function exportToFile() {
        const bundle = {
            user_data: loadAll(),
            layout: loadLayout() || {},
        };
        const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "rosetta_dag_user_data.json";
        a.click();
        URL.revokeObjectURL(url);
    }

    /** Import user data (and optional layout) from a JSON file, merging with existing. */
    function importFromFile(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = (e) => {
                try {
                    const parsed = JSON.parse(e.target.result);
                    // Support both old flat format and new bundle format
                    const imported = parsed.user_data || parsed;
                    const importedLayout = parsed.layout || null;

                    const existing = loadAll();
                    const merged = { ...existing, ...imported };
                    saveAll(merged);

                    if (importedLayout && Object.keys(importedLayout).length > 0) {
                        saveLayout(importedLayout);
                    }
                    resolve(merged);
                } catch (err) {
                    reject(err);
                }
            };
            reader.onerror = reject;
            reader.readAsText(file);
        });
    }

    /** Theme persistence */
    function getTheme() {
        return localStorage.getItem(THEME_KEY) || "dark";
    }

    function setTheme(theme) {
        localStorage.setItem(THEME_KEY, theme);
    }

    // ── Layout persistence ──────────────────────────────────
    const LAYOUT_KEY = "rosetta_dag_layout";

    /**
     * Save a positions map: { [nodeId]: { x, y } }
     */
    function saveLayout(positions) {
        try {
            localStorage.setItem(LAYOUT_KEY, JSON.stringify(positions));
        } catch (e) {
            console.warn("Persistence: failed to save layout", e);
        }
    }

    /**
     * Load saved positions map, or null if none saved yet.
     */
    function loadLayout() {
        try {
            const raw = localStorage.getItem(LAYOUT_KEY);
            return raw ? JSON.parse(raw) : null;
        } catch (e) {
            console.warn("Persistence: failed to load layout", e);
            return null;
        }
    }

    /** Delete saved layout (will fall back to auto dagre on next load). */
    function clearLayout() {
        localStorage.removeItem(LAYOUT_KEY);
    }

    function hasSavedLayout() {
        return localStorage.getItem(LAYOUT_KEY) !== null;
    }

    return {
        loadAll, saveAll, getNode, setNode, resetAll,
        exportToFile, importFromFile,
        getTheme, setTheme,
        saveLayout, loadLayout, clearLayout, hasSavedLayout,
    };
})();
