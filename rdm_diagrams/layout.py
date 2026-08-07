"""
layout.py
================================================================================
WHAT THIS FILE IS
--------------------------------------------------------------------------------
A handful of Graphviz layout tricks shared by all three diagrams. None of them
changes what a diagram depicts -- no box or arrow is added, removed, or
relabelled by anything in here. They only change WHERE things end up drawn.

This exists because Graphviz's `dot` engine does not read the `stages` list
(the "top to bottom" order declared in each project's CURATION) when it
decides where to place a cluster on the page -- cluster position is worked
out purely from the edges. Left alone, that produces three visible problems:

  1. Stage panels can come out in an order that does not match the `stages`
     list at all (`pin_stage_order` fixes this).
  2. A "hub" script -- one that calls many other scripts across many stages,
     e.g. model_wrapper.do -- draws one long line per script it calls, and
     those lines have to sweep across the whole page to reach stages that are
     visually far away (`bundle_hub_edges` fixes this).
  3. Even with the panels ranked in order, `dot` still chooses their
     left-right positions itself, and it likes putting the first and last
     stages at opposite horizontal extremes. That cannot be overridden
     directly -- edge weights and constraint=false guides were both tried and
     measurably did nothing (see DIAGRAM_LAYOUT_PLAN.md, Phase 2, Problem 1).
     What CAN be controlled is the vertical axis, so instead the first and
     last stages each get a horizontal band of their own, where there is no
     left-right decision left for `dot` to make (`pin_stage_order`'s
     top_group / last_stage options -- Phase 3 of the same plan).

Which stages get banded is a per-project decision, declared as a LAYOUT dict
in projects/<key>.py and read here by layout_spec(). It lives there rather
than in CURATION because it is a fact about the PICTURE's geometry, not about
what the picture depicts.
================================================================================
"""

import importlib
from contextlib import contextmanager


# ==============================================================================
# SECTION 1: PER-PROJECT LAYOUT SETTINGS
# ==============================================================================

# What applies when a project declares no LAYOUT of its own: no banding,
# exactly the Phase 1 behavior.
DEFAULT_LAYOUT = {
    "top_group": (),      # stage ids drawn as one block, alone at the top
    "last_stage": None,   # stage id drawn in a band of its own at the bottom
}


def layout_spec(project):
    """Return the project's LAYOUT dict, filled out with the defaults.

    Looked up by importing projects.<key> rather than stored on the Project
    record, because the Project dataclass (config.py) is frozen and this
    module deliberately does not touch it. A project with no LAYOUT at all
    just gets the defaults -- adding a third project does not require one.
    """
    try:
        module = importlib.import_module("projects." + project.key)
    except ImportError:
        return dict(DEFAULT_LAYOUT)
    spec = dict(DEFAULT_LAYOUT)
    spec.update(getattr(module, "LAYOUT", None) or {})
    return spec


def arrange_stages(stages, top_group=(), last_stage=None):
    """Return `stages` re-sequenced so the banded stages sit where the bands
    will be: top_group stages first (keeping their relative order), the
    last_stage stage at the end.

    This is a renderer-side re-sequencing only -- the CURATION list it came
    from is not touched. It matters because pin_stage_order() chains the
    stage anchors in list order: banding a stage that the spine chain wedges
    somewhere else would make the two constraints fight.
    """
    front = [s for s in stages if s[0] in top_group]
    back = [s for s in stages if s[0] == last_stage and s[0] not in top_group]
    middle = [s for s in stages
              if s[0] not in top_group and s[0] != last_stage]
    return front + middle + back


# ==============================================================================
# SECTION 2: PIN STAGE PANELS INTO THE DECLARED ORDER
# ==============================================================================

# The invisible parent cluster the top_group stages are nested inside. The
# name must begin with "cluster" -- that prefix is what makes Graphviz treat
# a subgraph as a drawn-together group at all.
TOP_GROUP_CLUSTER = "cluster__top_group"


@contextmanager
def stage_panel(dot, stage_id, top_group=()):
    """Open (or re-open) one stage's cluster, honoring the top group.

    Graphviz merges same-named subgraphs, so re-opening "cluster_<stage>" adds
    to the existing panel -- but a grouped stage must be re-opened THROUGH the
    parent cluster, never at the top level, or the same panel ends up declared
    in two different places and Graphviz mis-assigns which cluster owns it.
    Routing every open through this one helper is what guarantees that.
    """
    if stage_id in top_group:
        with dot.subgraph(name=TOP_GROUP_CLUSTER) as group:
            # The parent draws no border and no label of its own: its whole
            # job is "keep these panels physically together on the page".
            group.attr(style="invis")
            with group.subgraph(name="cluster_" + stage_id) as panel:
                yield panel
    else:
        with dot.subgraph(name="cluster_" + stage_id) as panel:
            yield panel


