"""
render_data.py
================================================================================
WHAT THIS FILE IS
--------------------------------------------------------------------------------
This is the DATA-FOCUSED view of a project's pipeline. It answers the question
"where does this data file come from, and what gets made out of it?"

Three diagrams are drawn for each project, each answering a different question.
They are all built from the same underlying description of the pipeline, so
they can never disagree with each other:

  <Prefix>comprehensive_pipeline_diagram.png
        EVERYTHING -- every script and every data file. Use it to trace exactly
        where a number came from. Too big to read on a slide.

  <Prefix>simple_pipeline_diagram.png
        THE SCRIPTS -- data files folded away, so you see which script depends
        on which. Fits on one page. Good for a meeting.

  <Prefix>data_pipeline_diagram.png
        THIS ONE -- THE DATA. Scripts are folded away instead, so the boxes are
        the data files and the arrows are labelled with whichever script does
        the work. Good for answering "what feeds into this file?"

You do not run this file directly. Run the wrapper for the project you want:

    python make_fluke_diagrams.py
    python make_groundfish_diagrams.py

See SETUP_INSTRUCTIONS.md if this is your first time running Python.

--------------------------------------------------------------------------------
HOW THIS ONE IS BUILT
--------------------------------------------------------------------------------
It is the mirror image of the simplified diagram. That one kept the scripts and
folded away the data files; this one keeps the data files and folds away the
scripts, turning each script into a LABEL ON AN ARROW instead of a box.

So this, in the detailed diagram:

    (gulf_atl_2022.dta) --read by--> [survey_trip_costs.do] --writes--> (trip_costs.dta)

becomes this:

    (gulf_atl_2022.dta) ----survey_trip_costs.do----> (trip_costs.dta)

Same information, told from the data's point of view.

--------------------------------------------------------------------------------
TWO DECISIONS BAKED IN, AND WHY
--------------------------------------------------------------------------------
1. ALL TOGGLES ARE ASSUMED ON. The other two diagrams draw optional steps as
   dashed arrows, because in reality a switch in model_wrapper.do decides
   whether they run. Here every step is drawn as if switched on, so what you
   see is the complete set of data relationships that CAN exist. Nothing is
   dashed, and no switch names appear.

2. DEAD CODE IS LEFT OUT ENTIRELY -- excluded, not just faded. A dead script
   typically writes the very same files as the live script that replaced it.
   Including it would draw a second arrow into those files from a script that
   never actually runs, which in a data-focused diagram reads as "this data has
   two sources". It doesn't. (Which scripts are dead is a per-project fact and
   lives in that project's CURATION list, not here.)
================================================================================
"""

from graphviz import Digraph

from . import mermaid
from . import palette
from .config import DEFAULT_ENGINE
from .graphviz_path import ensure_on_path
from .layout import (arrange_stages, flip_for_bands, layout_spec,
                     pin_stage_order, stage_panel)
from .legend import legend_swatch, legend_line


# The name this diagram's files get, after the project's prefix. Declared
# here so that archiving and the comparison page can find the files this
# module writes without a second copy of the name to keep in step.
DIAGRAM_FILE = "data_pipeline_diagram"


# ==============================================================================
# SECTION 1: WHICH THINGS BECOME BOXES, AND HOW THEY LOOK
# ==============================================================================
# In this diagram, data files become boxes and scripts become arrow labels.
# The "external" things (Google Drive, the Oracle database, the Azure queue)
# are treated as boxes too -- in a data-focused view they matter, because they
# are where data physically enters and leaves the whole operation.

BOX_TYPES = {"data", "external"}          # these become boxes
SCRIPT_TYPES = {"stata", "r", "shiny"}    # these become arrow labels

# Same colours as the other two diagrams, so someone who has seen one can read
# this one without relearning anything: data is grey, outside systems are
# yellow, Stata is blue, R is green.

DATA_STYLE = dict(palette.NODE_COLORS["data"], shape="cylinder", style="filled",
                  fontcolor="#2b2b2b")
EXTERNAL_STYLE = dict(palette.NODE_COLORS["external"], shape="octagon", style="filled,dashed",
                      fontcolor="#4a3a00")

# Arrows are coloured by which LANGUAGE does the work, so you can see at a
# glance where the pipeline hands off between Stata and R.
SCRIPT_COLOR = {"stata": palette.NODE_COLORS["stata"]["color"],
                "r": palette.NODE_COLORS["r"]["color"],
                "shiny": palette.NODE_COLORS["shiny"]["color"]}

