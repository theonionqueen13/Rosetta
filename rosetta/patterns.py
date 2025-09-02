# rosetta/patterns.py
import networkx as nx
import math
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
def angle_delta(deg1, deg2):
    diff = abs(deg1 - deg2) % 360
    return diff if diff <= 180 else 360 - diff

def aspect_match(angle, aspect_name):
    asp = ASPECTS[aspect_name]
    target, orb = asp["angle"], asp["orb"]
    delta = abs(angle - target)
    if delta <= orb:
        return "present", delta
    elif delta <= orb + 1.0:  # tolerance window
        return "near", delta
    return None, delta

def within_deg(angle, target, orb, pad=0.0):
    """Return True if |angle - target| <= orb + pad."""
    return abs(angle - target) <= (orb + pad)

def _mean_deg(degs):
    s = sum(math.sin(math.radians(d)) for d in degs)
    c = sum(math.cos(math.radians(d)) for d in degs)
    ang = math.degrees(math.atan2(s, c))
    if ang < 0:
        ang += 360
    return ang

def _cluster_conjunctions_for_detection(pos, members, orb_deg=3.0):
    remaining = set(members)
    reps = []
    rep_map = {}
    while remaining:
        seed = min(remaining, key=lambda m: pos[m])
        cluster = [seed]
        remaining.remove(seed)
        to_check = list(remaining)
        for m in to_check:
            if angle_delta(pos[m], pos[seed]) <= orb_deg:
                cluster.append(m)
                remaining.remove(m)
        rep_id = "|".join(sorted(cluster))
        rep_map[rep_id] = cluster
        reps.append(rep_id)
    rep_pos = {rep: _mean_deg([pos[m] for m in rep_map[rep]]) for rep in reps}
    rep_anchor = {rep: rep_map[rep][0] for rep in reps}
    return rep_pos, rep_map, rep_anchor

def _status(rep_pos, a, b, aspect):
    return aspect_match(angle_delta(rep_pos[a], rep_pos[b]), aspect)[0]

def _add_shape(shapes, sh_type, parent_idx, sid, node_list, edge_specs, rep_map, rep_anchor):
    # Expand members back to originals
    members_expanded = []
    for r in node_list:
        members_expanded.extend(rep_map[r])
    edges_expanded = [((rep_anchor[a], rep_anchor[b]), asp) for ((a, b), asp) in edge_specs]
    shape = {
        "id": f"shape{sid}",
        "type": sh_type,
        "members": members_expanded,
        "edges": edges_expanded,
        "parent": parent_idx
    }
    shapes.append(shape)
    return sid + 1

# -------------------------------
# Helpers
# -------------------------------
def angle_delta(deg1, deg2):
    diff = abs(deg1 - deg2) % 360
    return diff if diff <= 180 else 360 - diff

def aspect_match(angle, aspect_name):
    asp = ASPECTS[aspect_name]
    target, orb = asp["angle"], asp["orb"]
    delta = abs(angle - target)
    if delta <= orb:
        return "present", delta
    elif delta <= orb + 1.0:  # tolerance window
        return "near", delta
    return None, delta

def _mean_deg(degs):
    s = sum(math.sin(math.radians(d)) for d in degs)
    c = sum(math.cos(math.radians(d)) for d in degs)
    ang = math.degrees(math.atan2(s, c))
    if ang < 0:
        ang += 360
    return ang

def _cluster_conjunctions_for_detection(pos, members, orb_deg=3.0):
    remaining = set(members)
    reps = []
    rep_map = {}
    while remaining:
        seed = min(remaining, key=lambda m: pos[m])
        cluster = [seed]
        remaining.remove(seed)
        to_check = list(remaining)
        for m in to_check:
            if angle_delta(pos[m], pos[seed]) <= orb_deg:
                cluster.append(m)
                remaining.remove(m)
        rep_id = "|".join(sorted(cluster))
        rep_map[rep_id] = cluster
        reps.append(rep_id)
    rep_pos = {rep: _mean_deg([pos[m] for m in rep_map[rep]]) for rep in reps}
    rep_anchor = {rep: rep_map[rep][0] for rep in reps}
    return rep_pos, rep_map, rep_anchor

def _status(rep_pos, a, b, aspect):
    return aspect_match(angle_delta(rep_pos[a], rep_pos[b]), aspect)[0]