def flip_for_bands(from_stage, to_stage, top_group=(), last_stage=None):
    """True when a real edge crosses a Phase 3 band pointing UP the page --
    into the top group from below, or out of the bottom stage to above.

    Such an edge forms a cycle with pin_stage_order()'s boundary chain, and
    `dot` breaks cycles by reversing an edge of ITS choosing -- measured on
    real renders, it regularly picked one of the invisible band edges, which
    quietly unpinned that box (the R wrapper sank two thousand points down
    the comprehensive diagram, cluster and all). So the caller must not hand
    `dot` the cycle in the first place: draw the edge with its endpoints
    swapped and `dir="back"` (for a plain `arrowhead="none"` line, swapping
    alone is enough). That is the standard Graphviz back-edge idiom -- same
    line, same arrowhead, same meaning, but the layout constraint now agrees
    with the band instead of fighting it.

    A stage of None (an id this diagram doesn't draw, or a synthetic node)
    never flips.
    """
    if to_stage is None or from_stage is None:
        return False
    if to_stage in top_group and from_stage not in top_group:
        return True
    if last_stage is not None and from_stage == last_stage \
            and to_stage != last_stage:
        return True
    return False


def pin_stage_order(dot, stages, nodes, extra_ids_by_stage=None,
                    top_group=(), last_stage=None):
    """Force stage panels to rank top-to-bottom in `stages` list order.

    Adds one invisible point node inside each stage's cluster, chains those
    points together in list order, and also ties every real box in a stage to
    that stage's point. Graphviz has to keep an edge's tail at an equal or
    earlier rank than its head, so this guarantees two things at once:
    stage N's anchor sits at or before stage N+1's, AND no box in stage N can
    float to an earlier rank than stage N's anchor -- which matters for a
    stage like "standalone / legacy scripts" whose boxes have no other
    incoming edges. Left only to the real edges, boxes like that drift to
    rank 0 regardless of where their stage sits in the declared order.

    `nodes` is whatever list of {"id", "stage", ...} dicts the caller is
    about to draw (`nodes`, `kept_nodes`, or `box_nodes` depending on which
    diagram this is). `extra_ids_by_stage`, if given, is a
    {stage_id: [extra_node_id, ...]} map for ids this diagram draws that
    don't live in that list -- e.g. render_data.py's junction boxes, or the
    tap nodes bundle_hub_edges() introduces.

    `top_group` and `last_stage` (normally straight from layout_spec()) turn
    on the Phase 3 banding: the top_group stages are held in a horizontal
    band of their own at the top of the page, and the last_stage stage in a
    band of its own at the bottom. The mechanism is a "boundary chain" -- an
    invisible edge from every box on one side of the boundary to the spine
    anchor on the other side, so no box can share a horizontal band with the
    pinned stages. That removes the left-right placement decision for those
    stages entirely, which is the only reliable way to control it: `dot`
    decides horizontal order with a heuristic that provably ignores edge
    weights and constraint=false guides (measured, not guessed -- see
    DIAGRAM_LAYOUT_PLAN.md, Phase 2, Problem 1).

    A handful of real edges cross these boundaries against the flow (e.g.
    the R wrapper reading back files that later stages wrote). Each would
    form a cycle with the chain, so the caller must draw those particular
    edges pre-reversed -- see flip_for_bands() for why letting `dot` break
    the cycles itself does not work. They still render pointing upward into
    the band; the plan's Phase 3 section lists every such edge by name.

    Call this AFTER the stage-cluster loop that draws the real boxes: panels
    are re-opened by name (through stage_panel(), so grouped stages re-open
    inside their parent), which Graphviz merges into the same cluster rather
    than creating a second one. The caller must pass `stages` already run
    through arrange_stages() with the same top_group/last_stage, so the
    spine chain and the bands agree about the order.
    """
    extra_ids_by_stage = extra_ids_by_stage or {}
    ids_by_stage = {}
    for n in nodes:
        ids_by_stage.setdefault(n["stage"], []).append(n["id"])
    for stage_id, extra_ids in extra_ids_by_stage.items():
        ids_by_stage.setdefault(stage_id, []).extend(extra_ids)

    # Re-sequenced defensively even though callers already do this: a stages
    # list that disagrees with the banding would chain the anchors into a
    # contradiction (a stage pinned to the bottom with its anchor wedged
    # mid-spine), and Graphviz would resolve the resulting cycle arbitrarily.
    stages = arrange_stages(stages, top_group, last_stage)

    prev_anchor_id = None
    for stage_id, _stage_title in stages:
        anchor_id = "_spine_" + stage_id
        with stage_panel(dot, stage_id, top_group) as panel:
            # Same invisible-point trick the legend already uses elsewhere in
            # this codebase (a real node hidden by matching the background,
            # not a style="invis" node -- point nodes hidden that way still
            # take part in ranking, which is the whole point here).
            panel.node(anchor_id, "", shape="point", width="0.01", color="white")
            # weight="0" keeps these edges out of the crossing-minimization
            # tug-of-war over left-right position -- they should only ever
            # affect rank (top-to-bottom), never compete with a real edge
            # over where a box sits horizontally.
            for node_id in ids_by_stage.get(stage_id, []):
                panel.edge(anchor_id, node_id, style="invis", weight="0")

        if prev_anchor_id is not None:
            dot.edge(prev_anchor_id, anchor_id, style="invis")
        prev_anchor_id = anchor_id

    # --- The boundary chains (Phase 3 banding) -------------------------------
    stage_ids = [s for s, _ in stages]
    grouped = [s for s in stage_ids if s in top_group]
    ungrouped = [s for s in stage_ids if s not in top_group]

    # Top band: every box in the group must finish before the first stage
    # outside it begins. One edge to the first outside anchor is enough --
    # the spine chain already puts every later anchor (and, through the
    # anchor ties, every later box) below that one.
    if grouped and ungrouped:
        first_outside_anchor = "_spine_" + ungrouped[0]
        for stage_id in grouped:
            for node_id in ids_by_stage.get(stage_id, []):
                dot.edge(node_id, first_outside_anchor, style="invis")

    # Bottom band: every box NOT in the last stage must finish before the
    # last stage's anchor. Top-group boxes are skipped -- the top chain
    # already holds them above the first outside anchor, which the spine
    # holds above this one, so an edge here would say nothing new (and every
    # invisible constraint edge is one more chance to hit dot's init_rank
    # crash -- see the plan's Phase 3 wrinkles).
    if last_stage in stage_ids:
        last_anchor = "_spine_" + last_stage
        for stage_id in stage_ids:
            if stage_id == last_stage or stage_id in top_group:
                continue
            for node_id in ids_by_stage.get(stage_id, []):
                dot.edge(node_id, last_anchor, style="invis")