INFERRED_COLOR = palette.EDGE_COLORS["inferred"]

PAIR_LIMIT = 3   # at or below this many input/output pairs, draw direct arrows

# How much to thicken a direct arrow for each extra distinct script that
# shares its exact (from, to) box pair (see DIAGRAM_LAYOUT_PLAN.md Phase 2,
# Problem 2) -- e.g. mrip_lists -> mrip_processed in fluke, where 2 different
# scripts legitimately write the same output from the same input. One script
# sharing a pair draws at the normal width; each additional script adds this
# much more, instead of drawing a second full-strength line on top of the
# first.
PAIR_SHARE_PENWIDTH_STEP = 0.5


# ==============================================================================
# SECTION 2: TURN EACH SCRIPT INTO ARROWS (THE "HYBRID" RULE)
# ==============================================================================
# A script with one input and one output is easy: draw one arrow between the
# two files and write the script's name on it.
#
# The trouble is the big scripts. compare_calibration_data_to_MRIP.do reads 5
# files and writes 4. Connecting every input to every output means 5 x 4 = 20
# arrows, all carrying the same label, in one dense fan -- unreadable, and it
# overstates things by implying each input feeds each output separately.
#
# So we use a HYBRID rule:
#
#   * Simple script (3 or fewer input/output pairs) -> direct labelled arrows.
#     This is the common case and gives exactly the clean picture you'd draw
#     by hand.
#
#   * Busy script (more than 3 pairs) -> a small labelled JUNCTION dot. Every
#     input flows into the dot and every output flows out of it. That turns
#     20 arrows into 9, and reads honestly: "these files go in, that script
#     runs, these files come out."

def fold_scripts(nodes, edges):
    """Work out the data-only picture.

    Returns a dictionary holding the boxes to draw, the directly-labelled
    arrows, the scripts that need a junction box instead, and the lookups the
    drawing step needs (a script's label, type and stage, by id).
    """
    # A script collapsed upstream in extract.py (e.g. fluke's 9 near-identical
    # recDST/model_run_<ST>.R scripts drawn as one "model_run" box) can appear
    # multiple times in `nodes` under the same id. Dedup by id here, once,
    # before anything below derives ins/outs/junctions from it -- otherwise
    # each duplicate independently re-derives the same edges and junction box,
    # and build_graph() draws them once per duplicate instead of once per real
    # relationship (see DIAGRAM_LAYOUT_PLAN.md Phase 2, Problem 2).
    seen_ids = set()
    deduped_nodes = []
    for n in nodes:
        if n["id"] in seen_ids:
            continue
        seen_ids.add(n["id"])
        deduped_nodes.append(n)
    nodes = deduped_nodes

    # Dead code is dropped here and now, so nothing downstream has to think
    # about it -- see "TWO DECISIONS BAKED IN" at the top for why.
    live_scripts = [n for n in nodes if n["type"] in SCRIPT_TYPES and not n.get("dead")]
    dead_ids = {n["id"] for n in nodes if n.get("dead")}

    box_nodes = [n for n in nodes if n["type"] in BOX_TYPES]
    box_ids = {n["id"] for n in box_nodes}

    # Look up a script's display name and type from its id, for labelling arrows.
    script_label = {n["id"]: n["label"].split("\\n")[0] for n in live_scripts}
    script_type = {n["id"]: n["type"] for n in live_scripts}
    # Which pipeline stage each script belongs to. Needed so that a script
    # drawn as a junction box lands inside the right panel instead of floating
    # loose on the canvas -- a loose junction drags its arrows right across the
    # diagram.
    script_stage = {n["id"]: n["stage"] for n in live_scripts}

    # For every script we collect the data boxes flowing IN and the data boxes
    # flowing OUT. Arrows to and from other SCRIPTS are ignored -- in this view
    # a script calling another script isn't a data relationship, and the other
    # two diagrams already show that.
    def data_inputs(script_id):
        """The data boxes this script reads."""
        return [e for e in edges if e["to"] == script_id and e["from"] in box_ids]

    def data_outputs(script_id):
        """The data boxes this script writes."""
        return [e for e in edges if e["from"] == script_id and e["to"] in box_ids]

    def is_inferred(*legs):
        """True if any leg of the journey was only an assumption.

        Task 1 flagged some connections as existing via a shared folder or a
        queue rather than an actual line of code. If either half of a bridged
        arrow was one of those, the whole arrow is only as trustworthy as that
        half -- so it stays marked inferred and gets drawn differently.
        """
        return any(leg["kind"] == "inferred" for leg in legs)

    simple_edges = []    # directly labelled arrows
    junctions = []       # scripts that get a dot instead: (script_id, ins, outs)
    seen = set()         # de-duplicates identical arrows

    for script in live_scripts:
        sid = script["id"]
        ins = data_inputs(sid)
        outs = data_outputs(sid)

        # A script with no data going in, or none coming out, has no data
        # relationship to draw. required_packages.R is the clearest example: it
        # installs R packages and touches no data at all.
        if not ins or not outs:
            continue

        if len(ins) * len(outs) <= PAIR_LIMIT:
            for i in ins:
                for o in outs:
                    key = (i["from"], o["to"], sid)
                    if key in seen:
                        continue
                    seen.add(key)
                    simple_edges.append({
                        "from": i["from"], "to": o["to"],
                        "label": script_label[sid],
                        "stype": script_type[sid],
                        "inferred": is_inferred(i, o),
                    })
        else:
            junctions.append({"id": sid, "ins": ins, "outs": outs})

    # A handful of genuinely distinct scripts can legitimately share the same
    # (from, to) box pair -- e.g. fluke's mrip_lists -> mrip_processed, done
    # by 2 different scripts. Rather than draw one full-strength line per
    # script on top of the others, collapse each pair to a single arrow,
    # thickened by how many scripts share it and labelled with all their
    # names (see DIAGRAM_LAYOUT_PLAN.md Phase 2, Problem 2).
    edges_by_pair = {}
    for e in simple_edges:
        edges_by_pair.setdefault((e["from"], e["to"]), []).append(e)

    combined_edges = []
    for (frm, to), group in edges_by_pair.items():
        labels = []
        for g in group:
            if g["label"] not in labels:
                labels.append(g["label"])
        combined_edges.append({
            "from": frm,
            "to": to,
            "label": ", ".join(labels),
            "stype": group[0]["stype"],
            "inferred": any(g["inferred"] for g in group),
            "share_count": len(group),
        })
    simple_edges = combined_edges

    return {
        "box_nodes": box_nodes,
        "simple_edges": simple_edges,
        "junctions": junctions,
        "dead_ids": dead_ids,
        "script_label": script_label,
        "script_type": script_type,
        "script_stage": script_stage,
    }


