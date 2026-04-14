import matplotlib.pyplot as plt
import pandas as pd
import pytest

from src.rendering.dispositor_graph import order_siblings, compute_house_map, plot_dispositor_graph
from src.core.models_v2 import AstrologicalChart, ChartObject, static_db


def make_chart(objects):
    """Helper: create an AstrologicalChart from list of dict rows."""
    df = pd.DataFrame(objects)
    chart = AstrologicalChart.from_dataframe(
        df,
        chart_datetime="2025-01-01 00:00:00",
        timezone="UTC",
        latitude=0.0,
        longitude=0.0,
        static=static_db,
    )
    return chart


def test_order_siblings_by_house():
    # create a simple weights dict
    weights = {"A": 1, "B": 1, "C": 1, "D": 1, "E": 1, "F": 1}
    names = list(weights.keys())
    # pretend these are in houses: A,B,C in 6; D,E in 7; F in 11
    house_map = {"A": 6, "B": 6, "C": 6, "D": 7, "E": 7, "F": 11}
    ordered = order_siblings(names, weights, house_map=house_map)
    # should group by house ascending and keep subordering stable
    assert ordered[:3] == ["A", "B", "C"]
    assert ordered[3:5] == ["D", "E"]
    assert ordered[5:] == ["F"]


def test_plot_dispositor_graph_includes_house_rectangles(tmp_path):
    # build a chart with Mars and children; each row must include house info
    objects = [
        {"Object": "Mars", "Glyph": "", "Longitude": 0.0,
         "Sign": "Aries", "Placidus House": 12, "Equal House": 12, "Whole Sign House": 12},
        {"Object": "Pluto", "Glyph": "", "Longitude": 1.0,
         "Sign": "Aries", "Placidus House": 6, "Equal House": 6, "Whole Sign House": 6},
        {"Object": "Juno", "Glyph": "", "Longitude": 2.0,
         "Sign": "Aries", "Placidus House": 6, "Equal House": 6, "Whole Sign House": 6},
        {"Object": "Moon", "Glyph": "", "Longitude": 3.0,
         "Sign": "Aries", "Placidus House": 6, "Equal House": 6, "Whole Sign House": 6},
        {"Object": "Lilith", "Glyph": "", "Longitude": 4.0,
         "Sign": "Aries", "Placidus House": 7, "Equal House": 7, "Whole Sign House": 7},
        {"Object": "DC", "Glyph": "", "Longitude": 5.0,
         "Sign": "Aries", "Placidus House": 7, "Equal House": 7, "Whole Sign House": 7},
        {"Object": "Eris", "Glyph": "", "Longitude": 6.0,
         "Sign": "Aries", "Placidus House": 11, "Equal House": 11, "Whole Sign House": 11},
    ]
    chart = make_chart(objects)

    # monkeypatch simple plot_data for a single parent-child chain
    plot_data = {
        "raw_links": [("Mars", "Pluto"), ("Mars", "Juno"), ("Mars", "Moon"),
                      ("Mars", "Lilith"), ("Mars", "DC"), ("Mars", "Eris")],
        "sovereigns": [],
        "self_ruling": [],
    }
    # call function; scope doesn't matter since graph code only uses raw_links etc.
    fig = plot_dispositor_graph(plot_data, chart, header_info=None, house_system="placidus")
    assert fig is not None
    # save for manual inspection if needed (uses pytest tmp_path)
    fig.savefig(tmp_path / "dispositor_debug.png")
    texts = [t.get_text() for ax in fig.axes for t in ax.texts]
    # verify house labels appear
    assert "6H" in texts
    assert "7H" in texts
    assert "11H" in texts
    assert "12H" in texts
    # also ensure the Mars label is present
    assert "Mars" in texts

    plt.close(fig)


