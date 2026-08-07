"""
render_dataflow.py
================================================================================
WHAT THIS FILE IS
--------------------------------------------------------------------------------
This module draws the COMPREHENSIVE picture (a "data flow diagram") of a
project's pipeline: which script runs when, which data files each script reads
and writes, and which steps are optional because they sit behind an on/off
switch.

You do NOT run this file directly, and you do NOT need to understand Python to
use it. Run the wrapper for the project you want:

    python make_fluke_diagrams.py
    python make_groundfish_diagrams.py

Each writes two picture files into output/<project>/:
    <Prefix>comprehensive_pipeline_diagram.png   (an image -- double-click to view)
    <Prefix>comprehensive_pipeline_diagram.svg   (a vector version -- open in a web
                            browser, zooms in forever without going blurry,
                            good for printing)

See SETUP_INSTRUCTIONS.md if this is your first time running Python.

--------------------------------------------------------------------------------
WHY IT WORKS THIS WAY
--------------------------------------------------------------------------------
A diagram drawn by hand goes stale the moment someone edits the pipeline. So
instead of a drawing, we keep a *list* of the pipeline's pieces and let the
computer do the drawing. That list is not maintained by hand either: it is read
straight out of the source code by extract.py, every time you run a wrapper.

When the pipeline changes, you change nothing here. Re-run the wrapper. The
picture regenerates in a second and cannot disagree with the code it describes.

--------------------------------------------------------------------------------
WHERE THE INFORMATION CAME FROM
--------------------------------------------------------------------------------
Everything is read from the SOURCE CODE. No markdown analysis document is
involved at any point.

extract.py walks the project's repository, reading only .do and .R files, and
produces the three lists this module draws. It gets:

  * Execution order, wrapper structure and the on/off toggles by parsing
    Code/pre_sim/model_wrapper.do directly.
  * The data files each script reads and writes from two independent places --
    the "Inputs:" and "Outputs:" header blocks at the top of each script, AND
    the actual read/write statements in the code (use, save, import delimited,
    read_fst, write_csv and so on). Having both is what lets the extractor
    report drift when a header and its code disagree.

So the way to change this picture is to change the code or its headers, then
re-run the wrapper. Do not edit the node and edge lists by hand --
output/<project>/pipeline_data_generated.py is overwritten on every run.

(Historical note: an earlier version of this script carried hand-typed lists
transcribed from a DATAFLOW_*.md analysis document. That is no longer how it
works. A snapshot of that approach, generate_dataflow_diagram_from_DATAFLOW.py,
used to live in groundfish_diagrams/ for --check to compare against; both have
since been deleted.)

--------------------------------------------------------------------------------
TWO DRAWING ENGINES
--------------------------------------------------------------------------------
This module can draw the same picture with either engine:

    build_mermaid()   Mermaid + ELK -- the default
    build_graph()     Graphviz -- the original, still available

They read the same three lists and produce the same content. What differs is
layout: ELK draws this graph with about a third fewer line crossings (414 ->
281 on groundfish; measured, not asserted -- tests/check_layout.py). That is
why it is the default. Graphviz is still one flag away:
`--engine=graphviz` on the wrapper script.

The Mermaid path deliberately does NOT reproduce the Phase 3 band machinery
(pin_stage_order / flip_for_bands): those work by drawing edges pre-reversed,
which Mermaid has no way to express without also reversing the arrowhead. See
the note above build_mermaid().
================================================================================
"""

# graphviz is the Python package that talks to the Graphviz drawing program.
# If this line errors, you have not installed it yet -- see SETUP_INSTRUCTIONS.md.
from graphviz import Digraph

from . import mermaid
from . import palette
from .config import DEFAULT_ENGINE
from .graphviz_path import ensure_on_path
from .layout import (arrange_stages, bundle_hub_edges, flip_for_bands,
                     layout_spec, pin_stage_order, stage_panel)


