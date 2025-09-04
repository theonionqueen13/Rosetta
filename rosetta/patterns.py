
import networkx as nx
from itertools import combinations, permutations
from rosetta.lookup import ASPECTS
from rosetta.drawing import classify_major_aspect_pair, enumerate_major_edges
 
 # -------------------------------
 # Aspect graph (patterns as connected components)
 # -------------------------------
def build_aspect_graph(pos, return_graph=False):
    G = nx.Graph()
    for p1, p2 in combinations(pos.keys(), 2):
        asp = classify_major_aspect_pair(pos, p1, p2)
        if asp:
            G.add_edge(p1, p2, aspect=asp)
    comps = list(nx.connected_components(G))
    if return_graph:
        return comps, G
    return comps

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
    singleton_map = {
        planet: singleton_index_offset + i for i, planet in enumerate(singletons)
    }
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


# -------------------------------
# Helpers
# -------------------------------
def _add_shape(
    shapes, sh_type, parent_idx, sid,
    node_list, edge_specs,
    rep_map=None, rep_anchor=None, suppresses=None
):
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


def _has_aspect(G, a, b, kind):
    return G.has_edge(a, b) and G[a][b]["aspect"] == kind

# -------------------------------
# Main detection (pattern matching on graph)
# -------------------------------
def _cluster_conjunctions_for_detection(pos, members, orb=4.0):
    members_sorted = sorted(members, key=lambda m: pos[m])
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

