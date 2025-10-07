# patterns_v2.py — refactored to source data from calc_v2/profiles_v2
from __future__ import annotations

import importlib.util
import pathlib
from itertools import combinations, permutations
from typing import Sequence

import networkx as nx

import profiles_v2 as _profiles_mod


def _load_calc_module():
    """Dynamically load calc_v2.py from this folder (like test_calc_v2)."""

    here = pathlib.Path(__file__).resolve()
    calc_path = here.with_name("calc_v2.py")
    spec = importlib.util.spec_from_file_location("calc_v2_local", str(calc_path))
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:  # pragma: no cover - safety guard
        raise ImportError("Unable to load calc_v2 module")
    spec.loader.exec_module(module)
    return module


_calc_mod = _load_calc_module()


# Mirror the ASPECTS dict structure expected by the legacy pattern logic.
ASPECTS = {
    name: {"angle": data["angle"], "orb": data["orb"]}
    for name, data in getattr(_calc_mod, "_ASPECTS_ALL").items()
}

# Re-export a few helpers from calc_v2 so downstream callers can use the
# curated calculations without recomputing anything here.
build_aspect_edges = _calc_mod.build_aspect_edges
build_conjunction_clusters = _calc_mod.build_conjunction_clusters


def glyph_for(name: str) -> str:
    """Convenience passthrough for profile glyph lookup (used by UI callers)."""

    try:
        return _profiles_mod.glyph_for(name)
    except Exception:
        return ""


def _object_rows(df):
    """Return the object-only subset of the dataframe via calc_v2 helper."""

    extractor = getattr(_calc_mod, "_extract_object_rows", None)
    if extractor is not None:
        return extractor(df)
    return df


def positions_from_dataframe(df) -> dict[str, float]:
    """Build {name: longitude} from the already-curated calc_v2 dataframe."""

    objs = _object_rows(df)
    pos = {}
    for _, row in objs.iterrows():
        name = row.get("Object")
        lon = row.get("Longitude")
        try:
            if name is not None and lon is not None:
                pos[str(name)] = float(lon) % 360.0
        except Exception:
            continue
    return pos


def edges_from_major_list(edges_major: Sequence[tuple]) -> list[tuple]:
    """Convert calc_v2 major edges (with metadata) into legacy ((p1,p2), aspect)."""

    formatted = []
    for edge in edges_major or []:
        try:
            p1, p2, meta = edge
            aspect = meta.get("aspect") if isinstance(meta, dict) else None
        except ValueError:  # pragma: no cover - unexpected tuple format
            continue
        if aspect:
            formatted.append(((p1, p2), aspect))
    return formatted


def build_patterns_from_edges(pos: dict[str, float], edges_major: Sequence[tuple]) -> list[set[str]]:
    """Generate conjunction-aware patterns using calc_v2 major edges."""

    nodes = list(pos.keys())
    formatted_edges = edges_from_major_list(edges_major)
    return connected_components_from_edges(nodes, formatted_edges)


def prepare_pattern_inputs(df, edges_major: Sequence[tuple] | None = None):
    """Return (pos, patterns, major_edges_all) ready for shape detection."""

    if edges_major is None:
        edges_major, _ = build_aspect_edges(df)
    pos = positions_from_dataframe(df)
    formatted_edges = edges_from_major_list(edges_major)
    patterns = connected_components_from_edges(list(pos.keys()), formatted_edges)
    return pos, patterns, formatted_edges

# -------------------------------
# Connected components from edges
# -------------------------------

def aspect_match(pos, p1, p2, target_aspect):
    """Check if planets form the given aspect within orb tolerance."""
    angle = abs(pos[p1] - pos[p2]) % 360
    if angle > 180:
        angle = 360 - angle
    data = ASPECTS[target_aspect]
    return abs(angle - data["angle"]) <= data["orb"]

def connected_components_from_edges(nodes, edges):
    nodes = list(nodes)
    adj = {n: set() for n in nodes}
    for (u, v), _asp in edges:
        if u in adj and v in adj:
            adj[u].add(v)
            adj[v].add(u)

    visited, comps = set(), []
    for n in nodes:
        if n in visited or not adj[n]:
            continue
        stack = [n]
        visited.add(n)
        comp = {n}
        while stack:
            cur = stack.pop()
            for nbr in adj[cur]:
                if nbr not in visited:
                    visited.add(nbr)
                    stack.append(nbr)
                    comp.add(nbr)
        comps.append(comp)
    return comps

# -------------------------------
# Conjunction clustering
# -------------------------------