# The name this diagram's files get, after the project's prefix. Declared
# here so that archiving and the comparison page can find the files this
# module writes without a second copy of the name to keep in step.
DIAGRAM_FILE = "comprehensive_pipeline_diagram"


# ==============================================================================
# SECTION 1: HOW EACH KIND OF BOX AND ARROW SHOULD LOOK
# ==============================================================================
# Keeping the styling in one place means changing a colour is a one-line edit,
# and every box of that type changes together.

NODE_STYLES = {
    "stata":    dict(palette.NODE_COLORS["stata"],    shape="box",      style="filled,rounded"),
    "r":        dict(palette.NODE_COLORS["r"],        shape="box",      style="filled,rounded"),
    "shiny":    dict(palette.NODE_COLORS["shiny"],    shape="box3d",    style="filled"),
    "data":     dict(palette.NODE_COLORS["data"],     shape="cylinder", style="filled"),
    "external": dict(palette.NODE_COLORS["external"], shape="octagon",  style="filled,dashed"),
}

EDGE_STYLES = {
    # Orange = "this script runs that script". These are the pipeline's spine.
    "calls":    {"color": palette.EDGE_COLORS["calls"], "penwidth": "2.0"},
    # Grey = data moving on and off disk.
    "reads":    {"color": palette.EDGE_COLORS["reads"]},
    "writes":   {"color": palette.EDGE_COLORS["writes"]},
    # Red dotted = a connection that exists in practice but not in the code.
    "inferred": {"color": palette.EDGE_COLORS["inferred"], "style": "dotted", "penwidth": "1.5"},
}


# ==============================================================================
# SECTION 2: BUILD THE DIAGRAM
# ==============================================================================