def _detect_shapes_for_members(pos, members, parent_idx, sid_start=0, G=None, widen_orb=False):
    """
    Detect shapes for the given members of a parent pattern.

    - Strict mode: only use edges already present in G for this pattern.
    - Approx mode: allow "almost" edges if within 4.5° orb.
    """
    if not members or G is None:
        return [], sid_start

    # 1) Cluster conjunctions into representative nodes
    rep_pos, rep_map, rep_anchor = _cluster_conjunctions_for_detection(pos, list(members))
    R = list(rep_pos.keys())

    # 2) Build lookup of parent edges limited to these members (single source of truth)
    edge_lookup = {}
    for u, v, data in G.edges(data=True):
        if u in members and v in members:
            a, b = rep_anchor[u], rep_anchor[v]
            edge_lookup[frozenset([a, b])] = data.get("aspect")

    shapes, seen, sid = [], set(), sid_start

    def has_edge(a, b, aspect):
        """Return True if parent says this rep edge has `aspect`; 'approx' if widen-orb qualifies."""
        key = frozenset([a, b])
        if key in edge_lookup and edge_lookup[key] == aspect:
            return True
        if widen_orb:
            # Only in approx mode: allow near-miss
            d1, d2 = rep_pos[a], rep_pos[b]
            angle = abs(d1 - d2) % 360
            if angle > 180:
                angle = 360 - angle
            target = ASPECTS[aspect]["angle"]
            if abs(angle - target) <= 4.5:
                return "approx"
        return False

    def add_once(sh_type, node_list, candidate_edges, suppresses=None):
        nonlocal sid
        key = (sh_type, tuple(sorted(node_list)))
        if key in seen:
            return False
        seen.add(key)

        specs = []
        for (x, y), asp in candidate_edges:
            status = has_edge(x, y, asp)
            if status is True:
                specs.append(((x, y), asp))
            elif status == "approx":
                specs.append(((x, y), f"{asp}_approx"))

        if specs:
            sid = _add_shape(
                shapes, sh_type, parent_idx, sid,
                node_list, specs, rep_map, rep_anchor, suppresses
            )
        return True
    
    # -----------------------
    # SHAPE DETECTION LOGIC
    # -----------------------

    # --- Envelope ---
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
                    ((a, b), "Sextile"),
                    ((b, c), "Sextile"),
                    ((c, d), "Sextile"),
                    ((d, e), "Sextile"),
                    ((a, d), "Opposition"),
                    ((b, e), "Opposition"),
                    ((a, e), "Trine"),
                    ((b, d), "Trine"),
                ]
                add_once("Envelope", (a, b, c, d, e), candidate_edges,
                         {"suppress": suppresses, "keep": keep})
                break

    # --- Grand Cross ---
    for quad in combinations(R, 4):
        a, b, c, d = quad
        if (has_edge(a, c, "Opposition") and has_edge(b, d, "Opposition") and
            has_edge(a, b, "Square") and has_edge(b, c, "Square") and
            has_edge(c, d, "Square") and has_edge(d, a, "Square")):
            suppresses = {
                "T-Square": {
                    frozenset([a, b, c]),
                    frozenset([b, c, d]),
                    frozenset([c, d, a]),
                    frozenset([d, a, b]),
                }
            }
            candidate_edges = [
                ((a, c), "Opposition"),
                ((b, d), "Opposition"),
                ((a, b), "Square"),
                ((b, c), "Square"),
                ((c, d), "Square"),
                ((d, a), "Square"),
            ]
            add_once("Grand Cross", (a, b, c, d), candidate_edges,
                     {"suppress": suppresses})

    # --- Mystic Rectangle ---
    for quad in combinations(R, 4):
        a, b, c, d = quad
        if (has_edge(a, c, "Opposition") and has_edge(b, d, "Opposition") and
            has_edge(a, b, "Sextile") and has_edge(c, d, "Sextile") and
            has_edge(a, d, "Trine") and has_edge(b, c, "Trine")):
            suppresses = {
                "Wedge": {
                    frozenset([a, b, c]), frozenset([a, b, d]),
                    frozenset([b, c, d]), frozenset([a, c, d]),
                }
            }
            candidate_edges = [
                ((a, c), "Opposition"),
                ((b, d), "Opposition"),
                ((a, b), "Sextile"),
                ((c, d), "Sextile"),
                ((a, d), "Trine"),
                ((b, c), "Trine"),
            ]
            add_once("Mystic Rectangle", (a, b, c, d), candidate_edges,
                     {"suppress": suppresses})

    # --- Cradle ---
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
                ((a, b), "Sextile"),
                ((b, c), "Sextile"),
                ((c, d), "Sextile"),
                ((a, d), "Opposition"),
                ((a, c), "Trine"),
                ((b, d), "Trine"),
            ]
            add_once("Cradle", (a, b, c, d), candidate_edges,
                     {"suppress": suppresses})
            break

    # --- Kite ---
    for quad in combinations(R, 4):
        for trio in combinations(quad, 3):
            a, b, c = trio
            apex = list(set(quad) - set(trio))[0]
            if (has_edge(a, b, "Trine") and has_edge(b, c, "Trine") and
                has_edge(a, c, "Trine")):
                for t in (a, b, c):
                    if has_edge(apex, t, "Opposition"):
                        rest = [x for x in (a, b, c) if x != t]
                        suppresses = {
                            "Wedge": {
                                frozenset([a, b, apex]),
                                frozenset([b, c, apex]),
                                frozenset([a, c, apex]),
                            },
                            "Sextile Wedge": {
                                frozenset([apex, rest[0], a]),
                                frozenset([apex, rest[1], b]),
                            },
                            "Grand Trine": {frozenset([a, b, c])},
                        }
                        candidate_edges = [
                            ((a, b), "Trine"),
                            ((b, c), "Trine"),
                            ((a, c), "Trine"),
                            ((apex, t), "Opposition"),
                            ((apex, rest[0]), "Sextile"),
                            ((apex, rest[1]), "Sextile"),
                        ]
                        add_once("Kite", (a, b, c, apex), candidate_edges,
                                 {"suppress": suppresses})
                        break

    # --- Grand Trine ---
    for trio in combinations(R, 3):
        a, b, c = trio
        if (has_edge(a, b, "Trine") and has_edge(b, c, "Trine") and
            has_edge(a, c, "Trine")):
            candidate_edges = [
                ((a, b), "Trine"),
                ((b, c), "Trine"),
                ((a, c), "Trine"),
            ]
            add_once("Grand Trine", (a, b, c), candidate_edges)

    # --- T-Square ---
    for trio in combinations(R, 3):
        for apex in trio:
            a, b = [n for n in trio if n != apex]
            if (has_edge(a, b, "Opposition") and
                has_edge(apex, a, "Square") and
                has_edge(apex, b, "Square")):
                candidate_edges = [
                    ((a, b), "Opposition"),
                    ((apex, a), "Square"),
                    ((apex, b), "Square"),
                ]
                add_once("T-Square", (a, b, apex), candidate_edges)
                break

    # --- Wedge ---
    for trio in combinations(R, 3):
        pairs = list(combinations(trio, 2))
        opp = [p for p in pairs if has_edge(p[0], p[1], "Opposition")]
        tri = [p for p in pairs if has_edge(p[0], p[1], "Trine")]
        sex = [p for p in pairs if has_edge(p[0], p[1], "Sextile")]
        if len(opp) == 1 and len(tri) == 1 and len(sex) == 1:
            candidate_edges = [
                (opp[0], "Opposition"),
                (tri[0], "Trine"),
                (sex[0], "Sextile"),
            ]
            add_once("Wedge", trio, candidate_edges)

    # --- Sextile Wedge ---
    for trio in combinations(R, 3):
        pairs = list(combinations(trio, 2))
        tri = [p for p in pairs if has_edge(p[0], p[1], "Trine")]
        sex = [p for p in pairs if has_edge(p[0], p[1], "Sextile")]
        opp = [p for p in pairs if has_edge(p[0], p[1], "Opposition")]
        if len(tri) == 1 and len(sex) == 2 and not opp:
            candidate_edges = [
                (tri[0], "Trine"),
                (sex[0], "Sextile"),
                (sex[1], "Sextile"),
            ]
            add_once("Sextile Wedge", trio, candidate_edges)

    return shapes, sid


