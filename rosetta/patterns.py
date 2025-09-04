# rosetta/patterns.py
import networkx as nx
from itertools import combinations, permutations
from rosetta.lookup import ASPECTS

# -------------------------------
# Connected components from edges
# -------------------------------

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

    # DEBUG: show what this parent actually kept from master edges
    print(f"\nDEBUG: edge_lookup for parent {parent_idx}, members={members}")
    for k, asp_list in edge_lookup.items():
        u, v = tuple(k)
        print(f"   {u}-{v}: {asp_list}")

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
                # DEBUG: show invented approx edges
                # print(f"   [approx] {x}-{y} {asp} (bonus={approx_bonus})")

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

def detect_shapes(pos, patterns, major_edges_all):
    shapes = []
    sid = 0
    used_members = set()
    used_edges = set()  # track edges already consumed by strict/approx shapes

    # strict pass
    for parent_idx, mems in enumerate(patterns):
        s_here, sid = _detect_shapes_for_members(
            pos, mems, parent_idx, sid, major_edges_all, widen_orb=False
        )
        shapes.extend(s_here)
        for sh in s_here:
            used_members.update(sh["members"])
            for (u, v), asp in sh["edges"]:
                used_edges.add((tuple(sorted((u, v))), asp))

    # approx pass
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

    # remainder pass (grouped by connectivity)
    for parent_idx, mems in enumerate(patterns):
        members_set = set(mems)

        # collect unused edges
        remainders = []
        for (u, v), asp in major_edges_all:
            edge_key = (tuple(sorted((u, v))), asp)
            if (
                edge_key not in used_edges
                and u in members_set
                and v in members_set
            ):
                remainders.append(((u, v), asp))

        if remainders:
            # build adjacency graph
            import networkx as nx
            G = nx.Graph()
            for (u, v), asp in remainders:
                G.add_edge(u, v, aspect=asp)

            for comp in nx.connected_components(G):
                comp_edges = []
                for u, v in G.subgraph(comp).edges():
                    asp = G[u][v]["aspect"]
                    comp_edges.append(((u, v), asp))

                shapes.append({
                    "id": sid,
                    "type": "Remainder",
                    "parent": parent_idx,
                    "members": list(comp),
                    "edges": comp_edges,
                    "remainder": True,
                })
                sid += 1

    # suppression at the very end
    shapes = apply_suppression(shapes)

    # sort: strict+approx first, then remainder groups last
    shapes.sort(key=lambda s: (s.get("remainder", False), s["id"]))
    return shapes

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
