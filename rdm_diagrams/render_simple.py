"""
render_simple.py
================================================================================
WHAT THIS FILE IS
--------------------------------------------------------------------------------
This is the "presentation" version of the data flow diagram.

Three diagrams are drawn for each project, into output/<project>/:

  <Prefix>comprehensive_pipeline_diagram.png
        the DETAILED one -- every script AND every data file. Great for
        actually tracing where a number came from. Too big to read on a slide.

  <Prefix>simple_pipeline_diagram.png
        THIS one -- scripts only, no data files. Fits on a single page or
        slide. Great for showing someone the shape of the pipeline in a
        meeting.

  <Prefix>data_pipeline_diagram.png
        the data's-eye view -- boxes are files, arrows are labelled with the
        script doing the work.

You do not run this file directly. Run the wrapper for the project you want:

    python make_fluke_diagrams.py
    python make_groundfish_diagrams.py

See SETUP_INSTRUCTIONS.md if this is your first time running Python.

--------------------------------------------------------------------------------
WHY IT WORKS THIS WAY
--------------------------------------------------------------------------------
This file does NOT keep its own copy of the pipeline. The same 'stages',
'nodes' and 'edges' lists that the comprehensive diagram draws are handed to it
as arguments, and they came from extract.py reading the project's source code.

That matters: there is one description of the pipeline, derived from the code
itself, and all three diagrams read it. There is no second list to keep in
sync, the pictures can never disagree with each other, and none of them can
drift from the code without the extractor reporting it.

(This module used to get those lists by importing the comprehensive diagram's
script, which meant drawing the simple diagram silently redrew the big one as
a side effect. Passing them in as arguments removed that.)

--------------------------------------------------------------------------------
HOW THE SIMPLIFICATION WORKS
--------------------------------------------------------------------------------
The detailed diagram is crowded mostly because of data files -- about 40 of the
boxes are files on disk rather than steps that run. But we cannot just delete
them, because they carry meaning: if script A writes a file and script B reads
that same file, then B depends on A. Deleting the file box would silently delete
that dependency and the picture would be wrong.

So instead of deleting, we "bridge" -- we replace this:

    [cpt1] ---writes---> (baseline_mrip.xlsx) ---read by---> [copula]

with this:

    [cpt1] ------------------------------------------------> [copula]

Same information about what depends on what, one less box. Do that for every
data file and the diagram shrinks to something you can read on a slide, without
telling any lies about the pipeline.
================================================================================
"""

from graphviz import Digraph

from . import mermaid
from . import palette
from .config import DEFAULT_ENGINE
from .graphviz_path import ensure_on_path
from .layout import (arrange_stages, bundle_hub_edges, flip_for_bands,
                     layout_spec, pin_stage_order, stage_panel)
from .legend import legend_swatch, legend_line


# The name this diagram's files get, after the project's prefix. Declared
# here so that archiving and the comparison page can find the files this
# module writes without a second copy of the name to keep in step.
DIAGRAM_FILE = "simple_pipeline_diagram"


# ==============================================================================
# SECTION 1: HOW EACH KIND OF BOX AND ARROW SHOULD LOOK
# ==============================================================================
# Same colour scheme as the detailed diagram, so someone who has seen one can
# read the other without relearning anything.

# We keep everything that DOES something (Stata scripts, R scripts, the Shiny
# app) plus the handful of outside systems (Google Drive, the Oracle database,
# the Azure queue) -- those are worth keeping because they show where data
# enters and leaves the whole operation. We drop only type "data": the files.
KEEP_TYPES = {"stata", "r", "shiny", "external"}

NODE_STYLE = {
    "stata":    dict(palette.NODE_COLORS["stata"],    shape="box", style="rounded,filled",
                     fontcolor="#12263a"),
    "r":        dict(palette.NODE_COLORS["r"],        shape="box", style="rounded,filled",
                     fontcolor="#14331c"),
    "shiny":    dict(palette.NODE_COLORS["shiny"],    shape="box", style="rounded,filled,bold",
                     fontcolor="#2a133f"),
    "external": dict(palette.NODE_COLORS["external"], shape="octagon", style="filled,dashed",
                     fontcolor="#4a3a00"),
}