# ==============================================================================
# SECTION 3: BUNDLE A HUB'S FAN-OUT THROUGH ONE TAP PER TARGET STAGE
# ==============================================================================
# Same idea as render_data.py's PAIR_LIMIT / junction-box rule: past a certain
# number of wires between the same two things, replace the wires with one
# shared point and keep the detail local to it. There, it was data pairs
# through a busy script. Here, it's a hub script's calls fanning out into a
# stage full of targets.

HUB_OUT_DEGREE_THRESHOLD = 1


def bundle_hub_edges(nodes, edges, threshold=HUB_OUT_DEGREE_THRESHOLD):
    """Group a hub's outgoing `calls` edges by the target's stage.

    A "hub" is any node whose outgoing `calls` edges into a single stage
    number more than `threshold` -- this is what catches model_wrapper.do
    (and, for flukeRDM, its R wrapper too) without naming either one, so the
    same rule works for any project this toolchain is pointed at.

    Returns a dict:
      tap_nodes    -- [{"id", "stage"}] one per (hub, crowded target stage)
                       pair; the caller draws these as small invisible points
                       inside that stage's cluster, alongside the real boxes.
      spine_edges  -- [{"from", "to"}] one hub -> tap edge per crowded group.
                       Undecorated: it stands for several different toggles
                       at once, so no single toggle's label or dash pattern
                       belongs on it.
      leaf_edges   -- the original per-script edges, unchanged except their
                       "from" now points at the tap instead of the hub. All
                       styling (dashed, toggle label, colour) is preserved,
                       so the diagram still says exactly which switch enables
                       which script -- just from a shorter line.
      other_edges  -- every edge NOT touched by bundling, in original order.
                       The caller draws these exactly as before.
    """
    stage_of = {n["id"]: n["stage"] for n in nodes}

    calls_by_hub = {}
    for e in edges:
        if e["kind"] == "calls":
            calls_by_hub.setdefault(e["from"], []).append(e)

    # --- Decide which (hub, target-stage) groups are crowded enough to bundle
    bundle_map = {}   # (hub, target_stage) -> tap id
    tap_nodes = []
    for hub, hub_edges in calls_by_hub.items():
        by_stage = {}
        for e in hub_edges:
            by_stage.setdefault(stage_of.get(e["to"]), []).append(e)
        for target_stage, group in by_stage.items():
            if len(group) > threshold:
                tap_id = "_tap_%s_%s" % (hub, target_stage)
                bundle_map[(hub, target_stage)] = tap_id
                tap_nodes.append({"id": tap_id, "stage": target_stage})

    # --- Split the edges into the four buckets described above ---------------
    other_edges = []
    spine_edges = []
    leaf_edges = []
    seen_spine = set()

    for e in edges:
        key = (e["from"], stage_of.get(e["to"])) if e["kind"] == "calls" else None
        if key is not None and key in bundle_map:
            tap_id = bundle_map[key]
            if key not in seen_spine:
                spine_edges.append({"from": e["from"], "to": tap_id})
                seen_spine.add(key)
            leaf = dict(e)
            leaf["from"] = tap_id
            leaf_edges.append(leaf)
        else:
            other_edges.append(e)

    return {
        "tap_nodes": tap_nodes,
        "spine_edges": spine_edges,
        "leaf_edges": leaf_edges,
        "other_edges": other_edges,
    }