def build_graph(project, stages, nodes, edges):
    """Return the finished Graphviz drawing, ready to render.

    The pipeline description arrives as arguments rather than being imported.
    That is what lets one copy of this code draw any project -- and it is why
    importing this module no longer draws anything as a side effect.
    """
    # Create the drawing. rankdir="TB" means the flow runs Top -> Bottom.
    dot = Digraph(
        name="%s data flow" % project.display_name,
        comment="Generated by render_dataflow.py - do not edit by hand",
        format="png",
    )
    dot.attr(
        rankdir="TB",          # top-to-bottom pipeline order
        splines="spline",      # curved arrows -- easier to follow when they cross
        nodesep="0.35",        # horizontal gap between boxes
        ranksep="0.75",        # vertical gap between rows
        fontname="Helvetica",
        labelloc="t",          # put the overall title at the top
        label=(
            "%s - Data Flow and Execution Order\\l"
            "Generated by render_dataflow.py from the %s source code: "
            "model_wrapper.do for execution order, plus the Inputs/Outputs headers "
            "and the read/write statements in each .do and .R file\\l"
            % (project.display_name, project.repo_name)
        ),
        fontsize="20",
        compound="true",
        newrank="true",        # lets ranking work sensibly across the panels
    )
    dot.attr("node", fontname="Helvetica", fontsize="10", margin="0.12,0.07")
    dot.attr("edge", fontname="Helvetica", fontsize="9")

    # The project's banding choices (which stages are held alone at the top
    # and bottom of the page), and the stage order re-sequenced to match --
    # see layout.py and DIAGRAM_LAYOUT_PLAN.md Phase 3.
    layout = layout_spec(project)
    stages = arrange_stages(stages, layout["top_group"], layout["last_stage"])

    # A hub script (model_wrapper.do, and for flukeRDM its R wrapper too)
    # calls dozens of scripts scattered across every stage. Drawn as one line
    # per call, those arrows have to sweep across the whole page to reach
    # stages that are visually far away, which is the single most disruptive
    # thing in this diagram. bundle_hub_edges() collapses each hub's fan-out
    # into one shared entry point per crowded target stage -- see layout.py.
    bundle = bundle_hub_edges(nodes, edges)
    taps_by_stage = {}
    for tap in bundle["tap_nodes"]:
        taps_by_stage.setdefault(tap["stage"], []).append(tap)

    # --- Draw the boxes, one panel (stage) at a time -------------------------
    # A "subgraph" whose name starts with "cluster" is how Graphviz draws a
    # labelled box around a group of nodes.
    for stage_id, stage_title in stages:
        with stage_panel(dot, stage_id, layout["top_group"]) as panel:
            panel.attr(
                label=stage_title,
                fontsize="14",
                fontname="Helvetica-Bold",
                style="rounded",
                color="#9aa5b1",
                bgcolor="#fbfbfd",
            )
            for node in nodes:
                if node["stage"] != stage_id:
                    continue
                style = dict(NODE_STYLES[node["type"]])
                # "Dead code" scripts are drawn faded with a dashed outline, so
                # the reader can tell at a glance that they do not normally run.
                if node.get("dead"):
                    style["style"] = style["style"] + ",dashed"
                    style.update(palette.DEAD_CODE_OVERRIDE)
                    node_label = node["label"] + "\n[dead code - toggle OFF]"
                else:
                    node_label = node["label"]
                panel.node(node["id"], node_label, **style)

            # The shared entry point(s) a hub's bundled calls land on, so the
            # long part of the journey ends inside the panel it's heading for
            # instead of stopping short at the panel's edge.
            for tap in taps_by_stage.get(stage_id, []):
                panel.node(tap["id"], "", shape="point", width="0.01", color="white")

    # Pin the panels into the order the project declared -- without this,
    # Graphviz places them purely by what the edges imply, which does not
    # reliably come out top-to-bottom in `stages` order.
    tap_ids_by_stage = {stage_id: [t["id"] for t in taps]
                         for stage_id, taps in taps_by_stage.items()}
    pin_stage_order(dot, stages, nodes, extra_ids_by_stage=tap_ids_by_stage,
                    top_group=layout["top_group"],
                    last_stage=layout["last_stage"])

    # --- Draw the arrows -----------------------------------------------------

    # Which stage each drawable id lives in, taps included -- needed to spot
    # the few edges that cross a Phase 3 band pointing up the page.
    stage_of = {n["id"]: n["stage"] for n in nodes}
    stage_of.update((t["id"], t["stage"]) for t in bundle["tap_nodes"])

    def draw_styled_edge(edge):
        """Draw one edge with the toggle/note styling every real edge gets."""
        style = dict(EDGE_STYLES[edge["kind"]])

        # A step controlled by an on/off switch gets a dashed, labelled arrow,
        # so "always runs" is visually distinct from "runs only if the toggle
        # is on".
        if "toggle" in edge:
            style["style"] = "dashed"
            default_note = " = 0 by default" if edge.get("default_off") else " = 1 by default"
            style["label"] = "if " + edge["toggle"] + default_note
            style["fontcolor"] = "#a0522d"
        elif "note" in edge:
            style["label"] = edge["note"]
            style["fontcolor"] = "#c0392b"

        # An edge that points upward across a Phase 3 band is drawn
        # pre-reversed so it cannot form a cycle with the band constraints --
        # same line, same arrowhead, see layout.flip_for_bands().
        if flip_for_bands(stage_of.get(edge["from"]), stage_of.get(edge["to"]),
                          layout["top_group"], layout["last_stage"]):
            style["dir"] = "back"
            dot.edge(edge["to"], edge["from"], **style)
        else:
            dot.edge(edge["from"], edge["to"], **style)

    for edge in bundle["other_edges"]:
        draw_styled_edge(edge)

    # The bundled portion of a hub's fan-out: one plain "calls"-coloured line
    # per crowded target stage (undecorated, since it stands for several
    # different toggles at once -- no single toggle's label belongs on it),
    # then the original per-script arrow, toggle label and all, running the
    # short distance from the tap to the actual target.
    for edge in bundle["spine_edges"]:
        style = dict(EDGE_STYLES["calls"])
        if flip_for_bands(stage_of.get(edge["from"]), stage_of.get(edge["to"]),
                          layout["top_group"], layout["last_stage"]):
            style["dir"] = "back"
            dot.edge(edge["to"], edge["from"], **style)
        else:
            dot.edge(edge["from"], edge["to"], **style)
    for edge in bundle["leaf_edges"]:
        draw_styled_edge(edge)

    # --- Draw the legend -----------------------------------------------------
    # The legend is just another cluster containing example boxes. The
    # invisible arrows stack them vertically instead of spreading them across
    # the page.
    with dot.subgraph(name="cluster_legend") as legend:
        legend.attr(label="LEGEND", fontsize="14", fontname="Helvetica-Bold",
                    style="rounded", color="#333333", bgcolor="#ffffff")
        legend.node("lg_stata", "Stata .do script",   **NODE_STYLES["stata"])
        legend.node("lg_r",     "R script",           **NODE_STYLES["r"])
        legend.node("lg_shiny", "Shiny app (endpoint)", **NODE_STYLES["shiny"])
        legend.node("lg_data",  "Data file on disk",  **NODE_STYLES["data"])
        legend.node("lg_ext",   "Outside the repo\n(Drive, Oracle, queue)", **NODE_STYLES["external"])
        # Stack the legend entries with invisible connecting arrows.
        legend.edge("lg_stata", "lg_r",     style="invis")
        legend.edge("lg_r",     "lg_shiny", style="invis")
        legend.edge("lg_shiny", "lg_data",  style="invis")
        legend.edge("lg_data",  "lg_ext",   style="invis")

        # Example arrows, so the arrow colours mean something to a first-time
        # reader.
        legend.node("lg_a1", "", shape="point", width="0.01", color="white")
        legend.node("lg_a2", "", shape="point", width="0.01", color="white")
        legend.node("lg_b1", "", shape="point", width="0.01", color="white")
        legend.node("lg_b2", "", shape="point", width="0.01", color="white")
        legend.node("lg_c1", "", shape="point", width="0.01", color="white")
        legend.node("lg_c2", "", shape="point", width="0.01", color="white")
        legend.node("lg_d1", "", shape="point", width="0.01", color="white")
        legend.node("lg_d2", "", shape="point", width="0.01", color="white")
        legend.edge("lg_a1", "lg_a2", label=" runs this script", **EDGE_STYLES["calls"])
        legend.edge("lg_b1", "lg_b2", label=" reads / writes data", **EDGE_STYLES["reads"])
        legend.edge("lg_c1", "lg_c2", label=" runs only if toggle is ON",
                    style="dashed", color="#e07b39", fontcolor="#a0522d")
        legend.edge("lg_d1", "lg_d2", label=" connected by a shared folder,\\l not by code (unconfirmed)\\l",
                    **EDGE_STYLES["inferred"])
        legend.edge("lg_ext", "lg_a1", style="invis")
        legend.edge("lg_a2", "lg_b1", style="invis")
        legend.edge("lg_b2", "lg_c1", style="invis")
        legend.edge("lg_c2", "lg_d1", style="invis")

    return dot