# ==============================================================================
# SECTION 3: BUILD THE DIAGRAM
# ==============================================================================

def build_graph(project, stages, folded):
    """Return the finished Graphviz drawing, ready to render."""
    box_nodes = folded["box_nodes"]
    simple_edges = folded["simple_edges"]
    junctions = folded["junctions"]
    script_label = folded["script_label"]
    script_type = folded["script_type"]
    script_stage = folded["script_stage"]

    dot = Digraph("%s_data" % project.key, format="png")

    dot.attr(
        rankdir="TB",
        labelloc="t",
        label=("%s - Data-Focused View\\n"
               "Boxes are data files. Each arrow is labelled with the script that "
               "does the work.\\n"
               "All toggles assumed ON; dead code excluded.\\n"
               % project.display_name),
        fontname="Helvetica-Bold",
        fontsize="20",
        size="17,11",
        dpi="200",
        nodesep="0.30",
        ranksep="0.75",
        splines="spline",
        bgcolor="white",
        # One global rank grid across all the panels (same setting the
        # comprehensive diagram always had). Without it, each panel keeps its
        # own local grid, which is allowed to drift some tens of points from
        # its neighbours' -- enough to blur the edges of the Phase 3 bands.
        newrank="true",
    )

    dot.attr("node", fontname="Helvetica", fontsize="10", margin="0.13,0.07")
    dot.attr("edge", fontname="Helvetica", fontsize="9")

    # The project's banding choices (which stages are held alone at the top
    # and bottom of the page), and the stage order re-sequenced to match --
    # see layout.py and DIAGRAM_LAYOUT_PLAN.md Phase 3.
    layout = layout_spec(project)
    stages = arrange_stages(stages, layout["top_group"], layout["last_stage"])

    # --- Draw the data boxes, grouped by pipeline stage ----------------------
    # Grouping keeps the diagram readable and preserves execution order: the
    # panels run top to bottom in the order the pipeline actually works
    # through them.

    for stage_id, stage_label in stages:
        stage_boxes = [n for n in box_nodes if n["stage"] == stage_id]
        stage_junctions = [j for j in junctions if script_stage[j["id"]] == stage_id]

        # Skip a panel only if it has NOTHING in it. Checking the junctions too
        # matters: Stage 0 holds no data files at all, only scripts, so testing
        # data boxes alone would skip it -- and then its junction box (the R
        # wrapper) would never get created. Graphviz would silently invent a
        # blank default node from the arrows pointing at it.
        if not stage_boxes and not stage_junctions:
            continue

        with stage_panel(dot, stage_id, layout["top_group"]) as sub:
            sub.attr(label=stage_label, fontname="Helvetica-Bold", fontsize="12",
                     color="#9aa5b1", style="rounded", bgcolor="#fafbfc",
                     margin="12")

            for n in stage_boxes:
                style = EXTERNAL_STYLE if n["type"] == "external" else DATA_STYLE
                sub.node(n["id"], n["label"], **style)

            # Busy scripts are drawn as a labelled junction box (see Section 2).
            # They are created HERE, inside their own stage's panel, so they sit
            # among the data files they work on rather than drifting to the edge
            # of the picture and stretching their arrows across everything.
            for j in stage_junctions:
                color = SCRIPT_COLOR[script_type[j["id"]]]
                sub.node("junction_" + j["id"], script_label[j["id"]],
                         shape="box", style="filled,rounded", fillcolor="#ffffff",
                         color=color, fontcolor=color, fontname="Helvetica-Bold",
                         fontsize="10", margin="0.10,0.05")

    # Pin the panels into the order the project declared -- without this,
    # Graphviz places them purely by what the edges imply, which does not
    # reliably come out top-to-bottom in `stages` order.
    junction_ids_by_stage = {}
    for j in junctions:
        junction_ids_by_stage.setdefault(script_stage[j["id"]], []).append("junction_" + j["id"])
    pin_stage_order(dot, stages, box_nodes, extra_ids_by_stage=junction_ids_by_stage,
                    top_group=layout["top_group"],
                    last_stage=layout["last_stage"])

    # --- Draw the simple, direct arrows --------------------------------------

    # Which stage each drawable id lives in (data boxes and junction boxes) --
    # needed to spot the few edges that cross a Phase 3 band pointing up the
    # page. Those get drawn pre-reversed so they cannot form a cycle with the
    # band constraints -- same line, same arrowhead, see
    # layout.flip_for_bands().
    stage_of = {n["id"]: n["stage"] for n in box_nodes}
    stage_of.update(("junction_" + j["id"], script_stage[j["id"]])
                    for j in junctions)

    def draw_edge(src, dst, **style):
        if flip_for_bands(stage_of.get(src), stage_of.get(dst),
                          layout["top_group"], layout["last_stage"]):
            if style.get("arrowhead") != "none":
                style["dir"] = "back"
            dot.edge(dst, src, **style)
        else:
            dot.edge(src, dst, **style)

    for e in simple_edges:
        # Pairs shared by more than one script (see fold_scripts()) get a
        # thicker line instead of a second line drawn on top of the first.
        extra_scripts = e.get("share_count", 1) - 1
        if e["inferred"]:
            penwidth = 1.4 + PAIR_SHARE_PENWIDTH_STEP * extra_scripts
            draw_edge(e["from"], e["to"], label="  " + e["label"],
                      color=INFERRED_COLOR, fontcolor=INFERRED_COLOR,
                      style="dotted", penwidth=str(penwidth))
        else:
            color = SCRIPT_COLOR[e["stype"]]
            penwidth = 1.3 + PAIR_SHARE_PENWIDTH_STEP * extra_scripts
            draw_edge(e["from"], e["to"], label="  " + e["label"],
                      color=color, fontcolor=color, penwidth=str(penwidth))

    # --- Draw the arrows into and out of the junction boxes ------------------
    # The boxes themselves were already created inside their stage panels
    # above; here we only join them up. Inputs arrive with no arrowhead (they
    # are feeding in, not producing anything yet); outputs leave with a normal
    # arrowhead. That reads as one event: gather, run, produce.

    for j in junctions:
        sid = j["id"]
        color = SCRIPT_COLOR[script_type[sid]]
        node_id = "junction_" + sid

        for i in j["ins"]:
            inferred = i["kind"] == "inferred"
            draw_edge(i["from"], node_id, arrowhead="none",
                      color=INFERRED_COLOR if inferred else color,
                      style="dotted" if inferred else "solid",
                      penwidth="1.2")

        for o in j["outs"]:
            inferred = o["kind"] == "inferred"
            draw_edge(node_id, o["to"],
                      color=INFERRED_COLOR if inferred else color,
                      style="dotted" if inferred else "solid",
                      penwidth="1.3")

    # --- The legend ----------------------------------------------------------
    # Built as one compact table rather than as separate boxes, for the same
    # reason as in the simplified diagram: separate boxes get spread out by the
    # diagram's row spacing and the legend ends up taller than the content.

    legend_html = (
        '<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="4" CELLPADDING="2">'
        '<TR><TD COLSPAN="2"><B>LEGEND</B></TD></TR>'
        + legend_swatch(palette.NODE_COLORS["data"]["fillcolor"],
                        palette.NODE_COLORS["data"]["color"], "a data file")
        + legend_swatch(palette.NODE_COLORS["external"]["fillcolor"],
                        palette.NODE_COLORS["external"]["color"],
                        "outside the code<BR ALIGN=\"LEFT\"/>"
                        "&nbsp;(Drive, Oracle, queue)")
        + '<TR><TD COLSPAN="2"></TD></TR>'
        + legend_line(palette.NODE_COLORS["stata"]["color"], "&#8212;&#8212;&gt;",
                      "made by a Stata script<BR ALIGN=\"LEFT\"/>"
                      "&nbsp;(named on the arrow)")
        + legend_line(palette.NODE_COLORS["r"]["color"], "&#8212;&#8212;&gt;",
                      "made by an R script")
        + legend_line(palette.EDGE_COLORS["inferred"], "&#183;&#183;&#183;&#183;&gt;",
                      "shared folder / queue,<BR ALIGN=\"LEFT\"/>"
                      "&nbsp;NOT a code call")
        + '<TR><TD COLSPAN="2"></TD></TR>'
        + '<TR><TD COLSPAN="2" ALIGN="LEFT">'
          '<FONT POINT-SIZE="9">A boxed script name means that script has<BR ALIGN="LEFT"/>'
          'many inputs and outputs: everything flowing<BR ALIGN="LEFT"/>'
          'in is read, everything flowing out is written.</FONT></TD></TR>'
        + '</TABLE>>'
    )

    dot.node("legend_box", legend_html, shape="box", style="rounded",
             color="#9aa5b1", fillcolor="white", fontname="Helvetica",
             fontsize="10", margin="0.1,0.06")

    return dot


