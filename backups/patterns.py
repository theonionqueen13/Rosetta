# rosetta/patterns.py
import networkx as nx
from itertools import combinations, permutations
from rosetta.lookup import ASPECTS


# -------------------------------
# Aspect graph (patterns as connected components)
# -------------------------------
def build_aspect_graph(pos, return_graph=False):
    MAJORS = ("Conjunction", "Sextile", "Square", "Trine", "Opposition")
    G = nx.Graph()
    for p1, p2 in combinations(pos.keys(), 2):
        d1, d2 = pos[p1], pos[p2]
        angle = abs(d1 - d2) % 360
        if angle > 180:
            angle = 360 - angle
        for asp in MAJORS:
            data = ASPECTS[asp]
            if abs(angle - data["angle"]) <= data["orb"]:
                G.add_edge(p1, p2, aspect=asp)
                break
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
    """
    Collapse tightly conjunct members into clusters.
    A cluster is valid if all members are within `orb` degrees,
    or if they are linked by "bridging" members (chained within orb).
    Returns:
        rep_pos: {rep_node: mean_degree}
        rep_map: {rep_node: [all members]}
        rep_anchor: {member: rep_node}
    """
    # Sort members by degree
    members_sorted = sorted(members, key=lambda m: pos[m])
    clusters = []
    current = [members_sorted[0]]

    for m in members_sorted[1:]:
        prev = current[-1]
        gap = abs(pos[m] - pos[prev])
        if gap <= orb:
            # stays in the same cluster
            current.append(m)
        else:
            # gap too large → close cluster, start new
            clusters.append(current)
            current = [m]
    clusters.append(current)

    # Now build maps
    rep_pos, rep_map, rep_anchor = {}, {}, {}
    for cluster in clusters:
        rep = cluster[0]  # representative = first member
        degrees = [pos[m] for m in cluster]
        mean_deg = sum(degrees) / len(degrees)
        rep_pos[rep] = mean_deg
        rep_map[rep] = cluster
        for m in cluster:
            rep_anchor[m] = rep

    return rep_pos, rep_map, rep_anchor

from rosetta.drawing import enumerate_major_edges  # <- add this import at top of patterns.py

# ...