# ==============================================================================
# SECTION 3: BUILD THE SAME DIAGRAM IN MERMAID
# ==============================================================================
# The same content as build_graph() above, expressed for the other engine.
#
# WHAT IS THE SAME: every box, every arrow, the stage panels, hub bundling
# (layout.bundle_hub_edges() is shared -- it is engine-independent), the
# toggle labels, the dead-code styling and the legend's content.
#
# WHAT IS NOT, AND WHY:
#
#   * No pin_stage_order() and no flip_for_bands(). Both work by adding
#     invisible ordering edges and then drawing the handful of edges that
#     point back up the page PRE-REVERSED, using Graphviz's dir="back" to
#     keep the arrowhead correct. Mermaid has no dir="back" -- `A <-- B` is
#     not valid Mermaid -- so a reversed edge there would also have a
#     reversed arrowhead, i.e. the diagram would state the wrong direction
#     for 7 of the 131 arrows. Until that is solved, this path uses ELK's
#     defaults, which get the stage order roughly (not exactly) right: see
#     "Decision A" in MERMAID_MIGRATION_PLAN.md.
#
#   * The multi-line caption becomes a note inside the legend panel, because
#     Mermaid's title is a single line.

# Mermaid shape per node type, chosen to read as close to the Graphviz shapes
# above as Mermaid's vocabulary allows (it has no cylinder or octagon).
MERMAID_SHAPES = {
    "stata":    "round",
    "r":        "round",
    "shiny":    "subroutine",
    "data":     "cylinder",
    "external": "hexagon",
}