def _cluster_conjunctions_for_detection(pos, members, orb=None):
    """
    Cluster members that are within the conjunction orb.
    If orb is None, use the orb defined in ASPECTS["Conjunction"].
    """
    if orb is None:
        orb = ASPECTS["Conjunction"]["orb"]

    members_sorted = sorted(members, key=lambda m: pos[m])
    if not members_sorted:
        return {}, {}, {}

    clusters = []
    current = [members_sorted[0]]
    for m in members_sorted[1:]:
        prev = current[-1]
        gap = abs(pos[m] - pos[prev])
        if gap <= orb:
            current.append(m)
        else:
            clusters.append(current)
            current = [m]
    clusters.append(current)

    rep_pos, rep_map, rep_anchor = {}, {}, {}
    for cluster in clusters:
        rep = cluster[0]
        degrees = [pos[m] for m in cluster]
        mean_deg = sum(degrees) / len(degrees)
        rep_pos[rep] = mean_deg
        rep_map[rep] = cluster
        for m in cluster:
            rep_anchor[m] = rep

    return rep_pos, rep_map, rep_anchor

# -------------------------------
# Shape detection - FIXED VERSION
# -------------------------------

def _detect_shapes_for_members(pos, members, parent_idx, sid_start, major_edges_all, widen_orb=False):
    """
    Detect shapes for this parent using ONLY the provided major edge list.
    - Strict mode uses only edges present in major_edges_all.
    - widen_orb is ignored for now (no new edges invented).
    """
    if not members:
        return [], sid_start

    # 1) Conjunction clustering
    rep_pos, rep_map, rep_anchor = _cluster_conjunctions_for_detection(pos, list(members))
    R = list(rep_pos.keys())

    # 2) Build an edge lookup by FILTERING the precomputed master list
    edge_lookup = {}
    members_set = set(members)
    for (u, v), asp in major_edges_all:
        if u in members_set and v in members_set:
            ru = rep_anchor.get(u, u)
            rv = rep_anchor.get(v, v)
            if ru == rv:
                continue  # skip self-edges (within same conj cluster)
            edge_key = frozenset((ru, rv))
            edge_lookup.setdefault(edge_key, []).append(asp)

    # 3) Shape bookkeeping
    shapes = []
    seen = set()
    sid = sid_start

    def has_edge(a, b, aspect):
        """True iff edge exists in master list, or (if widen_orb) it's close enough to qualify as approx."""
        key = frozenset((a, b))
        if aspect in edge_lookup.get(key, []):
            return True

        if widen_orb:
            # Expanded orb check for approximate edges
            d1, d2 = pos.get(a), pos.get(b)
            if d1 is None or d2 is None:
                return False
            angle = abs(d1 - d2) % 360
            if angle > 180:
                angle = 360 - angle
            data = ASPECTS[aspect]
            widened_orb = data["orb"] * 1.5  # expand by 50%, adjust as you like
            if abs(angle - data["angle"]) <= widened_orb:
                return True
        return False

    def has_edge_loose(a, b, aspect, bonus=1.0):
        """
        When widen_orb=True, allow 'near misses' by checking angles directly
        using representative positions and a wider orb. Returns True if the
        pair is within (orb + bonus). This does NOT touch major_edges_all.
        """
        if not widen_orb:
            return False
        if aspect not in ("Opposition", "Trine", "Sextile", "Square", "Conjunction"):
            return False

        # Use representative (cluster) degrees, not raw planet degrees
        da = rep_pos.get(a)
        db = rep_pos.get(b)
        if da is None or db is None:
            return False

        angle = abs((da - db) % 360)
        if angle > 180:
            angle = 360 - angle

        target = ASPECTS[aspect]["angle"]
        base_orb = ASPECTS[aspect]["orb"]
        return abs(angle - target) <= (base_orb + bonus)

    def add_once(sh_type, node_list, candidate_edges, suppresses=None, approx_bonus=2.0):
        nonlocal sid
        key = (sh_type, tuple(sorted(node_list)))
        if key in seen:
            return False

        specs = []
        for (x, y), asp in candidate_edges:
            is_forced_approx = asp.endswith("_approx")
            asp_clean = asp.replace("_approx", "")

            # Strict edge present in filtered master list?
            if has_edge(x, y, asp_clean):
                specs.append(((x, y), asp_clean))
            # Allow explicitly provided approximate edges to pass through
            elif is_forced_approx:
                specs.append(((x, y), asp))
            # Otherwise, if we're in widen_orb mode, allow an approximate edge
            elif has_edge_loose(x, y, asp_clean, bonus=approx_bonus):
                specs.append(((x, y), f"{asp_clean}_approx"))

        if not specs:
            return False

        sid = _add_shape(
            shapes, sh_type, parent_idx, sid,
            node_list, specs, rep_map, rep_anchor, suppresses
        )
        seen.add(key)
        return True

    # -----------------------
    # SHAPE DETECTION LOGIC
    # (unchanged from your version; uses has_edge/add_once)
    # -----------------------
    def aspect_ok(a, b, aspect, slack=0.75):
        """Return True if the aspect exists or is very close within slack degrees."""
        if has_edge(a, b, aspect):
            return True

        da = rep_pos.get(a, pos.get(a))
        db = rep_pos.get(b, pos.get(b))
        if da is None or db is None:
            return False

        angle = abs((da - db) % 360)
        if angle > 180:
            angle = 360 - angle

        data = ASPECTS[aspect]
        return abs(angle - data["angle"]) <= (data["orb"] + slack)

    def aspect_ok(a, b, aspect, slack=0.75):
        """Return True if the aspect exists or is very close within slack degrees."""
        if has_edge(a, b, aspect):
            return True

        da = rep_pos.get(a, pos.get(a))
        db = rep_pos.get(b, pos.get(b))
        if da is None or db is None:
            return False

        angle = abs((da - db) % 360)
        if angle > 180:
            angle = 360 - angle

        data = ASPECTS[aspect]
        return abs(angle - data["angle"]) <= (data["orb"] + slack)

    # Envelope (5 nodes, chain of 4 Sextiles, with Oppositions and Trines)
    for quint in combinations(R, 5):
        opp_pairs = [
            pair
            for pair in combinations(quint, 2)
            if aspect_ok(pair[0], pair[1], "Opposition")
        ]
        if len(opp_pairs) < 2:
            continue

        added = False
        for opp1, opp2 in combinations(opp_pairs, 2):
            if set(opp1) & set(opp2):
                continue  # oppositions must be disjoint

            center_candidates = set(quint) - set(opp1) - set(opp2)
            if len(center_candidates) != 1:
                continue

            c = next(iter(center_candidates))

            for pair_primary, pair_secondary in ((opp1, opp2), (opp2, opp1)):
                for a, d in (pair_primary, pair_primary[::-1]):
                    for b, e in (pair_secondary, pair_secondary[::-1]):
                        sextile_specs = [
                            ((a, b), "Sextile"),
                            ((b, c), "Sextile"),
                            ((c, d), "Sextile"),
                            ((d, e), "Sextile"),
                        ]
                        if not all(has_edge(x, y, asp) for (x, y), asp in sextile_specs):
                            continue

                        diag_specs = []
                        diag_checks = [
                            ((a, d), "Opposition"),
                            ((b, e), "Opposition"),
                            ((a, e), "Trine"),
                            ((b, d), "Trine"),
                        ]
                        valid_diag = True
                        for (x, y), asp in diag_checks:
                            if not aspect_ok(x, y, asp):
                                valid_diag = False
                                break
                            label = asp if has_edge(x, y, asp) else f"{asp}_approx"
                            diag_specs.append(((x, y), label))
                        if not valid_diag:
                            continue

                        suppresses = {
                            "Sextile Wedge": {frozenset([a, b, c]), frozenset([c, d, e])},
                            "Kite": {frozenset([a, b, c, e]), frozenset([a, c, d, e])},
                            "Cradle": {frozenset([a, b, c, d]), frozenset([b, c, d, e])},
                            "Wedge": {
                                frozenset([a, b, d]), frozenset([c, d, e]),
                                frozenset([a, c, d]), frozenset([a, b, e]),
                                frozenset([a, d, e]), frozenset([b, c, e]),
                                frozenset([b, d, e]),
                            },
                        }
                        keep = {
                            "Sextile Wedge": {frozenset([b, c, d])},
                            "Mystic Rectangle": {frozenset([a, b, d, e])},
                            "Grand Trine": {frozenset([a, c, e])},
                        }
                        candidate_edges = sextile_specs + diag_specs
                        add_once(
                            "Envelope",
                            (a, b, c, d, e),
                            candidate_edges,
                            {"suppress": suppresses, "keep": keep},
                        )
                        added = True
                        break
                    if added:
                        break
                if added:
                    break
            if added:
                break

    # Grand Cross
    for quad in combinations(R, 4):
        a, b, c, d = quad
        if (has_edge(a, c, "Opposition") and has_edge(b, d, "Opposition") and
            has_edge(a, b, "Square") and has_edge(b, c, "Square") and
            has_edge(c, d, "Square") and has_edge(d, a, "Square")):

            suppresses = {"T-Square": {
                frozenset([a, b, c]), frozenset([b, c, d]),
                frozenset([c, d, a]), frozenset([d, a, b]),
            }}
            candidate_edges = [
                ((a, c), "Opposition"), ((b, d), "Opposition"),
                ((a, b), "Square"), ((b, c), "Square"),
                ((c, d), "Square"), ((d, a), "Square"),
            ]
            add_once("Grand Cross", (a, b, c, d), candidate_edges,
                     {"suppress": suppresses})

    # Mystic Rectangle
    for quad in combinations(R, 4):
        a, b, c, d = quad
        sextile_specs = [
            ((a, b), "Sextile"),
            ((c, d), "Sextile"),
        ]
        if not all(has_edge(x, y, asp) for (x, y), asp in sextile_specs):
            continue

        diag_checks = [
            ((a, c), "Opposition"),
            ((b, d), "Opposition"),
            ((a, d), "Trine"),
            ((b, c), "Trine"),
        ]
        diag_specs = []
        valid_diag = True
        for (x, y), asp in diag_checks:
            if not aspect_ok(x, y, asp):
                valid_diag = False
                break
            label = asp if has_edge(x, y, asp) else f"{asp}_approx"
            diag_specs.append(((x, y), label))
        if not valid_diag:
            continue

        suppresses = {"Wedge": {
            frozenset([a, b, c]), frozenset([a, b, d]),
            frozenset([b, c, d]), frozenset([a, c, d]),
        }}
        candidate_edges = sextile_specs + diag_specs
        add_once("Mystic Rectangle", (a, b, c, d), candidate_edges,
                 {"suppress": suppresses})

    # Cradle
    for quad in permutations(R, 4):
        a, b, c, d = quad
        if (has_edge(a, b, "Sextile") and has_edge(b, c, "Sextile") and
            has_edge(c, d, "Sextile") and has_edge(a, d, "Opposition") and
            has_edge(a, c, "Trine") and has_edge(b, d, "Trine")):

            suppresses = {
                "Wedge": {frozenset([a, b, d]), frozenset([a, c, d])},
                "Sextile Wedge": {frozenset([a, b, c]), frozenset([b, c, d])},
            }
            candidate_edges = [
                ((a, b), "Sextile"), ((b, c), "Sextile"), ((c, d), "Sextile"),
                ((a, d), "Opposition"), ((a, c), "Trine"), ((b, d), "Trine"),
            ]
            add_once("Cradle", (a, b, c, d), candidate_edges,
                     {"suppress": suppresses})
            break

    # Kite
    for quad in combinations(R, 4):
        for trio in combinations(quad, 3):
            a, b, c = trio
            apex = list(set(quad) - set(trio))[0]
            if (has_edge(a, b, "Trine") and has_edge(b, c, "Trine") and has_edge(a, c, "Trine")):
                for t in (a, b, c):
                    if has_edge(apex, t, "Opposition"):
                        # a,b,c are the grand-trine nodes, t is the one opposed by apex
                        rest = [x for x in (a, b, c) if x != t]

                        suppress_wedges = {
                            frozenset([apex, t, rest[0]]),  # wedge using apex–t opposition + trines/sextiles
                            frozenset([apex, t, rest[1]]),
                        }

                        suppress_sextile_wedge = {
                            frozenset([apex, rest[0], rest[1]])  # apex sextiles to both, those two are trine
                        }

                        suppresses = {
                            "Wedge": suppress_wedges,
                            "Sextile Wedge": suppress_sextile_wedge,
                            "Grand Trine": {frozenset([a, b, c])},
                        }

                        candidate_edges = [
                            ((a, b), "Trine"), ((b, c), "Trine"), ((a, c), "Trine"),
                            ((apex, t), "Opposition"),
                            ((apex, rest[0]), "Sextile"), ((apex, rest[1]), "Sextile"),
                        ]
                        add_once("Kite", (a, b, c, apex), candidate_edges,
                                 {"suppress": suppresses})
                        break

    # Grand Trine
    for trio in combinations(R, 3):
        a, b, c = trio
        tri_specs = [
            ((a, b), "Trine"),
            ((b, c), "Trine"),
            ((a, c), "Trine"),
        ]
        valid_tri = True
        candidate_edges = []
        for (x, y), asp in tri_specs:
            if has_edge(x, y, asp):
                candidate_edges.append(((x, y), asp))
            elif aspect_ok(x, y, asp):
                candidate_edges.append(((x, y), f"{asp}_approx"))
            else:
                valid_tri = False
                break
        if not valid_tri:
            continue
        add_once("Grand Trine", (a, b, c), candidate_edges)

    # T-Square
    for trio in combinations(R, 3):
        for apex in trio:
            a, b = [n for n in trio if n != apex]
            if (has_edge(a, b, "Opposition") and
                has_edge(apex, a, "Square") and has_edge(apex, b, "Square")):
                candidate_edges = [
                    ((a, b), "Opposition"),
                    ((apex, a), "Square"),
                    ((apex, b), "Square"),
                ]
                add_once("T-Square", (a, b, apex), candidate_edges)
                break

    # Wedge
    for trio in combinations(R, 3):
        pairs = list(combinations(trio, 2))
        opp = [p for p in pairs if has_edge(p[0], p[1], "Opposition")]
        tri = [p for p in pairs if has_edge(p[0], p[1], "Trine")]
        sex = [p for p in pairs if has_edge(p[0], p[1], "Sextile")]
        if len(opp) == 1 and len(tri) == 1 and len(sex) == 1:
            candidate_edges = [(opp[0], "Opposition"), (tri[0], "Trine"), (sex[0], "Sextile")]
            add_once("Wedge", trio, candidate_edges)

    # Sextile Wedge
    for trio in combinations(R, 3):
        pairs = list(combinations(trio, 2))
        tri = [p for p in pairs if has_edge(p[0], p[1], "Trine")]
        sex = [p for p in pairs if has_edge(p[0], p[1], "Sextile")]
        opp = [p for p in pairs if has_edge(p[0], p[1], "Opposition")]
        if len(tri) == 1 and len(sex) == 2 and not opp:
            candidate_edges = [(tri[0], "Trine"), (sex[0], "Sextile"), (sex[1], "Sextile")]
            add_once("Sextile Wedge", trio, candidate_edges)

    return shapes, sid

