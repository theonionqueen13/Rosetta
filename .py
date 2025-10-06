# --- reload rosetta.patterns so we always have the latest version ---
import importlib
import rosetta.patterns as _pat_mod

importlib.reload(_pat_mod)

# now grab the live functions from the reloaded module
build_aspect_graph = _pat_mod.build_aspect_graph
detect_minor_links_with_singletons = _pat_mod.detect_minor_links_with_singletons
generate_combo_groups = _pat_mod.generate_combo_groups
detect_shapes = _pat_mod.detect_shapes
internal_minor_edges_for_pattern = _pat_mod.internal_minor_edges_for_pattern

# optional: sanity check to prove what signature is live
import inspect

st.caption(f"detect_shapes sig: {inspect.signature(detect_shapes)}")

# -------------------------------
# Aspect graph (patterns as connected components)
# -------------------------------


def build_aspect_graph(pos):
    """Build connected components using MAJOR aspects only."""
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
    return list(nx.connected_components(G))


def detect_minor_links_with_singletons(pos, patterns):
    """Find minor aspect connections and map singletons."""
    minor_aspects = ["Quincunx", "Sesquisquare"]
    connections = []

    # Create pattern mapping
    pattern_map = {}
    for idx, pattern in enumerate(patterns):
        for planet in pattern:
            pattern_map[planet] = idx

    # Handle singleton planets (not in any pattern)
    all_patterned = set(pattern_map.keys())
    all_placements = set(pos.keys())
    singletons = all_placements - all_patterned
    singleton_index_offset = len(patterns)
    singleton_map = {
        planet: singleton_index_offset + i for i, planet in enumerate(singletons)
    }
    pattern_map.update(singleton_map)

    # Find minor aspect connections
    for p1, p2 in combinations(pos.keys(), 2):
        angle = abs(pos[p1] - pos[p2])
        if angle > 180:
            angle = 360 - angle

        for asp in minor_aspects:
            if abs(ASPECTS[asp]["angle"] - angle) <= ASPECTS[asp]["orb"]:
                pat1 = pattern_map.get(p1)
                pat2 = pattern_map.get(p2)
                if pat1 is not None and pat2 is not None:
                    connections.append((p1, p2, asp, pat1, pat2))
                break

    return connections, singleton_map


def generate_combo_groups(filaments):
    """Generate combo groups from filaments."""
    G = nx.Graph()
    for _, _, _, pat1, pat2 in filaments:
        if pat1 != pat2:
            G.add_edge(pat1, pat2)
    return [sorted(list(g)) for g in nx.connected_components(G) if len(g) > 1]


# -------------------------------
# Angle helpers
# -------------------------------


def angle_delta(deg1, deg2):
    diff = abs(deg1 - deg2) % 360
    return diff if diff <= 180 else 360 - diff


def aspect_match(angle, aspect_name, open_factor=1.5, extra_slop=2.0):
    asp = ASPECTS[aspect_name]
    target, orb = asp["angle"], asp["orb"]
    delta = abs(angle - target)

    if delta <= orb:
        return "present", delta
    elif delta <= max(orb * open_factor, orb + extra_slop):
        return "near", delta
    else:
        return None, delta


# -------------------------------
# Shape detection
# -------------------------------


def _detect_shapes_for_members(pos, members, parent_idx, sid_start=0):
    """
    Detect shapes (T-Square, Kite, Yod, etc.) within a given set of members.
    Returns (shapes, next_sid).
    """
    shapes = []
    sid = sid_start
    from itertools import combinations, permutations

    # --- 3-planet shapes ---
    for trio in combinations(members, 3):
        A, B, C = trio

        # T-Square
        for x, y, z in permutations(trio):
            status1 = aspect_match(angle_delta(pos[x], pos[y]), "Opposition")[0]
            status2 = aspect_match(angle_delta(pos[x], pos[z]), "Square")[0]
            status3 = aspect_match(angle_delta(pos[y], pos[z]), "Square")[0]
            if status1 == status2 == status3 == "present":
                shapes.append(
                    {
                        "id": f"shape{sid}",
                        "type": "T-Square",
                        "members": [x, y, z],
                        "edges": [
                            ((x, y), "Opposition"),
                            ((x, z), "Square"),
                            ((y, z), "Square"),
                        ],
                        "parent": parent_idx,
                    }
                )
                sid += 1

        # Yod
        status1 = aspect_match(angle_delta(pos[A], pos[B]), "Sextile")[0]
        status2 = aspect_match(angle_delta(pos[A], pos[C]), "Quincunx")[0]
        status3 = aspect_match(angle_delta(pos[B], pos[C]), "Quincunx")[0]
        if status1 == status2 == status3 == "present":
            shapes.append(
                {
                    "id": f"shape{sid}",
                    "type": "Yod",
                    "members": [A, B, C],
                    "edges": [
                        ((A, B), "Sextile"),
                        ((A, C), "Quincunx"),
                        ((B, C), "Quincunx"),
                    ],
                    "parent": parent_idx,
                }
            )
            sid += 1

    # --- 4-planet shapes ---
    for quad in combinations(members, 4):
        for trio in combinations(quad, 3):
            apex = list(set(quad) - set(trio))[0]
            tA, tB, tC = trio
            if (
                aspect_match(angle_delta(pos[tA], pos[tB]), "Trine")[0] == "present"
                and aspect_match(angle_delta(pos[tB], pos[tC]), "Trine")[0] == "present"
                and aspect_match(angle_delta(pos[tA], pos[tC]), "Trine")[0] == "present"
                and aspect_match(angle_delta(pos[apex], pos[tA]), "Opposition")[0]
                == "present"
            ):
                shapes.append(
                    {
                        "id": f"shape{sid}",
                        "type": "Kite",
                        "members": [tA, tB, tC, apex],
                        "edges": [
                            ((tA, tB), "Trine"),
                            ((tB, tC), "Trine"),
                            ((tA, tC), "Trine"),
                            ((apex, tA), "Opposition"),
                            ((apex, tB), "Sextile"),
                            ((apex, tC), "Sextile"),
                        ],
                        "parent": parent_idx,
                    }
                )
                sid += 1

    return shapes, sid


def detect_shapes(pos, patterns):
    """Detect closed/open shapes *within each parent pattern*."""
    results = []
    sid = 0
    for parent_idx, members in enumerate(patterns):
        member_pos = {m: pos[m] for m in members if m in pos}
        shapes_here, sid = _detect_shapes_for_members(pos, members, parent_idx, sid)
        results.extend(shapes_here)
    return results


def internal_minor_edges_for_pattern(pos, members):
    """
    Return all minor-aspect (Quincunx, Sesquisquare) edges between planets
    that belong to the same parent pattern.
    """
    minors = []
    for i in range(len(members)):
        for j in range(i + 1, len(members)):
            p1, p2 = members[i], members[j]
            if p1 not in pos or p2 not in pos:
                continue
            angle = abs(pos[p1] - pos[p2]) % 360
            if angle > 180:
                angle = 360 - angle
            for asp in ["Quincunx", "Sesquisquare"]:
                data = ASPECTS[asp]
                if abs(angle - data["angle"]) <= data["orb"]:
                    minors.append(((p1, p2), asp))
                    break
    return minors