# Line weight per arrow kind, mirroring the penwidths in EDGE_STYLES.
MERMAID_EDGE_WIDTH = {"calls": 2.0, "reads": 1.0, "writes": 1.0, "inferred": 1.5}


def build_mermaid(project, stages, nodes, edges):
    """Return the Mermaid source for the comprehensive diagram."""
    # The Graphviz version puts a two-line caption on the page; Mermaid's title
    # is one line, so both lines are joined into it. They are NOT put in a node
    # on the canvas: a caption-sized box is a big obstacle for the layout engine
    # to route around, and measuring it showed exactly that -- one note node in
    # the legend cost 54 extra line crossings and pushed `setup` out of the
    # left-hand side of the page (335 vs 281 crossings, corr_x -0.286 vs +0.381).
    chart = mermaid.Flowchart(
        title="%s - Data Flow and Execution Order   |   generated from the %s "
              "source code: model_wrapper.do for execution order, plus each "
              "script's Inputs/Outputs headers and its read/write statements"
              % (project.display_name, project.repo_name))

    layout = layout_spec(project)
    stages = arrange_stages(stages, layout["top_group"], layout["last_stage"])

    # Shared with the Graphviz path: one shared entry point per crowded
    # (hub, target stage) pair, so a wrapper's fan-out does not cross the page
    # once per called script. This is the single biggest readability win on
    # this diagram under either engine.
    bundle = bundle_hub_edges(nodes, edges)
    taps_by_stage = {}
    for tap in bundle["tap_nodes"]:
        taps_by_stage.setdefault(tap["stage"], []).append(tap)

    for stage_id, stage_title in stages:
        with chart.panel(stage_id, stage_title):
            for node in nodes:
                if node["stage"] != stage_id:
                    continue
                colors = palette.NODE_COLORS[node["type"]]
                label = node["label"]
                fill, stroke = colors["fillcolor"], colors["color"]
                text_color = None
                if node.get("dead"):
                    fill = palette.DEAD_CODE_OVERRIDE["fillcolor"]
                    stroke = palette.DEAD_CODE_OVERRIDE["color"]
                    text_color = palette.DEAD_CODE_OVERRIDE["fontcolor"]
                    label = label + "\n[dead code - toggle OFF]"
                chart.node(node["id"], label,
                           shape=MERMAID_SHAPES[node["type"]],
                           fill=fill, stroke=stroke, text_color=text_color,
                           dashed=bool(node.get("dead")))
            for tap in taps_by_stage.get(stage_id, []):
                chart.point(tap["id"])

    def draw_styled_edge(edge):
        """One arrow, with the toggle styling every real edge gets.

        Same rule as the Graphviz path: a step behind an on/off switch is
        dashed and labelled with the switch and its default, so "always runs"
        and "runs only if switched on" are distinguishable at a glance.
        """
        kind = edge["kind"]
        label = None
        dashed = False
        if "toggle" in edge:
            dashed = True
            default_note = (" = 0 by default" if edge.get("default_off")
                            else " = 1 by default")
            label = "if " + edge["toggle"] + default_note
        chart.edge(edge["from"], edge["to"], label=label,
                   color=palette.EDGE_COLORS[kind],
                   width=MERMAID_EDGE_WIDTH[kind],
                   dotted=(kind == "inferred"), dashed=dashed)

    for edge in bundle["other_edges"]:
        draw_styled_edge(edge)
    # The bundled fan-out: one undecorated line per crowded target stage (it
    # stands for several toggles at once, so no single toggle's label belongs
    # on it), then the original per-script arrows from the tap.
    for edge in bundle["spine_edges"]:
        chart.edge(edge["from"], edge["to"],
                   color=palette.EDGE_COLORS["calls"],
                   width=MERMAID_EDGE_WIDTH["calls"])
    for edge in bundle["leaf_edges"]:
        draw_styled_edge(edge)

    _mermaid_legend(chart, project)
    return chart.text()