EDGE_STYLE = {
    # A script running another script: the backbone of the picture, so it is
    # the boldest thing on the page.
    "calls":    {"color": palette.EDGE_COLORS["calls"], "penwidth": "2.0", "arrowsize": "0.8"},
    # A dependency that exists because one wrote a file the other read.
    "dataflow": {"color": palette.EDGE_COLORS["reads"], "penwidth": "1.0", "arrowsize": "0.6"},
    # Connected by a shared folder or a queue, NOT by a line of code. Task 1
    # flagged these as unconfirmed, so they look deliberately different.
    "inferred": {"color": palette.EDGE_COLORS["inferred"], "penwidth": "1.0", "style": "dotted",
                 "arrowsize": "0.6"},
}


# ==============================================================================
# SECTION 2: DECIDE WHICH BOXES TO KEEP, AND BRIDGE ACROSS THE REST
# ==============================================================================

def simplify(nodes, edges):
    """Fold the data files away, keeping every dependency they carried.

    Returns (kept_nodes, simple_edges). For each data file we drop, everything
    that wrote it is joined directly to everything that read it, so "B depends
    on A" survives the box disappearing.
    """
    kept_nodes = [n for n in nodes if n["type"] in KEEP_TYPES]
    kept_ids = {n["id"] for n in kept_nodes}

    # The ids of the boxes we are removing, i.e. the data files to bridge.
    data_ids = {n["id"] for n in nodes if n["type"] == "data"}

    simple_edges = []       # the arrows we will actually draw
    seen = set()            # remembers (from, to) pairs so we never duplicate

    def add_edge(src, dst, kind, toggle=None, default_off=False):
        """Record one arrow, ignoring self-loops and duplicates.

        Self-loops happen legitimately: a script that reads the draw files and
        writes them back out again would, after bridging, point at itself. An
        arrow from a box to itself tells the reader nothing, so we skip it.

        Duplicates happen a lot: two scripts often share several data files,
        which would bridge into the same arrow over and over. We keep the first
        one only, so a shared dependency shows as one clean arrow instead of
        five stacked on top of each other.
        """
        if src == dst:
            return
        if src not in kept_ids or dst not in kept_ids:
            return
        if (src, dst) in seen:
            return
        seen.add((src, dst))
        simple_edges.append({
            "from": src, "to": dst, "kind": kind,
            "toggle": toggle, "default_off": default_off,
        })

    # --- Step A: keep the arrows that already join two boxes we're keeping ---
    # These are the "calls" arrows (one script running another) and the few
    # direct links to outside systems. "calls" arrows are added first, before
    # any bridged arrows, because a real call is more informative than an
    # inferred dependency and we only keep one arrow per pair.
    for e in edges:
        if e["kind"] == "calls":
            add_edge(e["from"], e["to"], "calls",
                     e.get("toggle"), e.get("default_off", False))

    for e in edges:
        if e["kind"] != "calls" and e["from"] not in data_ids and e["to"] not in data_ids:
            # A plain "reads"/"writes" straight between two kept boxes (for
            # example the Oracle database feeding get_mrip_oracle.R) means the
            # same thing here as a bridged arrow does: one depends on the
            # other. So it gets the same look. "inferred" keeps its own look.
            kind = e["kind"] if e["kind"] == "inferred" else "dataflow"
            add_edge(e["from"], e["to"], kind)

    # --- Step B: bridge across each data file --------------------------------
    for d in data_ids:
        writers = [e for e in edges if e["to"] == d]      # things that produced it
        readers = [e for e in edges if e["from"] == d]    # things that consumed it
        for w in writers:
            for r in readers:
                # If either half of the journey was only an assumption, the
                # whole bridged arrow is only an assumption -- so it stays
                # marked inferred and gets drawn as a red dotted line.
                kind = "inferred" if "inferred" in (w["kind"], r["kind"]) else "dataflow"
                add_edge(w["from"], r["to"], kind)

    return kept_nodes, simple_edges


# ==============================================================================
# SECTION 3: BUILD THE DIAGRAM
# ==============================================================================