# ==============================================================================
# SECTION 4: BUILD THE SAME DIAGRAM IN MERMAID
# ==============================================================================
# Section 2's fold_scripts() -- the hybrid rule that decides which scripts
# become labelled arrows and which become junction boxes -- is shared. It is a
# statement about the pipeline, not about the drawing program.
#
# The one visible difference: this engine cannot pre-size the picture to a
# page the way the Graphviz version's size="17,11" does. See the note in
# render_simple.py's Section 4.

def build_mermaid(project, stages, folded):
    """Return the Mermaid source for the data-focused diagram."""
    box_nodes = folded["box_nodes"]
    simple_edges = folded["simple_edges"]
    junctions = folded["junctions"]
    script_label = folded["script_label"]
    script_type = folded["script_type"]
    script_stage = folded["script_stage"]

    chart = mermaid.Flowchart(
        title="%s - Data-Focused View   |   boxes are data files, each arrow "
              "is labelled with the script that does the work; a BOXED script "
              "name is a script with many inputs and outputs (everything "
              "flowing in is read, everything flowing out is written); all "
              "toggles assumed ON, dead code excluded" % project.display_name)

    layout = layout_spec(project)
    stages = arrange_stages(stages, layout["top_group"], layout["last_stage"])

    for stage_id, stage_label in stages:
        stage_boxes = [n for n in box_nodes if n["stage"] == stage_id]
        stage_junctions = [j for j in junctions
                           if script_stage[j["id"]] == stage_id]
        # Same reason as the Graphviz path: a stage with no data files but a
        # junction box in it (Stage 0 holds only scripts) still needs a panel,
        # or the junction has nowhere to live.
        if not stage_boxes and not stage_junctions:
            continue

        with chart.panel(stage_id, stage_label, fill="#fafbfc"):
            for n in stage_boxes:
                colors = palette.NODE_COLORS[n["type"]]
                chart.node(n["id"], n["label"],
                           shape=("hexagon" if n["type"] == "external"
                                  else "cylinder"),
                           fill=colors["fillcolor"], stroke=colors["color"])
            for j in stage_junctions:
                color = SCRIPT_COLOR[script_type[j["id"]]]
                chart.node("junction_" + j["id"], script_label[j["id"]],
                           shape="box", fill="#ffffff", stroke=color,
                           text_color=color)

    for e in simple_edges:
        extra_scripts = e.get("share_count", 1) - 1
        if e["inferred"]:
            color = INFERRED_COLOR
            width = 1.4 + PAIR_SHARE_PENWIDTH_STEP * extra_scripts
        else:
            color = SCRIPT_COLOR[e["stype"]]
            width = 1.3 + PAIR_SHARE_PENWIDTH_STEP * extra_scripts
        chart.edge(e["from"], e["to"], label=e["label"], color=color,
                   width=width, dotted=e["inferred"])

    # Junction arrows: inputs arrive with no arrowhead (they are feeding in,
    # not producing anything yet), outputs leave with one. That reads as a
    # single event -- gather, run, produce.
    for j in junctions:
        sid = j["id"]
        color = SCRIPT_COLOR[script_type[sid]]
        node_id = "junction_" + sid
        for i in j["ins"]:
            inferred = i["kind"] == "inferred"
            chart.edge(i["from"], node_id, arrow=False,
                       color=INFERRED_COLOR if inferred else color,
                       width=1.2, dotted=inferred)
        for o in j["outs"]:
            inferred = o["kind"] == "inferred"
            chart.edge(node_id, o["to"],
                       color=INFERRED_COLOR if inferred else color,
                       width=1.3, dotted=inferred)

    samples = [
        ("lg_data", "a data file", palette.NODE_COLORS["data"], "cylinder"),
        ("lg_ext", "outside the code\n(Drive, Oracle, queue)",
         palette.NODE_COLORS["external"], "hexagon"),
    ]
    arrows = [
        ("made by a Stata script\n(named on the arrow)",
         palette.NODE_COLORS["stata"]["color"], 1.3, False),
        ("made by an R script", palette.NODE_COLORS["r"]["color"], 1.3, False),
        ("shared folder / queue,\nNOT a code call", INFERRED_COLOR, 1.4, True),
    ]
    with chart.panel("legend", "LEGEND", fill="#ffffff"):
        for node_id, label, colors, shape in samples:
            chart.node(node_id, label, shape=shape,
                       fill=colors["fillcolor"], stroke=colors["color"])
        for i, _ in enumerate(arrows):
            chart.point("lg_a%d" % i)
            chart.point("lg_b%d" % i)
    for i, (label, color, width, dotted) in enumerate(arrows):
        chart.edge("lg_a%d" % i, "lg_b%d" % i, label=label, color=color,
                   width=width, dotted=dotted)

    return chart.text()


