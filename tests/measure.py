"""
measure.py
================================================================================
The shared scoring harness. Every renderer in this spike is judged by THIS file
and nothing else -- that is the only reason the three sets of numbers can be
compared at all.

The one design decision that makes it tool-agnostic:

    A stage's position is derived from the positions of its MEMBER NODES,
    never from the renderer's own cluster/subgraph markup.

Graphviz writes clusters as `<g class="cluster"><title>cluster_calib</title>`,
Mermaid writes them as `<g class="subgraph">` with a generated id, visNetwork has
no cluster concept at all. Node ids are the one thing all three preserve
verbatim, so the metric is built on those.

Two scores, per the spike plan:

  1. Reading-order score -- per stage, the centroid of its member nodes,
     normalised into a unit square. Headline questions: is `setup` in the
     top-left quadrant, is `shiny` in the bottom-right, and how well does the
     top-to-bottom (and left-to-right) ordering of the stages match the order
     they are declared in?

  2. Crossing count -- pairwise intersections of edges drawn as straight
     segments between node centroids. Deliberately crude: real renderers route
     edges as splines, so this is NOT the number of crossings a reader sees.
     It is a consistent proxy, computed identically for all three, and only its
     value RELATIVE to the baseline means anything.

Coordinates are normalised (min-max over the real nodes) before any score is
computed, so a renderer that emits points, inches or negative y coordinates
scores the same as one that emits pixels. Y is assumed to increase DOWNWARD,
which is true of SVG and of visNetwork's canvas; a caller reading a coordinate
system where y points up must flip it before calling in.
================================================================================
"""

import math


# ==============================================================================
# SECTION 1: NORMALISATION
# ==============================================================================

def normalise(positions):
    """Map {id: (x, y)} into the unit square, preserving nothing but shape.

    Each axis is scaled independently. That is intentional: the questions asked
    below are all about relative placement ("is setup left of centre?"), and
    aspect ratio differs wildly between renderers -- Graphviz's page here is
    6646x3281pt, Mermaid's is whatever its font metrics produce. A degenerate
    axis (every node at the same x) maps to 0.5 rather than dividing by zero.
    """
    if not positions:
        return {}
    xs = [p[0] for p in positions.values()]
    ys = [p[1] for p in positions.values()]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    spanx = (maxx - minx) or None
    spany = (maxy - miny) or None
    out = {}
    for node_id, (x, y) in positions.items():
        nx = 0.5 if spanx is None else (x - minx) / spanx
        ny = 0.5 if spany is None else (y - miny) / spany
        out[node_id] = (nx, ny)
    return out


# ==============================================================================
# SECTION 2: SCORE 1 -- READING ORDER
# ==============================================================================

def stage_centroids(norm_positions, nodes):
    """{stage_id: (cx, cy, n_members)} from member node positions only.

    Nodes with no measured position (a renderer dropped them, or they are
    synthetic ids this spike never drew) are skipped, and the member count is
    reported so a silently-thinned stage is visible in the output rather than
    quietly shifting a centroid.
    """
    acc = {}
    for n in nodes:
        pos = norm_positions.get(n["id"])
        if pos is None:
            continue
        sx, sy, count = acc.get(n["stage"], (0.0, 0.0, 0))
        acc[n["stage"]] = (sx + pos[0], sy + pos[1], count + 1)
    return {stage: (sx / c, sy / c, c) for stage, (sx, sy, c) in acc.items() if c}