def _add_shape(shapes, sh_type, parent_idx, sid, node_list, edge_specs, rep_map, rep_anchor):
    members_expanded = []
    for r in node_list:
        members_expanded.extend(rep_map[r])
    edges_expanded = [((rep_anchor[a], rep_anchor[b]), asp) for ((a, b), asp) in edge_specs]
    shape = {
        "id": f"shape{sid}",
        "type": sh_type,
        "members": members_expanded,
        "edges": edges_expanded,
        "parent": parent_idx
    }
    shapes.append(shape)
    return sid + 1

# -------------------------------
# Helpers
# -------------------------------
def angle_delta(deg1, deg2):
    diff = abs(deg1 - deg2) % 360
    return diff if diff <= 180 else 360 - diff

def aspect_match(angle, aspect_name):
    asp = ASPECTS[aspect_name]
    target, orb = asp["angle"], asp["orb"]
    delta = abs(angle - target)
    if delta <= orb:
        return "present", delta
    elif delta <= orb + 1.0:  # tolerance window
        return "near", delta
    return None, delta

def _mean_deg(degs):
    s = sum(math.sin(math.radians(d)) for d in degs)
    c = sum(math.cos(math.radians(d)) for d in degs)
    ang = math.degrees(math.atan2(s, c))
    if ang < 0:
        ang += 360
    return ang

def _cluster_conjunctions_for_detection(pos, members, orb_deg=3.0):
    remaining = set(members)
    reps = []
    rep_map = {}
    while remaining:
        seed = min(remaining, key=lambda m: pos[m])
        cluster = [seed]
        remaining.remove(seed)
        to_check = list(remaining)
        for m in to_check:
            if angle_delta(pos[m], pos[seed]) <= orb_deg:
                cluster.append(m)
                remaining.remove(m)
        rep_id = "|".join(sorted(cluster))
        rep_map[rep_id] = cluster
        reps.append(rep_id)
    rep_pos = {rep: _mean_deg([pos[m] for m in rep_map[rep]]) for rep in reps}
    rep_anchor = {rep: rep_map[rep][0] for rep in reps}
    return rep_pos, rep_map, rep_anchor

def _status(rep_pos, a, b, aspect):
    return aspect_match(angle_delta(rep_pos[a], rep_pos[b]), aspect)[0]

def _add_shape(shapes, sh_type, parent_idx, sid, node_list, edge_specs, rep_map, rep_anchor):
    members_expanded = []
    for r in node_list:
        members_expanded.extend(rep_map[r])
    edges_expanded = [((rep_anchor[a], rep_anchor[b]), asp) for ((a, b), asp) in edge_specs]
    shape = {
        "id": f"shape{sid}",
        "type": sh_type,
        "members": members_expanded,
        "edges": edges_expanded,
        "parent": parent_idx
    }
    shapes.append(shape)
    return sid + 1