def _detect_shapes_for_members(pos, members, parent_idx, sid_start=0, G=None, widen_orb=False):
    """
    Detect shapes for the given members of a parent pattern.
    - Conjunctions are clustered into rep nodes.
    - Aspect checks are done using edges already present in G.
    - If widen_orb=True, aspects can match with tolerance 4.5° even if not in G.
    """
    if not members:
        return [], sid_start

    # 1. Cluster conjunctions into representative nodes
    rep_pos, rep_map, rep_anchor = _cluster_conjunctions_for_detection(pos, list(members))
    R = list(rep_pos.keys())

    # 2. Build a rep-node graph using edges from G
    G_rep = nx.Graph()
    for a, b in combinations(R, 2):
        planets_a, planets_b = rep_map[a], rep_map[b]
        for pa in planets_a:
            for pb in planets_b:
                if G.has_edge(pa, pb):
                    asp = G.edges[pa, pb]["aspect"]
                    G_rep.add_edge(a, b, aspect=asp)

    # Shapes and bookkeeping
    shapes, seen, sid = [], set(), sid_start

    def add_once(sh_type, node_list, edge_specs, suppresses=None):
        nonlocal sid
        key = (sh_type, tuple(sorted(node_list)))
        if key in seen:
            return False
        seen.add(key)
        shape_id = sid
        sid = _add_shape(
            shapes, sh_type, parent_idx, sid,
            node_list, edge_specs, rep_map, rep_anchor, suppresses
        )
        # Tag approx shapes
        if widen_orb:
            shapes[-1]["approx"] = True
        return True

    def has_edge(a, b, aspect):
        # Parent edges first (strict)
        if G_rep.has_edge(a, b) and G_rep.edges[a, b]["aspect"] == aspect:
            return True

    # -------------------------------
    # SHAPE DETECTIONS (your existing logic, unchanged)
    # -------------------------------

    # --- Envelope ---
    for quint in combinations(R, 5):
        for perm in permutations(quint):
            a, b, c, d, e = perm
            if (has_edge(a, b, "Sextile") and has_edge(b, c, "Sextile") and
                has_edge(c, d, "Sextile") and has_edge(d, e, "Sextile")):

                suppresses = {
                    "Sextile Wedge": {
                        frozenset([a, b, c]),
                        frozenset([c, d, e]),
                    },
                    "Kite": {
                        frozenset([a, b, c, e]),
                        frozenset([a, c, d, e]),
                    },
                    "Cradle": {
                        frozenset([a, b, c, d]),
                        frozenset([b, c, d, e]),
                    },
                    "Wedge": {
                        frozenset([a, b, d]),
                        frozenset([c, d, e]),
                        frozenset([a, c, d]),
                        frozenset([a, b, e]),
                        frozenset([a, d, e]),
                        frozenset([b, c, e]),
                        frozenset([b, d, e]),
                    },
                }

                keep = {
                    "Sextile Wedge": {frozenset([b, c, d])},
                    "Mystic Rectangle": {frozenset([a, b, d, e])},
                    "Grand Trine": {frozenset([a, c, e])},
                }

                specs = []
                for (x, y), asp in candidate_edges:
                    status = has_edge(x, y, asp)
                    if status == True:
                        specs.append(((x, y), asp))
                    elif status == "approx":
                        specs.append(((x, y), f"{asp}_approx"))  # tag for lighter color

                add_once(
                    "Envelope",
                    (a, b, c, d, e),
                    [
                        ((a, b), "Sextile"),
                        ((b, c), "Sextile"),
                        ((c, d), "Sextile"),
                        ((d, e), "Sextile"),
                        ((a, d), "Opposition"),
                        ((b, e), "Opposition"),
                        ((a, e), "Trine"),
                        ((b, d), "Trine"),
                    ],
                    {"suppress": suppresses, "keep": keep},
                )
                break

    # --- Envelope --- (5 nodes, 4 consecutive Sextiles)
    for quint in combinations(R, 5):
        for perm in permutations(quint):
            a, b, c, d, e = perm
            if (has_edge(a, b, "Sextile") and has_edge(b, c, "Sextile") and
                has_edge(c, d, "Sextile") and has_edge(d, e, "Sextile")):

                suppresses = {
                    "Sextile Wedge": {
                        frozenset([a, b, c]),
                        frozenset([c, d, e]),
                    },
                    "Kite": {
                        frozenset([a, b, c, e]),
                        frozenset([a, c, d, e]),
                    },
                    "Cradle": {
                        frozenset([a, b, c, d]),
                        frozenset([b, c, d, e]),
                    },
                    "Wedge": {
                        frozenset([a, b, d]),
                        frozenset([c, d, e]),
                        frozenset([a, c, d]),
                        frozenset([a, b, e]),
                        frozenset([a, d, e]),
                        frozenset([b, c, e]),
                        frozenset([b, d, e]),
                    },
                }
                keep = {
                    "Sextile Wedge": {frozenset([b, c, d])},
                    "Mystic Rectangle": {frozenset([a, b, d, e])},
                    "Grand Trine": {frozenset([a, c, e])},
                }

                specs = []
                for (x, y), asp in candidate_edges:
                    status = has_edge(x, y, asp)
                    if status == True:
                        specs.append(((x, y), asp))
                    elif status == "approx":
                        specs.append(((x, y), f"{asp}_approx"))  # tag for lighter color

                add_once(
                    "Envelope",
                    (a, b, c, d, e),
                    [
                        ((a, b), "Sextile"),
                        ((b, c), "Sextile"),
                        ((c, d), "Sextile"),
                        ((d, e), "Sextile"),
                        ((a, d), "Opposition"),
                        ((b, e), "Opposition"),
                        ((a, e), "Trine"),
                        ((b, d), "Trine"),
                    ],
                    {"suppress": suppresses, "keep": keep},
                )
                break

    # --- Grand Cross --- (4 nodes, 2 Oppositions + 4 Squares)
    for quad in combinations(R, 4):
        a, b, c, d = quad
        if (has_edge(a, c, "Opposition") and
            has_edge(b, d, "Opposition") and
            has_edge(a, b, "Square") and
            has_edge(b, c, "Square") and
            has_edge(c, d, "Square") and
            has_edge(d, a, "Square")):

            suppresses = {
                "T-Square": {
                    frozenset([a, b, c]),
                    frozenset([b, c, d]),
                    frozenset([c, d, a]),
                    frozenset([d, a, b]),
                }
            }

            specs = []
            for (x, y), asp in candidate_edges:
                status = has_edge(x, y, asp)
                if status == True:
                    specs.append(((x, y), asp))
                elif status == "approx":
                    specs.append(((x, y), f"{asp}_approx"))  # tag for lighter color

            add_once(
                "Grand Cross",
                (a, b, c, d),
                [
                    ((a, c), "Opposition"),
                    ((b, d), "Opposition"),
                    ((a, b), "Square"),
                    ((b, c), "Square"),
                    ((c, d), "Square"),
                    ((d, a), "Square"),
                ],
                {"suppress": suppresses}
            )

    # --- Mystic Rectangle --- (4 nodes, 2 Oppositions, 2 Trines, 2 Sextiles)
    for quad in combinations(R, 4):
        a, b, c, d = quad
        if (has_edge(a, c, "Opposition") and
            has_edge(b, d, "Opposition") and
            has_edge(a, b, "Sextile") and
            has_edge(c, d, "Sextile") and
            has_edge(a, d, "Trine") and
            has_edge(b, c, "Trine")):

            suppresses = {
                "Wedge": {
                    frozenset([a, b, c]),
                    frozenset([a, b, d]),
                    frozenset([b, c, d]),
                    frozenset([a, c, d]),
                }
            }

            specs = []
            for (x, y), asp in candidate_edges:
                status = has_edge(x, y, asp)
                if status == True:
                    specs.append(((x, y), asp))
                elif status == "approx":
                    specs.append(((x, y), f"{asp}_approx"))  # tag for lighter color

            add_once(
                "Mystic Rectangle",
                (a, b, c, d),
                [
                    ((a, c), "Opposition"),
                    ((b, d), "Opposition"),
                    ((a, b), "Sextile"),
                    ((c, d), "Sextile"),
                    ((a, d), "Trine"),
                    ((b, c), "Trine"),
                ],
                {"suppress": suppresses}
            )

    # --- Cradle --- (4 nodes, 3 Sextiles, 2 Trines, 1 Opposition)
    for quad in permutations(R, 4):
        a, b, c, d = quad
        if (has_edge(a, b, "Sextile") and
            has_edge(b, c, "Sextile") and
            has_edge(c, d, "Sextile") and
            has_edge(a, d, "Opposition") and
            has_edge(a, c, "Trine") and
            has_edge(b, d, "Trine")):

            suppresses = {
                "Wedge": {
                    frozenset([a, b, d]),
                    frozenset([a, c, d]),
                },
                "Sextile Wedge": {
                    frozenset([a, b, c]),
                    frozenset([b, c, d]),
                },
            }

            specs = []
            for (x, y), asp in candidate_edges:
                status = has_edge(x, y, asp)
                if status == True:
                    specs.append(((x, y), asp))
                elif status == "approx":
                    specs.append(((x, y), f"{asp}_approx"))  # tag for lighter color

            add_once(
                "Cradle",
                (a, b, c, d),
                [
                    ((a, b), "Sextile"),
                    ((b, c), "Sextile"),
                    ((c, d), "Sextile"),
                    ((a, d), "Opposition"),
                    ((a, c), "Trine"),
                    ((b, d), "Trine"),
                ],
                {"suppress": suppresses}
            )
            break

    # --- Kite --- (4 nodes: Grand Trine + Apex Opposite + 2 Sextiles)
    for quad in combinations(R, 4):
        for trio in combinations(quad, 3):
            a, b, c = trio
            apex = list(set(quad) - set(trio))[0]

            if (has_edge(a, b, "Trine") and
                has_edge(b, c, "Trine") and
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
                            "Grand Trine": {
                                frozenset([a, b, c]),
                            },
                        }

                        specs = []
                        for (x, y), asp in candidate_edges:
                            status = has_edge(x, y, asp)
                            if status == True:
                                specs.append(((x, y), asp))
                            elif status == "approx":
                                specs.append(((x, y), f"{asp}_approx"))  # tag for lighter color

                        add_once(
                            "Kite",
                            (a, b, c, apex),
                            [
                                ((a, b), "Trine"),
                                ((b, c), "Trine"),
                                ((a, c), "Trine"),
                                ((apex, t), "Opposition"),
                                ((apex, rest[0]), "Sextile"),
                                ((apex, rest[1]), "Sextile"),
                            ],
                            {"suppress": suppresses}
                        )
                        break

    # --- Grand Trine ---
    for trio in combinations(R, 3):
        a, b, c = trio
        if (has_edge(a, b, "Trine") and
            has_edge(b, c, "Trine") and
            has_edge(a, c, "Trine")):


            specs = []
            for (x, y), asp in candidate_edges:
                status = has_edge(x, y, asp)
                if status == True:
                    specs.append(((x, y), asp))
                elif status == "approx":
                    specs.append(((x, y), f"{asp}_approx"))  # tag for lighter color

            add_once(
                "Grand Trine",
                (a, b, c),
                [
                    ((a, b), "Trine"),
                    ((b, c), "Trine"),
                    ((a, c), "Trine"),
                ]
            )

    # --- T-Square ---
    for trio in combinations(R, 3):
        for apex in trio:
            a, b = [n for n in trio if n != apex]
            if (has_edge(a, b, "Opposition") and
                has_edge(apex, a, "Square") and
                has_edge(apex, b, "Square")):

                specs = []
                for (x, y), asp in candidate_edges:
                    status = has_edge(x, y, asp)
                    if status == True:
                        specs.append(((x, y), asp))
                    elif status == "approx":
                        specs.append(((x, y), f"{asp}_approx"))  # tag for lighter color

                add_once(
                    "T-Square", (a, b, apex),
                    [
                        ((a, b), "Opposition"),
                        ((apex, a), "Square"),
                        ((apex, b), "Square"),
                    ]
                )
                break

    # --- Wedge ---
    for trio in combinations(R, 3):
        pairs = list(combinations(trio, 2))
        opp = [p for p in pairs if has_edge(p[0], p[1], "Opposition")]
        tri = [p for p in pairs if has_edge(p[0], p[1], "Trine")]
        sex = [p for p in pairs if has_edge(p[0], p[1], "Sextile")]
        if len(opp) == 1 and len(tri) == 1 and len(sex) == 1:

            specs = []
            for (x, y), asp in candidate_edges:
                status = has_edge(x, y, asp)
                if status == True:
                    specs.append(((x, y), asp))
                elif status == "approx":
                    specs.append(((x, y), f"{asp}_approx"))  # tag for lighter color

            add_once(
                "Wedge", trio,
                [
                    (opp[0], "Opposition"),
                    (tri[0], "Trine"),
                    (sex[0], "Sextile"),
                ]
            )

    # --- Sextile Wedge ---
    for trio in combinations(R, 3):
        pairs = list(combinations(trio, 2))
        tri = [p for p in pairs if has_edge(p[0], p[1], "Trine")]
        sex = [p for p in pairs if has_edge(p[0], p[1], "Sextile")]
        opp = [p for p in pairs if has_edge(p[0], p[1], "Opposition")]
        if len(tri) == 1 and len(sex) == 2 and not opp:

            specs = []
            for (x, y), asp in candidate_edges:
                status = has_edge(x, y, asp)
                if status == True:
                    specs.append(((x, y), asp))
                elif status == "approx":
                    specs.append(((x, y), f"{asp}_approx"))  # tag for lighter color

            add_once(
                "Sextile Wedge", trio,
                [
                    (tri[0], "Trine"),
                    (sex[0], "Sextile"),
                    (sex[1], "Sextile"),
                ]
            )

    return shapes, sid