# -------------------------------
# Detect shapes (public API)
# -------------------------------

# -------------------------------
# Aspect helpers
# -------------------------------

def _aspect_match_wide(pos, p1, p2, target_aspect, widen=1.0):
    """Looser orb check than strict aspect_match, for special cases."""
    angle = abs(pos[p1] - pos[p2]) % 360
    if angle > 180:
        angle = 360 - angle
    data = ASPECTS[target_aspect]
    return abs(angle - data["angle"]) <= data["orb"] * widen


# -------------------------------
# Detect shapes (public API)
# -------------------------------

def detect_shapes(pos, patterns, major_edges_all):
    shapes = []
    sid = 0
    used_members = set()
    used_edges = set()
    seen = set()   # <-- 🔑 global dedup set

    # -------------------------------
    # strict pass
    # -------------------------------
    for parent_idx, mems in enumerate(patterns):
        s_here, sid = _detect_shapes_for_members(
            pos, mems, parent_idx, sid, major_edges_all, widen_orb=False
        )
        shapes.extend(s_here)
        for sh in s_here:
            used_members.update(sh["members"])
            for (u, v), asp in sh["edges"]:
                used_edges.add((tuple(sorted((u, v))), asp))

    # -------------------------------
    # special-shape pass (orb-aware, with conjunction collapse)
    # -------------------------------
    rep_pos, rep_map, rep_anchor = _cluster_conjunctions_for_detection(pos, pos.keys())

    def collapse_members(members):
        return [rep_anchor.get(m, m) for m in members]

    def aspect_match(p1, p2, target_aspect):
        angle = abs(pos[p1] - pos[p2]) % 360
        if angle > 180:
            angle = 360 - angle
        data = ASPECTS[target_aspect]
        return abs(angle - data["angle"]) <= data["orb"]

    def assign_parent_for_special(members, fallback=0):
        for idx, mems in enumerate(patterns):
            if all(m in mems for m in members):
                return idx
        for idx, mems in enumerate(patterns):
            hits = sum(1 for m in members if m in mems)
            if hits >= 2:
                return idx
        return fallback

    def add_special(sh_type, members, edges, suppresses=None):
        nonlocal sid, seen
        collapsed = tuple(sorted(set(collapse_members(members))))
        key = (sh_type, collapsed)
        if key in seen:
            return
        parent_idx = assign_parent_for_special(collapsed)
        shape = {
            "id": sid,
            "type": sh_type,
            "parent": parent_idx,
            "members": list(collapsed),
            "edges": edges,
        }
        if suppresses is not None:
            shape["suppresses"] = suppresses
        shapes.append(shape)
        sid += 1
        seen.add(key)
        used_members.update(collapsed)
        for (u, v), asp in edges:
            used_edges.add((tuple(sorted((u, v))), asp))

    # loop edges → add special shapes
    for (a, b), asp in major_edges_all:
        # Yod
        if aspect_match(a, b, "Sextile"):
            for c in pos.keys():
                if c not in (a, b) and aspect_match(a, c, "Quincunx") and aspect_match(b, c, "Quincunx"):
                    edges = [((a, b), "Sextile"), ((a, c), "Quincunx"), ((b, c), "Quincunx")]
                    add_special("Yod", [a, b, c], edges)

        # Wide Yod
        if aspect_match(a, b, "Square"):
            for c in pos.keys():
                if c not in (a, b) and aspect_match(a, c, "Sesquisquare") and aspect_match(b, c, "Sesquisquare"):
                    edges = [((a, b), "Square"), ((a, c), "Sesquisquare"), ((b, c), "Sesquisquare")]
                    add_special("Wide Yod", [a, b, c], edges)

        # Unnamed
        if aspect_match(a, b, "Square"):
            for c in pos.keys():
                if c in (a, b):
                    continue
                if aspect_match(a, c, "Trine") and aspect_match(b, c, "Quincunx"):
                    edges = [((a, b), "Square"), ((a, c), "Trine"), ((b, c), "Quincunx")]
                    add_special("Unnamed", [a, b, c], edges)
                elif aspect_match(b, c, "Trine") and aspect_match(a, c, "Quincunx"):
                    edges = [((a, b), "Square"), ((b, c), "Trine"), ((a, c), "Quincunx")]
                    add_special("Unnamed", [a, b, c], edges)

    # ⚡ Lightning Bolt collapse (after Unnameds exist)
    unnamed_info = []
    for s in shapes:
        if s["type"] != "Unnamed":
            continue
        q_edge = None
        square_edge = None
        for (u, v), asp in s["edges"]:
            if asp == "Quincunx":
                q_edge = (u, v)
            elif asp == "Square":
                square_edge = (u, v)

        if not q_edge or not square_edge:
            continue

        q_endpoints = frozenset(q_edge)

        if square_edge[0] in q_endpoints and square_edge[1] not in q_endpoints:
            q_node = square_edge[0]
            extra = square_edge[1]
        elif square_edge[1] in q_endpoints and square_edge[0] not in q_endpoints:
            q_node = square_edge[1]
            extra = square_edge[0]
        else:
            continue

        unnamed_info.append({
            "members": set(s["members"]),
            "quincunx": q_endpoints,
            "q_node": q_node,
            "extra": extra,
        })

    for i in range(len(unnamed_info)):
        for j in range(i + 1, len(unnamed_info)):
            u1 = unnamed_info[i]
            u2 = unnamed_info[j]

            if u1["quincunx"] != u2["quincunx"]:
                continue

            if u1["q_node"] == u2["q_node"]:
                continue

            r1, r2 = u1["extra"], u2["extra"]
            if r1 == r2:
                continue

            q1, q2 = u1["q_node"], u2["q_node"]

            if not (aspect_match(q1, q2, "Quincunx") and
                    aspect_match(q1, r1, "Square") and
                    aspect_match(q2, r2, "Square") and
                    aspect_match(q1, r2, "Trine") and
                    aspect_match(q2, r1, "Trine")):
                continue

            candidate_edges = [
                ((q1, r1), "Square"),
                ((q1, r2), "Trine"),
                ((q2, r1), "Trine"),
                ((q2, r2), "Square"),
                ((q1, q2), "Quincunx"),
            ]

            suppresses = {
                "suppress": {
                    "Unnamed": {
                        frozenset(u1["members"]),
                        frozenset(u2["members"]),
                    }
                }
            }

            add_special("Lightning Bolt", [q1, q2, r1, r2], candidate_edges, suppresses)

    # -------------------------------
    # approx pass
    # -------------------------------
    for parent_idx, mems in enumerate(patterns):
        leftovers = set(mems) - used_members
        if not leftovers:
            continue
        s_here_approx, sid = _detect_shapes_for_members(
            pos, leftovers, parent_idx, sid, major_edges_all, widen_orb=True
        )
        for sh in s_here_approx:
            sh["approx"] = True
            used_members.update(sh["members"])
            for (u, v), asp in sh["edges"]:
                used_edges.add((tuple(sorted((u, v))), asp))
        shapes.extend(s_here_approx)

    # -------------------------------
    # remainder pass (conjunction-aware)
    # -------------------------------
    for parent_idx, mems in enumerate(patterns):
        if not mems:
            continue

        # Collapse conjunctions for this parent
        rep_pos, rep_map, rep_anchor = _cluster_conjunctions_for_detection(pos, list(mems))
        members_set = set(rep_pos.keys())  # only use cluster reps

        remainders = []
        for (u, v), asp in major_edges_all:
            ru, rv = rep_anchor.get(u, u), rep_anchor.get(v, v)
            if ru == rv:
                continue  # ignore intra-cluster self-edge

            edge_key = (tuple(sorted((ru, rv))), asp)
            if (
                edge_key not in used_edges
                and ru in members_set
                and rv in members_set
            ):
                remainders.append(((ru, rv), asp))

        if remainders:
            G = nx.Graph()
            for (ru, rv), asp in remainders:
                G.add_edge(ru, rv, aspect=asp)
            for comp in nx.connected_components(G):
                comp_edges = []
                for ru, rv in G.subgraph(comp).edges():
                    asp = G[ru][rv]["aspect"]
                    comp_edges.append(((ru, rv), asp))
                shapes.append({
                    "id": sid,
                    "type": "Remainder",
                    "parent": parent_idx,
                    "members": list(comp),
                    "edges": comp_edges,
                    "remainder": True,
                })
                sid += 1

    # -------------------------------
    # suppression
    # -------------------------------
    shapes = apply_suppression(shapes)

    # -------------------------------
    # final sort + return
    # -------------------------------
    envelope_order = {}
    desired_sequence = [
        ("Envelope", 0),
        ("Mystic Rectangle", 1),
        ("Grand Trine", 2),
        ("Sextile Wedge", 3),
    ]

    for sh in shapes:
        if sh["type"] != "Envelope":
            continue
        env_id = sh["id"]
        env_key = ("Envelope", frozenset(sh["members"]))
        envelope_order[env_key] = (env_id, 0)

        keep_map = sh.get("suppresses", {}).get("keep", {})
        for shape_type, slot in desired_sequence[1:]:
            for members in keep_map.get(shape_type, set()):
                envelope_order[(shape_type, members)] = (env_id, slot)

    def sort_key(shape):
        remainder_flag = shape.get("remainder", False)
        key = (shape["type"], frozenset(shape["members"]))
        if key in envelope_order:
            env_id, slot = envelope_order[key]
            return (remainder_flag, env_id, slot, shape["id"])
        return (remainder_flag, shape["id"], 0, shape["id"])

    shapes.sort(key=sort_key)
    return shapes


