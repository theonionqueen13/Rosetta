/**
 * git-status.js — Load and apply git diff highlights to graph nodes.
 *
 * Reads data/git_status.json (produced by update_git_status.py) and
 * exposes helpers to query changed status per file.
 */

const GitStatus = (() => {
    let _data = null;    // loaded git_status.json
    let _loaded = false;

    /** Fetch git_status.json. Returns the data or null on failure. */
    async function load() {
        try {
            const resp = await fetch("data/git_status.json?" + Date.now());
            if (!resp.ok) {
                console.warn("GitStatus: git_status.json not found (run update_git_status.py)");
                _data = null;
                _loaded = true;
                return null;
            }
            _data = await resp.json();
            _loaded = true;
            return _data;
        } catch (e) {
            console.warn("GitStatus: failed to load", e);
            _data = null;
            _loaded = true;
            return null;
        }
    }

    /** Check if a module (by its full_path, e.g. "src/chart_core.py") is changed. */
    function isChanged(fullPath) {
        if (!_data) return false;
        // Normalize separators
        const norm = fullPath.replace(/\\/g, "/");
        return (_data.changed_files || []).some(f => f.replace(/\\/g, "/") === norm);
    }

    /** Get diff stats { additions, deletions } for a file path, or null. */
    function getStats(fullPath) {
        if (!_data || !_data.stats) return null;
        const norm = fullPath.replace(/\\/g, "/");
        // Try exact match, then try with .py variations
        return _data.stats[norm] || _data.stats[fullPath] || null;
    }

    /** Get the branch name. */
    function getBranch() {
        return _data ? _data.branch : "unknown";
    }

    /** Get the last commit message. */
    function getLastCommit() {
        return _data ? _data.last_commit : "";
    }

    /** Get generated timestamp. */
    function getTimestamp() {
        return _data ? _data.generated_at : null;
    }

    /** Get all changed .py file paths. */
    function getChangedFiles() {
        return _data ? (_data.changed_files || []) : [];
    }

    function isLoaded() { return _loaded; }

    return { load, isChanged, getStats, getBranch, getLastCommit, getTimestamp, getChangedFiles, isLoaded };
})();