def _deduplicate_shapes(shapes, rep_map):
    """
    Collapse shapes that only differ by members of the same conjunction cluster.
    Example: (IC, Sun, South Node, Eros) vs (IC, Sun, Eros) → one shape.
    """
    seen = {}
    deduped = []

    for s in shapes:
        # Expand each shape's members to full cluster membership
        expanded = []
        for m in s["members"]:
            for rep, cluster in rep_map.items():
                if m in cluster:
                    expanded.extend(cluster)
                    break
            else:
                expanded.append(m)

        # Sort + unique
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
        # --- suppression pass ---
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

                    # Does this small shape match the suppression target?
                    if frozenset(s_small["members"]) == sub_members:
                        # Check if ANY parent Envelope (or other keeper) says keep this
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

# -------------------------------
# Public API
# -------------------------------
def detect_shapes(pos, patterns, G):
    shapes = []
    sid = 0

    # --- strict pass ---
    for parent_idx, mems in enumerate(patterns):
        shapes_here, sid = _detect_shapes_for_members(pos, mems, parent_idx, sid, G)
        shapes.extend(shapes_here)

    # collect nodes used in strict shapes
    strict_nodes = set()
    for s in shapes:
        strict_nodes.update(s["members"])

    # --- approx pass ---
    for parent_idx, mems in enumerate(patterns):
        leftovers = [m for m in mems if m not in strict_nodes]
        if leftovers:
            approx_shapes, sid = _detect_shapes_for_members(
                pos, leftovers, parent_idx, sid, G, widen_orb=True
            )
            for s in approx_shapes:
                s["approx"] = True
            shapes.extend(approx_shapes)

    # --- suppression pass ---
    # --- suppression pass (honors keep/override) ---
    suppressed = set()

    def _same_members(small, target_fset):
        return frozenset(small["members"]) == target_fset

    for i, s_big in enumerate(shapes):
        sup = s_big.get("suppresses")
        if not sup:
            continue

        sup_sets = sup.get("suppress", {})
        # NOTE: we don't actually need keep_sets on the big shape here;
        # we scan all shapes for potential keepers below.
        _ = sup.get("keep", {})

        for s_type, targets in sup_sets.items():
            for target in targets:
                for j, s_small in enumerate(shapes):
                    if j in suppressed:
                        continue
                    if s_small["type"] != s_type:
                        continue
                    # keep suppression within the same parent group
                    if s_small["parent"] != s_big["parent"]:
                        continue
                    if not _same_members(s_small, target):
                        continue

                    # Is there ANY shape (e.g., Envelope) that explicitly keeps this one?
                    protected = False
                    for keeper in shapes:
                        kdata = keeper.get("suppresses", {})
                        kkeep = kdata.get("keep", {})
                        if keeper["parent"] != s_small["parent"]:
                            continue
                        if s_small["type"] in kkeep and frozenset(s_small["members"]) in kkeep[s_small["type"]]:
                            protected = True
                            print(
                                f"KEEP (override): shape{s_small['id']} ({s_small['type']}, parent {s_small['parent']}) "
                                f"protected by shape{keeper['id']} ({keeper['type']})."
                            )
                            break

                    if protected:
                        continue

                    print(
                        f"SUPPRESS: shape{s_small['id']} ({s_small['type']}, parent {s_small['parent']}) "
                        f"BY shape{s_big['id']} ({s_big['type']})."
                    )
                    suppressed.add(j)

    shapes_after = [s for idx, s in enumerate(shapes) if idx not in suppressed]

    # --- final shape list after suppression ---
    shapes_after = [s for i, s in enumerate(shapes) if i not in suppressed]

    print("SHAPES AFTER SUPPRESSION:")
    for s in shapes_after:
        print(f" - shape{s['id']}: {s['type']} | parent={s['parent']} | members={s['members']}")

    return shapes_after

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