def build_graph(project, stages, kept_nodes, simple_edges):
    """Return the finished Graphviz drawing, ready to render."""
    dot = Digraph("%s_simple" % project.key, format="png")

    dot.attr(
        rankdir="TB",          # top to bottom: raw data at the top, outputs at the bottom
        labelloc="t",
        label=("%s Pipeline - Simplified View (scripts only)\\n"
               "Data files omitted; an arrow between two scripts means the second "
               "depends on the first.\\n" % project.display_name),
        fontname="Helvetica-Bold",
        fontsize="20",
        # "size" is what makes this fit a page: Graphviz lays the graph out at
        # its natural size, then scales the whole thing down to fit inside this
        # many inches -- roughly a 16:9 slide. Scaling down keeps the
        # proportions, so nothing gets squashed or stretched.
        size="17,9.5",
        # How many pixels per inch the PNG is rendered at. The default (96)
        # would give a picture only ~1600 pixels wide, which looks soft and
        # blurry on a projector or a big monitor. 200 gives ~3400 pixels for
        # the same physical size -- crisp when projected, and still a
        # comfortably small file. (PNG only; the SVG is sharp at any size.)
        dpi="200",
        nodesep="0.22",        # horizontal gap between boxes -- kept tight
        # Vertical gap between rows. Deliberately generous relative to nodesep:
        # this graph naturally wants to sprawl sideways, and a very wide, short
        # picture wastes the top and bottom of a 16:9 slide (everything shrinks
        # to fit the width). Spending space vertically instead pushes the shape
        # closer to the slide's proportions, so the text ends up bigger.
        ranksep="0.85",
        splines="spline",
        # NOTE: Graphviz has a "concentrate" option that merges parallel arrows.
        # It is deliberately NOT used here -- it crashes when the diagram also
        # uses labelled panels like ours ("rebuild_vlists: lead is null"). We
        # get the same tidiness from the duplicate-removal in Section 2 instead.
        bgcolor="white",
        # One global rank grid across all the panels (same setting the
        # comprehensive diagram always had). Without it, each panel keeps its
        # own local grid, which is allowed to drift some tens of points from
        # its neighbours' -- enough to let one panel's lowest box dip visibly
        # below the top of the Phase 3 bottom band it is pinned above.
        newrank="true",
    )

    dot.attr("node", fontname="Helvetica", fontsize="11", margin="0.14,0.08")
    dot.attr("edge", fontname="Helvetica", fontsize="8")

    # The project's banding choices (which stages are held alone at the top
    # and bottom of the page), and the stage order re-sequenced to match --
    # see layout.py and DIAGRAM_LAYOUT_PLAN.md Phase 3.
    layout = layout_spec(project)
    stages = arrange_stages(stages, layout["top_group"], layout["last_stage"])

    # A hub script (model_wrapper.do, and for flukeRDM its R wrapper too)
    # calls scripts scattered across every stage. One line per call has to
    # sweep across the whole page to reach a stage that's visually far away.
    # bundle_hub_edges() collapses each hub's fan-out into one shared entry
    # point per crowded target stage -- see layout.py.
    bundle = bundle_hub_edges(kept_nodes, simple_edges)
    taps_by_stage = {}
    for tap in bundle["tap_nodes"]:
        taps_by_stage.setdefault(tap["stage"], []).append(tap)

    # --- Draw the boxes, grouped into one panel per pipeline stage -----------
    # Grouping is what stops this from becoming a random scatter of 40 boxes:
    # each panel is a phase of the pipeline, and the panels read top to bottom
    # in the order the phases actually run.

    for stage_id, stage_label in stages:
        stage_nodes = [n for n in kept_nodes if n["stage"] == stage_id]
        stage_taps = taps_by_stage.get(stage_id, [])
        if not stage_nodes and not stage_taps:
            continue

        # A Graphviz cluster is just "draw a labelled box around this group".
        with stage_panel(dot, stage_id, layout["top_group"]) as sub:
            sub.attr(label=stage_label, fontname="Helvetica-Bold", fontsize="13",
                     color="#9aa5b1", style="rounded", bgcolor="#fafbfc",
                     margin="12")

            for n in stage_nodes:
                style = dict(NODE_STYLE[n["type"]])

                # Scripts the developers themselves marked "dead code" are
                # faded so the eye skips them -- they are in the repo but
                # switched off.
                if n.get("dead"):
                    style.update(palette.DEAD_CODE_OVERRIDE)
                    style["style"] = "rounded,filled,dashed"

                sub.node(n["id"], n["label"], **style)

            # The shared entry point(s) a hub's bundled calls land on, so the
            # long part of the journey ends inside the panel it's heading for.
            for tap in stage_taps:
                sub.node(tap["id"], "", shape="point", width="0.01", color="white")

    # Pin the panels into the order the project declared -- without this,
    # Graphviz places them purely by what the edges imply, which does not
    # reliably come out top-to-bottom in `stages` order.
    tap_ids_by_stage = {stage_id: [t["id"] for t in taps]
                         for stage_id, taps in taps_by_stage.items()}
    pin_stage_order(dot, stages, kept_nodes, extra_ids_by_stage=tap_ids_by_stage,
                    top_group=layout["top_group"],
                    last_stage=layout["last_stage"])

    # --- Draw the arrows -----------------------------------------------------

    # Which stage each drawable id lives in, taps included -- needed to spot
    # the few edges that cross a Phase 3 band pointing up the page. Bridging
    # can create such edges that don't exist in the raw edge list (a script
    # whose output the R wrapper reads back becomes a direct arrow into the
    # wrapper), so this check has to run here, on the bridged edges.
    stage_of = {n["id"]: n["stage"] for n in kept_nodes}
    stage_of.update((t["id"], t["stage"]) for t in bundle["tap_nodes"])

    def draw_styled_edge(e):
        style = dict(EDGE_STYLE[e["kind"]])

        # An arrow controlled by an on/off switch is drawn dashed, so "always
        # runs" and "runs only if switched on" are obvious at a glance.
        #
        # Deliberately NOT labelled with the switch's name here. Printing 20
        # macro names along the arrows is what made the first attempt at this
        # diagram too wide to read on a slide -- the labels forced the boxes
        # apart and shrank all the text. On a slide the useful fact is "this
        # step is optional"; if you need to know WHICH switch, the detailed
        # diagram spells every one out.
        if e.get("toggle"):
            style["style"] = "dashed"
            # Switches that ship set to 0 are greyed out -- they don't run as-is.
            if e.get("default_off"):
                style["color"] = "#b0b0b0"

        # An edge that points upward across a Phase 3 band is drawn
        # pre-reversed so it cannot form a cycle with the band constraints --
        # same line, same arrowhead, see layout.flip_for_bands().
        if flip_for_bands(stage_of.get(e["from"]), stage_of.get(e["to"]),
                          layout["top_group"], layout["last_stage"]):
            style["dir"] = "back"
            dot.edge(e["to"], e["from"], **style)
        else:
            dot.edge(e["from"], e["to"], **style)

    for e in bundle["other_edges"]:
        draw_styled_edge(e)

    # The bundled portion of a hub's fan-out: one plain "calls"-coloured line
    # per crowded target stage, undecorated (it stands for several different
    # toggles at once), then the original per-script arrow running the short
    # distance from the tap to the actual target.
    for e in bundle["spine_edges"]:
        style = dict(EDGE_STYLE["calls"])
        if flip_for_bands(stage_of.get(e["from"]), stage_of.get(e["to"]),
                          layout["top_group"], layout["last_stage"]):
            style["dir"] = "back"
            dot.edge(e["to"], e["from"], **style)
        else:
            dot.edge(e["from"], e["to"], **style)
    for e in bundle["leaf_edges"]:
        draw_styled_edge(e)

    # --- The legend ----------------------------------------------------------
    # Without this, the colours are just decoration; with it, the picture
    # explains itself to someone seeing it cold on a slide.
    #
    # The legend is built as ONE box containing a small table, rather than as a
    # dozen separate little boxes. The reason is layout: separate boxes get
    # spaced out using the same generous row spacing as the rest of the
    # diagram, which stretched the legend into a tall, gappy column taller than
    # the diagram itself. A table is laid out internally, so it stays compact
    # no matter what the rest of the graph is doing.
    #
    # The odd-looking <TABLE>/<TR>/<TD> text below is Graphviz's built-in
    # support for simple HTML-style tables in a label. The "<" and ">" wrapping
    # the whole thing is what tells Graphviz to read it as a table instead of
    # plain text.

    legend_html = (
        '<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="4" CELLPADDING="2">'
        '<TR><TD COLSPAN="2"><B>LEGEND</B></TD></TR>'
        + legend_swatch(palette.NODE_COLORS["stata"]["fillcolor"],
                        palette.NODE_COLORS["stata"]["color"], "Stata .do script")
        + legend_swatch(palette.NODE_COLORS["r"]["fillcolor"],
                        palette.NODE_COLORS["r"]["color"], "R script")
        + legend_swatch(palette.NODE_COLORS["shiny"]["fillcolor"],
                        palette.NODE_COLORS["shiny"]["color"], "Shiny app (endpoint)")
        + legend_swatch(palette.NODE_COLORS["external"]["fillcolor"],
                        palette.NODE_COLORS["external"]["color"],
                        "Outside the code<BR ALIGN=\"LEFT\"/>"
                        "(Drive, Oracle, queue)")
        + legend_swatch(palette.DEAD_CODE_OVERRIDE["fillcolor"],
                        palette.DEAD_CODE_OVERRIDE["color"], "Dead code (switched off)")
        + '<TR><TD COLSPAN="2"></TD></TR>'
        + legend_line(palette.EDGE_COLORS["calls"], "&#8212;&#8212;&gt;", "runs that script")
        + legend_line(palette.EDGE_COLORS["reads"], "&#8212;&#8212;&gt;", "depends on its output")
        + legend_line(palette.EDGE_COLORS["inferred"], "&#183;&#183;&#183;&#183;&gt;",
                      "shared folder / queue,<BR ALIGN=\"LEFT\"/>NOT a code call")
        + legend_line(palette.EDGE_COLORS["calls"], "&#8211; &#8211; &gt;",
                      "optional - controlled by a<BR ALIGN=\"LEFT\"/>"
                      "switch in model_wrapper.do")
        + '</TABLE>>'
    )

    dot.node("legend_box", legend_html, shape="box", style="rounded",
             color="#9aa5b1", fillcolor="white", fontname="Helvetica",
             fontsize="11", margin="0.1,0.06")

    return dot