def detect_shapes(pos, patterns, G):
    """Main entrypoint for strict + approx shape detection."""
    shapes = []
    sid = 0

    # --- strict pass ---
    for parent_idx, mems in enumerate(patterns):
        shapes_here, sid = _detect_shapes_for_members(
            pos, mems, parent_idx, sid, G, widen_orb=False
        )
        shapes.extend(shapes_here)

    # collect all nodes used in strict shapes
    strict_nodes = set()
    for s in shapes:
        strict_nodes.update(s["members"])

    # --- approx pass (optional widened orb) ---
    for parent_idx, mems in enumerate(patterns):
        leftovers = [m for m in mems if m not in strict_nodes]
        if leftovers:
            approx_shapes, sid = _detect_shapes_for_members(
                pos, leftovers, parent_idx, sid, G, widen_orb=True
            )
            for s in approx_shapes:
                s["approx"] = True
            shapes.extend(approx_shapes)

    return shapes

def _deduplicate_shapes(shapes, rep_map):
    seen = {}
    deduped = []
    for s in shapes:
        expanded = []
        for m in s["members"]:
            for rep, cluster in rep_map.items():
                if m in cluster:
                    expanded.extend(cluster)
                    break
            else:
                expanded.append(m)
        expanded = tuple(sorted(set(expanded)))
        key = (s["type"], expanded)
        if key not in seen:
            new_s = dict(s)
            new_s["members"] = expanded
            deduped.append(new_s)
            seen[key] = True
    return deduped


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
                                print(f"KEEP (override): shape{s_small['id']} ({s_small['type']}, parent {s_small['parent']}) "
                                      f"protected by shape{env['id']} ({env['type']}).")
                                break
                        if keep_hit:
                            continue
                        print(f"SUPPRESS: shape{s_small['id']} ({s_small['type']}, parent {s_small['parent']}) "
                              f"BY shape{s_big['id']} ({s_big['type']}).")
                        suppressed.add(j)

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