def detect_shapes_from_dataframe(df, edges_major: Sequence[tuple] | None = None):
    """High-level helper that plugs curated calc_v2 data into detect_shapes."""

    pos, patterns, major_edges_all = prepare_pattern_inputs(df, edges_major)
    return detect_shapes(pos, patterns, major_edges_all)

# -------------------------------
# Aspect helpers
# -------------------------------

def _aspect_match_wide(pos, p1, p2, target_aspect, widen=1.0):
    """Looser orb check than strict aspect_match, for special cases."""
    angle = abs(pos[p1] - pos[p2]) % 360
    if angle > 180:
        angle = 360 - angle
    data = ASPECTS[target_aspect]
    return abs(angle - data["angle"]) <= data["orb"] * widen

# -------------------------------
# Suppression
# -------------------------------

def apply_suppression(shapes):
    suppressed = set()

    # Define priority: higher number = stronger
    priority = {
        "Lightning Bolt": 3,
        "Envelope": 2,
        "Grand Cross": 2,
        "Mystic Rectangle": 2,
        "Cradle": 2,
        "Kite": 2,
        "Grand Trine": 1,
        "T-Square": 1,
        "Wedge": 1,
        "Sextile Wedge": 1,
        "Unnamed": 0,
    }

    for i, s_big in enumerate(shapes):
        if "suppresses" not in s_big:
            continue
        sup_data = s_big["suppresses"]
        sup_sets = sup_data.get("suppress", {})
        keep_sets = sup_data.get("keep", {})

        for s_type, sub_sets in sup_sets.items():
            for sub_members in sub_sets:
                for j, s_small in enumerate(shapes):
                    if j in suppressed:
                        continue
                    if s_small["type"] != s_type:
                        continue
                    if frozenset(s_small["members"]) == sub_members:
                        # Only suppress if big shape has >= priority than small one
                        if priority.get(s_big["type"], 0) >= priority.get(s_small["type"], 0):
                            # Check keep rules
                            keep_hit = False
                            for env in [sh for sh in shapes if "keep" in sh.get("suppresses", {})]:
                                keep_map = env["suppresses"]["keep"]
                                if (s_small["type"] in keep_map and
                                    frozenset(s_small["members"]) in keep_map[s_small["type"]]):
                                    keep_hit = True
                                    break
                            if keep_hit:
                                continue
                            suppressed.add(j)

        # Never suppress Lightning Bolt
    return [s for i, s in enumerate(shapes) if i not in suppressed or s["type"] == "Lightning Bolt"]