def _mermaid_legend(chart, project):
    """The legend, as a panel of real boxes.

    Graphviz can draw a legend as an HTML table inside a single node; Mermaid
    has no annotation layer and no table label, so a legend can only be more
    boxes and arrows. That has a cost the table version does not: the legend
    is a disconnected part of the graph, and the layout engine puts it
    wherever it likes -- often in the top-left, displacing the first stage.
    Measured at about 24% more line crossings
    (diagram_spikes/results/RESULTS.md, Q2).
    """
    samples = [
        ("lg_stata", "Stata .do script", "stata"),
        ("lg_r", "R script", "r"),
        ("lg_shiny", "Shiny app (endpoint)", "shiny"),
        ("lg_data", "Data file on disk", "data"),
        ("lg_ext", "Outside the repo\n(Drive, Oracle, queue)", "external"),
    ]
    arrows = [
        ("runs this script", palette.EDGE_COLORS["calls"], 2.0, False, False),
        ("reads / writes data", palette.EDGE_COLORS["reads"], 1.0, False, False),
        ("runs only if toggle is ON", palette.EDGE_COLORS["calls"], 1.0, False, True),
        ("connected by a shared folder,\nnot by code (unconfirmed)",
         palette.EDGE_COLORS["inferred"], 1.5, True, False),
    ]

    with chart.panel("legend", "LEGEND"):
        for node_id, label, node_type in samples:
            colors = palette.NODE_COLORS[node_type]
            chart.node(node_id, label, shape=MERMAID_SHAPES[node_type],
                       fill=colors["fillcolor"], stroke=colors["color"])
        for i, _ in enumerate(arrows):
            chart.point("lg_a%d" % i)
            chart.point("lg_b%d" % i)

    for i, (label, color, width, dotted, dashed) in enumerate(arrows):
        chart.edge("lg_a%d" % i, "lg_b%d" % i, label=label, color=color,
                   width=width, dotted=dotted, dashed=dashed)


# ==============================================================================
# SECTION 4: WRITE THE PICTURE FILES
# ==============================================================================
# We render twice: once as PNG (an ordinary image anyone can open) and once as
# SVG (a vector image that stays sharp no matter how far you zoom in -- useful
# for reading the small text or printing a wall-sized copy).

def render(project, stages, nodes, edges, engine=DEFAULT_ENGINE):
    """Draw the comprehensive diagram and write the .png and .svg."""
    base = project.output_base(DIAGRAM_FILE)

    if engine == "mermaid":
        png_path, svg_path = mermaid.render_text(
            build_mermaid(project, stages, nodes, edges), base,
            description="comprehensive diagram")
    else:
        ensure_on_path()
        dot = build_graph(project, stages, nodes, edges)
        # cleanup=True deletes the intermediate .gv text file Graphviz uses
        # internally, so you are left with just the two pictures.
        png_path = dot.render(filename=base, format="png", cleanup=True)
        svg_path = dot.render(filename=base, format="svg", cleanup=True)

    print("")
    print("Success! The comprehensive diagram was generated.")
    print("")
    print("  PNG (double-click to view): " + png_path)
    print("  SVG (open in a web browser): " + svg_path)
    print("")
    print("  " + str(len(nodes)) + " boxes and " + str(len(edges)) + " arrows drawn.")

    return png_path, svg_path