def _ranks(values):
    """Competition-free ordinal ranks (0 = smallest). Ties broken by input order,
    which is fine here: an exact centroid tie between two stages is vanishingly
    unlikely and would not change the correlation materially."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0] * len(values)
    for rank, i in enumerate(order):
        ranks[i] = rank
    return ranks


def spearman(a, b):
    """Spearman rank correlation of two equal-length sequences.

    Hand-rolled because the spike must not add a scipy dependency to a machine
    where the plan already pinned which packages exist. Uses the Pearson
    correlation of the ranks (not the tie-free d^2 shortcut), so ties degrade
    gracefully.
    """
    if len(a) < 2:
        return float("nan")
    ra, rb = _ranks(a), _ranks(b)
    n = len(ra)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((ra[i] - ma) * (rb[i] - mb) for i in range(n))
    da = math.sqrt(sum((r - ma) ** 2 for r in ra))
    db = math.sqrt(sum((r - mb) ** 2 for r in rb))
    if da == 0 or db == 0:
        return float("nan")
    return num / (da * db)


def reading_order(norm_positions, nodes, stages, top_group=(), last_stage=None):
    """The full reading-order report for one rendered graph.

    `stages` must already be in the order the renderer was ASKED to draw them
    (i.e. run through arrange_stages with the same banding spec) -- the
    correlations below measure "did the engine honour the order it was given",
    so comparing against a different order would answer a different question.

    Returned dict:
      stages            per-stage centroid + declared index + measured ranks
      corr_y / corr_x   rank correlation, declared order vs top-to-bottom /
                        left-to-right position. 1.0 is perfect.
      setup_top_left    the corner question for the first stage
      shiny_bottom_right the corner question for the last stage
    """
    cents = stage_centroids(norm_positions, nodes)
    ordered = [s for s, _t in stages if s in cents]
    cxs = [cents[s][0] for s in ordered]
    cys = [cents[s][1] for s in ordered]
    rank_y = _ranks(cys)
    rank_x = _ranks(cxs)
    declared = list(range(len(ordered)))

    rows = []
    for i, stage_id in enumerate(ordered):
        cx, cy, count = cents[stage_id]
        rows.append({
            "stage": stage_id,
            "declared_index": i,
            "cx": round(cx, 3),
            "cy": round(cy, 3),
            "rank_by_cy": rank_y[i],
            "rank_by_cx": rank_x[i],
            "n_nodes": count,
        })

    def corner(stage_id, want_left, want_top):
        if stage_id not in cents:
            return None
        cx, cy, _ = cents[stage_id]
        return ((cx < 0.5) == want_left) and ((cy < 0.5) == want_top)

    first_stage = (top_group[0] if top_group else (ordered[0] if ordered else None))
    return {
        "stages": rows,
        "corr_y": spearman(declared, cys),
        "corr_x": spearman(declared, cxs),
        "setup_top_left": corner(first_stage, want_left=True, want_top=True),
        "top_group_top_left": [
            {"stage": s, "top_left": corner(s, True, True)} for s in top_group
        ],
        "shiny_bottom_right": corner(last_stage, want_left=False, want_top=False),
    }


# ==============================================================================
# SECTION 3: SCORE 2 -- EDGE CROSSINGS
# ==============================================================================

def _orient(a, b, c):
    """Sign of the cross product (b-a) x (c-a): which side of line ab is c on."""
    v = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    if v > 1e-12:
        return 1
    if v < -1e-12:
        return -1
    return 0


def _crosses(p1, p2, p3, p4):
    """Proper (non-degenerate) intersection of segments p1p2 and p3p4.

    Collinear overlaps and shared-endpoint touches are NOT counted. Two edges
    that meet at a node are not a crossing a reader would notice, and this
    graph has plenty of them (82 nodes, 131 edges) -- counting them would swamp
    the signal the score exists to carry.
    """
    d1, d2 = _orient(p3, p4, p1), _orient(p3, p4, p2)
    d3, d4 = _orient(p1, p2, p3), _orient(p1, p2, p4)
    return d1 * d2 < 0 and d3 * d4 < 0


def count_crossings(norm_positions, edges):
    """Straight-line crossing count over every drawable edge pair.

    Returns (crossings, n_drawable_edges). Edges whose endpoints have no
    measured position are dropped from both numbers, so the count is always
    reported alongside how many edges it was computed over.
    """
    segs = []
    for e in edges:
        a = norm_positions.get(e["from"])
        b = norm_positions.get(e["to"])
        if a is None or b is None or a == b:
            continue
        segs.append((e["from"], e["to"], a, b))

    crossings = 0
    for i in range(len(segs)):
        fi, ti, ai, bi = segs[i]
        for j in range(i + 1, len(segs)):
            fj, tj, aj, bj = segs[j]
            if {fi, ti} & {fj, tj}:
                continue          # share a node: not a crossing
            if _crosses(ai, bi, aj, bj):
                crossings += 1
    return crossings, len(segs)


# ==============================================================================
# SECTION 4: ONE CALL THAT SCORES A RENDERER
# ==============================================================================

def score(label, positions, nodes, edges, stages, top_group=(), last_stage=None,
          notes=None):
    """Score one rendered graph. `positions` is {node_id: (x, y)}, y downward."""
    norm = normalise(positions)
    crossings, drawn_edges = count_crossings(norm, edges)
    found = sum(1 for n in nodes if n["id"] in positions)
    return {
        "label": label,
        "nodes_expected": len(nodes),
        "nodes_located": found,
        "edges_expected": len(edges),
        "edges_scored": drawn_edges,
        "crossings": crossings,
        "reading_order": reading_order(norm, nodes, stages, top_group, last_stage),
        "notes": notes or "",
    }


def format_report(result):
    """Human-readable block for one score() result."""
    ro = result["reading_order"]
    lines = []
    lines.append("=" * 78)
    lines.append(result["label"])
    lines.append("=" * 78)
    lines.append("nodes located %d/%d    edges scored %d/%d    crossings %d"
                 % (result["nodes_located"], result["nodes_expected"],
                    result["edges_scored"], result["edges_expected"],
                    result["crossings"]))
    lines.append("")
    lines.append("  stage         declared   cx     cy    rank_y  rank_x   n")
    lines.append("  " + "-" * 60)
    for r in ro["stages"]:
        lines.append("  %-12s %5d   %6.3f %6.3f %6d %7d %4d"
                     % (r["stage"], r["declared_index"], r["cx"], r["cy"],
                        r["rank_by_cy"], r["rank_by_cx"], r["n_nodes"]))
    lines.append("")
    lines.append("  declared-order vs top-to-bottom (corr_y): %+.3f" % ro["corr_y"])
    lines.append("  declared-order vs left-to-right (corr_x): %+.3f" % ro["corr_x"])
    for item in ro["top_group_top_left"]:
        lines.append("  %-8s in TOP-LEFT quadrant:      %s"
                     % (item["stage"], item["top_left"]))
    lines.append("  shiny    in BOTTOM-RIGHT quadrant:  %s" % ro["shiny_bottom_right"])
    if result["notes"]:
        lines.append("")
        lines.append("  note: " + result["notes"])
    return "\n".join(lines)
