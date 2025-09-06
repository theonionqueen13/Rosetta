# rosetta/patterns.py
import networkx as nx
from itertools import combinations, permutations
from rosetta.lookup import ASPECTS

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

from rosetta.lookup import ASPECTS

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
            # Strict edge present in filtered master list?
            if has_edge(x, y, asp):
                specs.append(((x, y), asp))
            # Otherwise, if we're in widen_orb mode, allow an approximate edge
            elif has_edge_loose(x, y, asp, bonus=approx_bonus):
                specs.append(((x, y), asp + "_approx"))

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

    # Envelope (5 nodes, chain of 4 Sextiles, with Oppositions and Trines)
    for quint in combinations(R, 5):
        for perm in permutations(quint):
            a, b, c, d, e = perm
            if (has_edge(a, b, "Sextile") and has_edge(b, c, "Sextile") and
                has_edge(c, d, "Sextile") and has_edge(d, e, "Sextile")):

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
                candidate_edges = [
                    ((a, b), "Sextile"), ((b, c), "Sextile"),
                    ((c, d), "Sextile"), ((d, e), "Sextile"),
                    ((a, d), "Opposition"), ((b, e), "Opposition"),
                    ((a, e), "Trine"), ((b, d), "Trine"),
                ]
                add_once("Envelope", (a, b, c, d, e), candidate_edges,
                         {"suppress": suppresses, "keep": keep})
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
        if (has_edge(a, c, "Opposition") and has_edge(b, d, "Opposition") and
            has_edge(a, b, "Sextile") and has_edge(c, d, "Sextile") and
            has_edge(a, d, "Trine") and has_edge(b, c, "Trine")):

            suppresses = {"Wedge": {
                frozenset([a, b, c]), frozenset([a, b, d]),
                frozenset([b, c, d]), frozenset([a, c, d]),
            }}
            candidate_edges = [
                ((a, c), "Opposition"), ((b, d), "Opposition"),
                ((a, b), "Sextile"), ((c, d), "Sextile"),
                ((a, d), "Trine"), ((b, c), "Trine"),
            ]
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
        if (has_edge(a, b, "Trine") and has_edge(b, c, "Trine") and has_edge(a, c, "Trine")):
            candidate_edges = [((a, b), "Trine"), ((b, c), "Trine"), ((a, c), "Trine")]
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

    def add_special(sh_type, members, edges):
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
                # Unnamed (Square + Trine + Sesquisquare)
                # Unnamed (Square + Trine + Sesquisquare)
                # Unnamed (Square + Trine + Sesquisquare)
        if aspect_match(a, b, "Square"):
            for c in pos.keys():
                if c in (a, b):
                    continue
                ca, cb = rep_anchor.get(a, a), rep_anchor.get(b, b)
                cc = rep_anchor.get(c, c)
                if len({ca, cb, cc}) < 3:
                    continue

                # Unnamed
                if aspect_match(a, b, "Square"):
                    for c in pos.keys():
                        if c not in (a, b):
                            if aspect_match(a, c, "Trine") and aspect_match(b, c, "Quincunx"):
                                edges = [((a, b), "Square"), ((a, c), "Trine"), ((b, c), "Quincunx")]
                                add_special("Unnamed", [a, b, c], edges)
                            elif aspect_match(b, c, "Trine") and aspect_match(a, c, "Quincunx"):
                                edges = [((a, b), "Square"), ((b, c), "Trine"), ((a, c), "Quincunx")]
                                add_special("Unnamed", [a, b, c], edges)

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
    shapes.sort(key=lambda s: (s.get("remainder", False), s["id"]))
    return shapes

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
# Suppression
# -------------------------------

def apply_suppression(shapes):
    suppressed = set()
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

    # Filter out suppressed shapes
    return [s for i, s in enumerate(shapes) if i not in suppressed]

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
    shape = {
        "id": sid,
        "type": sh_type,
        "parent": parent_idx,
        "members": node_list,
        "edges": edge_specs,
    }
    if rep_map is not None:
        shape["rep_map"] = rep_map
    if rep_anchor is not None:
        shape["rep_anchor"] = rep_anchor
    if suppresses is not None:
        shape["suppresses"] = suppresses
    shapes.append(shape)
    return sid + 1