# -------------------------------
# Minors (unchanged)
# -------------------------------

def detect_minor_links_with_singletons(pos, patterns):
    minor_aspects = ["Quincunx", "Sesquisquare"]
    connections = []
    pattern_map = {}
    for idx, pattern in enumerate(patterns):
        for planet in pattern:
            pattern_map[planet] = idx
    all_patterned = set(pattern_map.keys())
    all_placements = set(pos.keys())
    singletons = all_placements - all_patterned
    singleton_index_offset = len(patterns)
    singleton_map = {planet: singleton_index_offset + i for i, planet in enumerate(singletons)}
    pattern_map.update(singleton_map)
    for p1, p2 in combinations(pos.keys(), 2):
        angle = abs(pos[p1] - pos[p2]) % 360
        if angle > 180:
            angle = 360 - angle
        for asp in minor_aspects:
            data = ASPECTS[asp]
            if abs(angle - data["angle"]) <= data["orb"]:
                pat1 = pattern_map.get(p1)
                pat2 = pattern_map.get(p2)
                if pat1 is not None and pat2 is not None:
                    connections.append((p1, p2, asp, pat1, pat2))
                break
    return connections, singleton_map


def detect_minor_links_from_dataframe(df, edges_major: Sequence[tuple] | None = None):
    """Wrapper using calc_v2 dataframes to find filaments + singleton map."""

    pos, patterns, _ = prepare_pattern_inputs(df, edges_major)
    return detect_minor_links_with_singletons(pos, patterns)