# ==============================================================================
# SECTION 5: WRITE THE PICTURE FILES
# ==============================================================================

def render(project, stages, nodes, edges, engine=DEFAULT_ENGINE):
    """Draw the data-focused diagram and write the .png and .svg."""
    folded = fold_scripts(nodes, edges)
    base = project.output_base(DIAGRAM_FILE)

    if engine == "mermaid":
        png_path, svg_path = mermaid.render_text(
            build_mermaid(project, stages, folded), base,
            description="data-focused diagram")
    else:
        ensure_on_path()
        dot = build_graph(project, stages, folded)
        png_path = dot.render(filename=base, format="png", cleanup=True)
        svg_path = dot.render(filename=base, format="svg", cleanup=True)

    simple_edges = folded["simple_edges"]
    junctions = folded["junctions"]
    arrow_count = len(simple_edges) + sum(len(j["ins"]) + len(j["outs"])
                                          for j in junctions)

    print("")
    print("Success! The data-focused diagram was generated.")
    print("")
    print("  PNG (double-click to view): " + png_path)
    print("  SVG (open in a web browser): " + svg_path)
    print("")
    print("  " + str(len(folded["box_nodes"])) + " data boxes and " + str(arrow_count) + " arrows drawn.")
    print("  " + str(len(simple_edges)) + " arrows are labelled directly; "
          + str(len(junctions)) + " busy scripts use a junction box.")
    print("  " + str(len(folded["dead_ids"])) + " dead-code scripts excluded; all toggles assumed ON.")

    return png_path, svg_path