def test_spacing_and_width_behavior():
    # create two datasets of different complexity.  We use a "star"
    # configuration (one parent with many children) since that forces
    # horizontal expansion; a simple chain would remain vertical and therefore
    # always produce the minimum figure width.
    def make_star(num_children):
        return [("P", f"C{i}") for i in range(num_children)]

    small = {"raw_links": make_star(3), "sovereigns": [], "self_ruling": []}
    large = {"raw_links": make_star(15), "sovereigns": [], "self_ruling": []}

    fig_small = plot_dispositor_graph(small, chart=None)
    fig_large = plot_dispositor_graph(large, chart=None)

    w_small = fig_small.get_size_inches()[0]
    w_large = fig_large.get_size_inches()[0]
    assert w_large > w_small, "Fig width should increase for larger graph"

    # verify marker size scales up (so that they don't appear tiny when the
    # figure is later shrunk by the UI).  We check the maximum size found in
    # each figure's scatter collections.
    sizes_small = []
    for coll in fig_small.axes[0].collections:
        sizes_small.extend(coll.get_sizes())
    sizes_large = []
    for coll in fig_large.axes[0].collections:
        sizes_large.extend(coll.get_sizes())
    assert max(sizes_large) >= max(sizes_small)
    # also confirm that at least one planet label text grew
    text_fonts_small = [t.get_fontsize() for t in fig_small.axes[0].texts]
    text_fonts_large = [t.get_fontsize() for t in fig_large.axes[0].texts]
    assert max(text_fonts_large) >= max(text_fonts_small)

    # ensure horizontal spacing between *siblings* does not collapse
    # below H_GAP (we only compare points that share nearly identical
    # vertical positions because parent/child overlaps are expected).
    ax = fig_large.axes[0]
    pts = []
    for coll in ax.collections:
        off = coll.get_offsets()
        for x, y in off:
            pts.append((x, y))
    # group by y (within a small tolerance)
    groups = {}
    for x, y in pts:
        found = False
        for gy in list(groups):
            if abs(gy - y) < 1e-6:
                groups[gy].append(x)
                found = True
                break
        if not found:
            groups[y] = [x]
    for xs in groups.values():
        if len(xs) < 2:
            continue
        xs.sort()
        min_dx = min(b - a for a, b in zip(xs, xs[1:]))
        assert min_dx >= 1.2 * 0.9

    plt.close(fig_small)
    plt.close(fig_large)


def test_multi_tree_spacing_behavior():
    # build a large, tightly packed star to force scaling and a small one
    big_star = [("A", f"a{i}") for i in range(20)]
    small_star = [("B", f"b{i}") for i in range(3)]
    combined = {"raw_links": big_star + small_star, "sovereigns": [], "self_ruling": []}

    fig_big = plot_dispositor_graph({"raw_links": big_star, "sovereigns": [], "self_ruling": []}, chart=None)
    fig_small = plot_dispositor_graph({"raw_links": small_star, "sovereigns": [], "self_ruling": []}, chart=None)
    fig_comb = plot_dispositor_graph(combined, chart=None)

    # since we now draw all trees on a single axis, inspect text positions
    ax_comb = fig_comb.axes[0]
    texts = ax_comb.texts
    # collect x coordinates for small-tree labels and big-tree labels
    small_xs = [t.get_position()[0] for t in texts if t.get_text().startswith("B") or t.get_text().startswith("b")]
    big_xs = [t.get_position()[0] for t in texts if t.get_text().startswith("A") or t.get_text().startswith("a")]
    assert small_xs and big_xs, "expected labels from both trees"
    span_small = max(small_xs) - min(small_xs)

    # compare to the span when the small tree was rendered alone
    ax_small = fig_small.axes[0]
    texts_small = ax_small.texts
    span_small_alone = max(t.get_position()[0] for t in texts_small if t.get_text().startswith("B") or t.get_text().startswith("b")) - min(t.get_position()[0] for t in texts_small if t.get_text().startswith("B") or t.get_text().startswith("b"))
    assert span_small >= span_small_alone * 0.9, "small tree lost too much horizontal space when combined"

    plt.close(fig_big)
    plt.close(fig_small)
    plt.close(fig_comb)


def test_house_rectangles_dont_span_units():
    # simulate dual rulership: planet X appears under parents A and B,
    # both in the same house.  We also insert a sibling Y under A in the
    # same house to ensure a naive grouping would create a single large
    # rectangle covering X and Y and the copy of X.
    big_links = [("A", "X"), ("A", "Y"), ("B", "X")]
    plot_data = {"raw_links": big_links, "sovereigns": [], "self_ruling": []}

    fig = plot_dispositor_graph(plot_data, chart=None)
    ax = fig.axes[0]
    # count rectangles drawn (patches) that correspond to the house level of
    # our nodes.  There should be at least two patches: one for A's children
    # and another for B's child, not one big spanning rectangle.
    house_patches = []
    for p in ax.patches:
        # width > 0 indicates a house rectangle (we draw none else)
        if p.get_width() > 0 and isinstance(p, type(ax.patches[0])):
            house_patches.append(p)
    assert len(house_patches) >= 2, "Expected separate rectangles for each family unit"
    plt.close(fig)