def generate_combo_groups(filaments):
    G = nx.Graph()
    for _, _, _, pat1, pat2 in filaments:
        if pat1 != pat2:
            G.add_edge(pat1, pat2)
    return [sorted(list(g)) for g in nx.connected_components(G) if len(g) > 1]

def internal_minor_edges_for_pattern(pos, members):
    minors = []
    mems = [m for m in members if m in pos]
    for i in range(len(mems)):
        for j in range(i + 1, len(mems)):
            p1, p2 = mems[i], mems[j]
            angle = abs(pos[p1] - pos[p2]) % 360
            if angle > 180:
                angle = 360 - angle
            for asp in ["Quincunx", "Sesquisquare"]:
                data = ASPECTS[asp]
                if abs(angle - data["angle"]) <= data["orb"]:
                    minors.append(((p1, p2), asp))
                    break
    return minors

# -------------------------------
# Shape construction helper
# -------------------------------

def _add_shape(shapes, sh_type, parent_idx, sid, node_list, edge_specs,
               rep_map=None, rep_anchor=None, suppresses=None):
    # Expand members to include all planets in each cluster
    expanded_members = []
    for n in node_list:
        if rep_map and n in rep_map:
            expanded_members.extend(rep_map[n])
        else:
            expanded_members.append(n)

    shape = {
        "id": sid,
        "type": sh_type,
        "parent": parent_idx,
        "members": expanded_members,
        "edges": edge_specs,
    }
    if rep_map is not None:
        shape["rep_map"] = rep_map
    if rep_anchor is not None:
        shape["rep_anchor"] = rep_anchor
    if suppresses is not None:
        expanded_suppresses = {}
        for section in ("suppress", "keep"):
            sec_map = suppresses.get(section)
            if not sec_map:
                continue
            expanded_suppresses[section] = {}
            for s_type, sets in sec_map.items():
                expanded_sets = set()
                for member_set in sets:
                    members_expanded = []
                    for n in member_set:
                        if rep_map and n in rep_map:
                            members_expanded.extend(rep_map[n])
                        else:
                            members_expanded.append(n)
                    expanded_sets.add(frozenset(members_expanded))
                expanded_suppresses[section][s_type] = expanded_sets
        if expanded_suppresses:
            shape["suppresses"] = expanded_suppresses
    shapes.append(shape)
    return sid + 1