# ==============================================================================
# SECTION 4: BUILD THE SAME DIAGRAM IN MERMAID
# ==============================================================================
# Section 2's simplify() is shared -- which boxes to keep and how to bridge
# across the rest is a question about the pipeline, not about the drawing
# program. Only the drawing differs.
#
# ONE THING THIS ENGINE CANNOT DO: the Graphviz version sets size="17,9.5" and
# dpi="200", which lays the graph out at its natural size and then scales the
# whole picture down to fit a 16:9 slide. Mermaid has no equivalent -- it draws
# at natural size, and mmdc's --scale only multiplies pixels, it does not fit
# to a shape. So under this engine the "fits on a slide" property is lost: the
# PNG is a large image that a slide will letterbox. Everything else about the
# simplification (folding the data files away, dropping the toggle names)
# still applies, so it remains the small readable diagram -- just not
# pre-sized. See MERMAID_MIGRATION_PLAN.md.

MERMAID_SHAPES = {
    "stata": "round", "r": "round", "shiny": "subroutine", "external": "hexagon",
}

MERMAID_EDGE_WIDTH = {"calls": 2.0, "dataflow": 1.0, "inferred": 1.0}


def build_mermaid(project, stages, kept_nodes, simple_edges):
    """Return the Mermaid source for the simplified diagram."""
    chart = mermaid.Flowchart(
        title="%s Pipeline - Simplified View (scripts only)   |   data files "
              "omitted; an arrow between two scripts means the second depends "
              "on the first" % project.display_name)

    layout = layout_spec(project)
    stages = arrange_stages(stages, layout["top_group"], layout["last_stage"])

    bundle = bundle_hub_edges(kept_nodes, simple_edges)
    taps_by_stage = {}
    for tap in bundle["tap_nodes"]:
        taps_by_stage.setdefault(tap["stage"], []).append(tap)

    for stage_id, stage_label in stages:
        stage_nodes = [n for n in kept_nodes if n["stage"] == stage_id]
        stage_taps = taps_by_stage.get(stage_id, [])
        if not stage_nodes and not stage_taps:
            continue
        with chart.panel(stage_id, stage_label, fill="#fafbfc"):
            for n in stage_nodes:
                colors = palette.NODE_COLORS[n["type"]]
                fill, stroke = colors["fillcolor"], colors["color"]
                text_color = None
                if n.get("dead"):
                    fill = palette.DEAD_CODE_OVERRIDE["fillcolor"]
                    stroke = palette.DEAD_CODE_OVERRIDE["color"]
                    text_color = palette.DEAD_CODE_OVERRIDE["fontcolor"]
                chart.node(n["id"], n["label"],
                           shape=MERMAID_SHAPES[n["type"]],
                           fill=fill, stroke=stroke, text_color=text_color,
                           dashed=bool(n.get("dead")))
            for tap in stage_taps:
                chart.point(tap["id"])

    def draw_styled_edge(e):
        """Same rule as the Graphviz path: an optional step is dashed, and
        deliberately NOT labelled with the switch's name -- 20 macro names
        along the arrows is what made the first version of this diagram too
        wide to read on a slide."""
        color = palette.EDGE_COLORS["calls"] if e["kind"] == "calls" else (
            palette.EDGE_COLORS["inferred"] if e["kind"] == "inferred"
            else palette.EDGE_COLORS["reads"])
        dashed = False
        if e.get("toggle"):
            dashed = True
            if e.get("default_off"):
                color = "#b0b0b0"     # ships switched off: greyed out
        chart.edge(e["from"], e["to"], color=color,
                   width=MERMAID_EDGE_WIDTH[e["kind"]],
                   dotted=(e["kind"] == "inferred"), dashed=dashed)

    for e in bundle["other_edges"]:
        draw_styled_edge(e)
    for e in bundle["spine_edges"]:
        chart.edge(e["from"], e["to"], color=palette.EDGE_COLORS["calls"],
                   width=MERMAID_EDGE_WIDTH["calls"])
    for e in bundle["leaf_edges"]:
        draw_styled_edge(e)

    # The legend, as boxes. The Graphviz version packs this into one HTML
    # table precisely so the diagram's generous row spacing cannot stretch it
    # into a tall gappy column; Mermaid has no table label, so the entries are
    # separate boxes inside their own panel and that protection is gone.
    samples = [
        ("lg_stata", "Stata .do script", palette.NODE_COLORS["stata"], "round"),
        ("lg_r", "R script", palette.NODE_COLORS["r"], "round"),
        ("lg_shiny", "Shiny app (endpoint)", palette.NODE_COLORS["shiny"], "subroutine"),
        ("lg_ext", "Outside the code\n(Drive, Oracle, queue)",
         palette.NODE_COLORS["external"], "hexagon"),
        ("lg_dead", "Dead code (switched off)",
         {"fillcolor": palette.DEAD_CODE_OVERRIDE["fillcolor"],
          "color": palette.DEAD_CODE_OVERRIDE["color"]}, "round"),
    ]
    arrows = [
        ("runs that script", palette.EDGE_COLORS["calls"], 2.0, False, False),
        ("depends on its output", palette.EDGE_COLORS["reads"], 1.0, False, False),
        ("shared folder / queue,\nNOT a code call",
         palette.EDGE_COLORS["inferred"], 1.0, True, False),
        ("optional - controlled by a switch\nin the wrapper",
         palette.EDGE_COLORS["calls"], 1.0, False, True),
    ]
    with chart.panel("legend", "LEGEND", fill="#ffffff"):
        for node_id, label, colors, shape in samples:
            chart.node(node_id, label, shape=shape,
                       fill=colors["fillcolor"], stroke=colors["color"])
        for i, _ in enumerate(arrows):
            chart.point("lg_a%d" % i)
            chart.point("lg_b%d" % i)
    for i, (label, color, width, dotted, dashed) in enumerate(arrows):
        chart.edge("lg_a%d" % i, "lg_b%d" % i, label=label, color=color,
                   width=width, dotted=dotted, dashed=dashed)

    return chart.text()