# -------------------------------
# Shape detection
def _detect_shapes_for_members(pos, members, parent_idx, sid_start=0):
    if not members:
        return [], sid_start

    rep_pos, rep_map, rep_anchor = _cluster_conjunctions_for_detection(
        pos, list(members), orb_deg=3.0
    )
    R = list(rep_pos.keys())
    shapes, seen = [], set()
    sid = sid_start

    # suppression sets (expanded members only)
    suppress_t_squares = []        # Grand Cross only
    suppress_wedges = []           # Mystic Rectangle + Cradle only
    suppress_sextile_wedges = []   # Cradle + Kite only
    suppress_trines = []           # Kite only

    def add_once(sh_type, node_list, edge_specs):
        nonlocal sid
        members_expanded = []
        for r in node_list:
            members_expanded.extend(rep_map[r])
        key = (sh_type, tuple(sorted(members_expanded)))
        if key in seen:
            return False
        seen.add(key)
        sid = _add_shape(
            shapes, sh_type, parent_idx, sid,
            node_list, edge_specs, rep_map, rep_anchor
        )
        return True

    # ---------------- 4-NODE SHAPES ----------------

    # Grand Cross
    gc_count = 0
    for quad in combinations(R, 4):
        pairs = list(combinations(quad, 2))
        opp = [(a, b) for (a, b) in pairs if _status(rep_pos, a, b, "Opposition") in ("present", "near")]
        sqr = [(a, b) for (a, b) in pairs if _status(rep_pos, a, b, "Square")     in ("present", "near")]
        if len(opp) == 2 and len(sqr) == 4:
            ok = all(
                sum(node in p for p in opp) >= 1 and
                sum(node in p for p in sqr) >= 2
                for node in quad
            )
            if ok and add_once("Grand Cross", quad,
                               [((a, b), "Opposition") for (a, b) in opp] +
                               [((a, b), "Square") for (a, b) in sqr]):
                expanded = set()
                for r in quad: expanded.update(rep_map[r])
                suppress_t_squares.append(expanded)
                gc_count += 1
    print(f"[GC] parent {parent_idx}: detected {gc_count}")

    # Mystic Rectangle
    mr_count = 0
    for quad in combinations(R, 4):
        pairs = list(combinations(quad, 2))
        opp = [(a, b) for (a, b) in pairs if _status(rep_pos, a, b, "Opposition") in ("present", "near")]
        tri = [(a, b) for (a, b) in pairs if _status(rep_pos, a, b, "Trine")      in ("present", "near")]
        sex = [(a, b) for (a, b) in pairs if _status(rep_pos, a, b, "Sextile")    in ("present", "near")]
        if len(opp) == 2 and len(tri) == 2 and len(sex) == 2:
            if add_once("Mystic Rectangle", quad,
                        [((a, b), "Opposition") for (a, b) in opp] +
                        [((a, b), "Trine") for (a, b) in tri] +
                        [((a, b), "Sextile") for (a, b) in sex]):
                expanded = set()
                for r in quad: expanded.update(rep_map[r])
                suppress_wedges.append(expanded)
                mr_count += 1
    print(f"[MR] parent {parent_idx}: detected {mr_count}")

    # Cradle
    cr_count = 0
    for quad in permutations(R, 4):
        A, B, C, D = quad
        if (_status(rep_pos, A, B, "Sextile") in ("present", "near") and
            _status(rep_pos, B, C, "Sextile") in ("present", "near") and
            _status(rep_pos, C, D, "Sextile") in ("present", "near") and
            _status(rep_pos, A, D, "Opposition") in ("present", "near") and
            _status(rep_pos, A, C, "Trine")     in ("present", "near") and
            _status(rep_pos, B, D, "Trine")     in ("present", "near")):
            if add_once("Cradle", (A, B, C, D),
                        [((A, B), "Sextile"), ((B, C), "Sextile"), ((C, D), "Sextile"),
                         ((A, D), "Opposition"),
                         ((A, C), "Trine"), ((B, D), "Trine")]):
                expanded = set()
                for r in (A, B, C, D): expanded.update(rep_map[r])
                suppress_wedges.append(expanded)
                suppress_sextile_wedges.append(expanded)
                cr_count += 1
            break
    print(f"[CR] parent {parent_idx}: detected {cr_count}")

    # Kite
    kite_count = 0
    for quad in combinations(R, 4):
        for trio in combinations(quad, 3):
            A, B, C = trio
            apex = list(set(quad) - set(trio))[0]
            if (_status(rep_pos, A, B, "Trine") in ("present", "near") and
                _status(rep_pos, B, C, "Trine") in ("present", "near") and
                _status(rep_pos, A, C, "Trine") in ("present", "near")):
                for t in (A, B, C):
                    if _status(rep_pos, apex, t, "Opposition") in ("present", "near"):
                        rest = [x for x in (A, B, C) if x != t]
                        if add_once("Kite", (A, B, C, apex),
                                    [((A, B), "Trine"), ((B, C), "Trine"), ((A, C), "Trine"),
                                     ((apex, t), "Opposition"),
                                     ((apex, rest[0]), "Sextile"), ((apex, rest[1]), "Sextile")]):
                            expanded = set()
                            for r in (A, B, C, apex): expanded.update(rep_map[r])
                            suppress_trines.append(expanded)
                            suppress_sextile_wedges.append(expanded)
                            kite_count += 1
                        break
    print(f"[KITE] parent {parent_idx}: detected {kite_count}")

    # ---------------- 3-NODE SHAPES ----------------

    # T-Square
    tsq_count = 0
    opp_orb = ASPECTS["Opposition"]["orb"]
    sqr_orb = ASPECTS["Square"]["orb"]

    for trio in combinations(R, 3):
        trio_expanded = set()
        for r in trio: trio_expanded.update(rep_map[r])

        if any(trio_expanded.issubset(parent) for parent in suppress_t_squares):
            print(f"[TSQ] parent {parent_idx}: SUPPRESS {list(trio_expanded)} by Grand Cross")
            continue

        accepted = None
        for apex in trio:
            a, b = [n for n in trio if n != apex]
            ang_opp = angle_delta(rep_pos[a], rep_pos[b])
            ang_s1  = angle_delta(rep_pos[apex], rep_pos[a])
            ang_s2  = angle_delta(rep_pos[apex], rep_pos[b])
            if within_deg(ang_opp, 180.0, opp_orb, pad=1.0) and \
               within_deg(ang_s1,   90.0, sqr_orb, pad=0.0) and \
               within_deg(ang_s2,   90.0, sqr_orb, pad=0.0):
                accepted = (a, b, apex)
                break

        if accepted:
            a, b, apex = accepted
            add_once("T-Square", (a, b, apex),
                     [((a, b), "Opposition"),
                      ((apex, a), "Square"),
                      ((apex, b), "Square")])
            tsq_count += 1
    print(f"[TSQ] parent {parent_idx}: total added = {tsq_count}")

    # Wedge
    wed_count = 0
    for trio in combinations(R, 3):
        trio_expanded = set()
        for r in trio: trio_expanded.update(rep_map[r])
        if any(trio_expanded.issubset(parent) for parent in suppress_wedges):
            print(f"[WED] parent {parent_idx}: SUPPRESS {list(trio_expanded)}")
            continue
        pairs = list(combinations(trio, 2))
        opp = [(a, b) for (a, b) in pairs if _status(rep_pos, a, b, "Opposition") == "present"]
        tri = [(a, b) for (a, b) in pairs if _status(rep_pos, a, b, "Trine")      == "present"]
        sex = [(a, b) for (a, b) in pairs if _status(rep_pos, a, b, "Sextile")    == "present"]
        if len(opp) == 1 and len(tri) == 1 and len(sex) == 1:
            add_once("Wedge", trio,
                     [(opp[0], "Opposition"), (tri[0], "Trine"), (sex[0], "Sextile")])
            wed_count += 1
    print(f"[WED] parent {parent_idx}: total added = {wed_count}")

    # Sextile Wedge
    sxw_count = 0
    for trio in combinations(R, 3):
        trio_expanded = set()
        for r in trio: trio_expanded.update(rep_map[r])
        if any(trio_expanded.issubset(parent) for parent in suppress_sextile_wedges):
            print(f"[SXW] parent {parent_idx}: SUPPRESS {list(trio_expanded)} (inside Kite/Cradle)")
            continue
        pairs = list(combinations(trio, 2))
        tri = [(a, b) for (a, b) in pairs if _status(rep_pos, a, b, "Trine")   == "present"]
        sex = [(a, b) for (a, b) in pairs if _status(rep_pos, a, b, "Sextile") == "present"]
        opp = [(a, b) for (a, b) in pairs if _status(rep_pos, a, b, "Opposition") == "present"]
        if len(tri) == 1 and len(sex) == 2 and len(opp) == 0:
            add_once("Sextile Wedge", trio,
                     [(tri[0], "Trine"), (sex[0], "Sextile"), (sex[1], "Sextile")])
            sxw_count += 1
    print(f"[SXW] parent {parent_idx}: total added = {sxw_count}")

    print(f"[TALLY] parent {parent_idx}: Grand Cross={gc_count}, Mystic Rectangle={mr_count}, "
          f"Cradle={cr_count}, Kite={kite_count}, T-Square={tsq_count}, "
          f"Wedge={wed_count}, Sextile Wedge={sxw_count}")
    return shapes, sid