# ==============================================================================
# SECTION 5: WRITE THE PICTURE FILES
# ==============================================================================

def render(project, stages, nodes, edges, engine=DEFAULT_ENGINE):
    """Draw the simplified diagram and write the .png and .svg."""
    kept_nodes, simple_edges = simplify(nodes, edges)
    base = project.output_base(DIAGRAM_FILE)

    if engine == "mermaid":
        png_path, svg_path = mermaid.render_text(
            build_mermaid(project, stages, kept_nodes, simple_edges), base,
            description="simplified diagram")
    else:
        ensure_on_path()
        dot = build_graph(project, stages, kept_nodes, simple_edges)
        png_path = dot.render(filename=base, format="png", cleanup=True)
        svg_path = dot.render(filename=base, format="svg", cleanup=True)

    # Count what we removed, so you can see at a glance how much simpler this
    # version is than the detailed one.
    dropped = len(nodes) - len(kept_nodes)

    print("")
    print("Success! The simplified diagram was generated.")
    print("")
    print("  PNG (for slides): " + png_path)
    print("  SVG (for printing): " + svg_path)
    print("")
    print("  " + str(len(kept_nodes)) + " boxes and " + str(len(simple_edges)) + " arrows drawn.")
    print("  (" + str(dropped) + " data-file boxes were folded away to fit one page.)")

    return png_path, svg_path