def detect_shapes(pos, patterns):
    results = []
    sid = 0
    for parent_idx, members in enumerate(patterns):
        mems = [m for m in members if m in pos]
        shapes_here, sid = _detect_shapes_for_members(pos, mems, parent_idx, sid)
        print(f"[SHAPES] parent {parent_idx} | members={len(mems)} -> shapes={len(shapes_here)}")
        for sh in shapes_here:
            print(f"    + {sh['type']} id={sh['id']} members={', '.join(sh['members'])}")
        results.extend(shapes_here)
    return results

def internal_minor_edges_for_pattern(pos,members):
    minors=[]
    mems=[m for m in members if m in pos]
    for i in range(len(mems)):
        for j in range(i+1,len(mems)):
            p1,p2=mems[i],mems[j]
            angle=abs(pos[p1]-pos[p2])%360
            if angle>180: angle=360-angle
            for asp in ["Quincunx","Sesquisquare"]:
                data=ASPECTS[asp]
                if abs(angle-data["angle"])<=data["orb"]:
                    minors.append(((p1,p2),asp))
                    break
    return minors

def internal_minor_edges_for_pattern(pos,members):
    minors=[]
    mems=[m for m in members if m in pos]
    for i in range(len(mems)):
        for j in range(i+1,len(mems)):
            p1,p2=mems[i],mems[j]
            angle=abs(pos[p1]-pos[p2])%360
            if angle>180: angle=360-angle
            for asp in ["Quincunx","Sesquisquare"]:
                data=ASPECTS[asp]
                if abs(angle-data["angle"])<=data["orb"]:
                    minors.append(((p1,p2),asp))
                    break
    return minors
