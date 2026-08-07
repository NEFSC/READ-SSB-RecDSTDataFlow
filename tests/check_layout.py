"""
check_layout.py
================================================================================
Score a rendered diagram: how many lines cross, and do the pipeline stages read
in the order they were declared?

WHY THIS EXISTS
--------------------------------------------------------------------------------
"Does the new engine draw a better picture?" is otherwise unanswerable -- two
people look at two large diagrams and disagree. This turns it into two numbers
that are computed the same way for both engines, so a change can be checked
instead of argued about.

It is the harness the renderer spike was decided on (it produced every figure in
diagram_spikes/results/RESULTS.md) and it was COPIED here, not imported: the
spike folder is disposable and deleting it must not break anything real.

WHAT IT MEASURES
--------------------------------------------------------------------------------
A stage's position is derived from the positions of its member NODES, never
from the renderer's own cluster markup -- Graphviz and Mermaid mark clusters up
completely differently, but both preserve the node ids this toolchain emits.
That is what makes one number comparable with the other.

  crossings   pairwise intersections of edges drawn as straight lines between
              node centres. Deliberately crude, and the absolute value means
              nothing; the ratio between two renderings of the SAME graph is
              the number to read.
  corr_y      rank correlation between declared stage order and the order the
              stages actually appear down the page. +1.000 is perfect.
  corr_x      the same for left-to-right, which is what "setup in the top-left
              corner" depends on.

USAGE
--------------------------------------------------------------------------------
    py tests/check_layout.py groundfish
    py tests/check_layout.py groundfish comprehensive
    py tests/check_layout.py fluke --all

It scores whatever is currently in output/<project>/ -- it does not draw
anything. Draw first, then score:

    py make_groundfish_diagrams.py --engine=mermaid --no-extract --no-archive
    py tests/check_layout.py groundfish

REFERENCE NUMBERS (groundfish comprehensive, 82 nodes / 131 edges)
--------------------------------------------------------------------------------
    Graphviz          414 crossings, corr_y +0.905, corr_x +0.000
    Mermaid + ELK     243 crossings, corr_y +0.881, corr_x +0.548  (bare graph)
    Mermaid + ELK     283 crossings, corr_y +0.762, corr_x +0.381  (all features)

The third row is what this toolchain now emits. A result far from it means
something changed -- which may be fine, but should be deliberate.
================================================================================
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DIAGRAMS_DIR = os.path.dirname(HERE)
sys.path.insert(0, DIAGRAMS_DIR)
sys.path.insert(0, HERE)

import measure           # noqa: E402
import svg_positions     # noqa: E402


# Which SVG belongs to which diagram, and which node ids that diagram actually
# draws. The simple and data diagrams draw a SUBSET of the nodes (scripts only,
# data files only), so scoring them against all 82 would report most of the
# graph as "missing" every time.
DIAGRAMS = ("comprehensive", "simple", "data")


def load_project(key):
    """The Project record for a project key, e.g. 'groundfish'."""
    import importlib
    module = importlib.import_module("projects." + key)
    return module.PROJECT


def drawn_nodes(diagram, nodes, edges):
    """The nodes a given diagram actually puts on the page.

    Re-uses each renderer's own filtering rule rather than restating it, so
    this cannot drift from what is drawn.
    """
    if diagram == "simple":
        from rdm_diagrams import render_simple
        kept, simple_edges = render_simple.simplify(nodes, edges)
        return kept, simple_edges
    if diagram == "data":
        from rdm_diagrams import render_data
        folded = render_data.fold_scripts(nodes, edges)
        # Score the data diagram on its boxes and its direct arrows. The
        # junction boxes are drawn too, but they are synthetic ids that carry
        # no stage of their own in `nodes`, so including them would say more
        # about this script than about the picture.
        box_edges = [{"from": e["from"], "to": e["to"], "kind": "dataflow"}
                     for e in folded["simple_edges"]]
        return folded["box_nodes"], box_edges
    return nodes, edges


def score_diagram(project, diagram, stages, nodes, edges):
    """Score one rendered diagram, or None if its SVG is not there."""
    from rdm_diagrams import RENDERERS
    from rdm_diagrams.layout import arrange_stages, layout_spec

    svg_path = project.output_base(RENDERERS[diagram].DIAGRAM_FILE) + ".svg"
    if not os.path.isfile(svg_path):
        print("no rendered SVG for the %s diagram (%s)" % (diagram, svg_path))
        return None

    with open(svg_path, "r", encoding="utf-8") as fh:
        head = fh.read(4000)
    # Which parser to use is decided by what the file says it is, not by a
    # flag the caller has to remember to pass -- getting that wrong would
    # silently score zero nodes.
    if "aria-roledescription=\"flowchart" in head or "mermaid" in head[:2000]:
        positions = svg_positions.mermaid_positions(svg_path)
        engine = "mermaid"
    else:
        positions = svg_positions.graphviz_positions(svg_path)
        engine = "graphviz"

    diagram_nodes, diagram_edges = drawn_nodes(diagram, nodes, edges)
    real_ids = {n["id"] for n in diagram_nodes}
    positions = {k: v for k, v in positions.items() if k in real_ids}

    spec = layout_spec(project)
    ordered = arrange_stages(stages, spec["top_group"], spec["last_stage"])

    result = measure.score(
        "%s / %s / %s" % (project.key, diagram, engine),
        positions, diagram_nodes, diagram_edges, ordered,
        spec["top_group"], spec["last_stage"],
        notes="scored from " + os.path.basename(svg_path))
    print(measure.format_report(result))

    # A renderer that silently drops boxes is drawing a different graph, and
    # every number above would be measuring that other graph instead.
    missing = result["nodes_expected"] - result["nodes_located"]
    if missing:
        print("")
        print("  WARNING: %d of %d boxes were not found in the SVG."
              % (missing, result["nodes_expected"]))
    return result


def main(argv):
    if not argv or argv[0].startswith("-"):
        print(__doc__.strip().split("USAGE")[1].split("REFERENCE")[0].strip())
        return 1

    key = argv[0]
    wanted = [a for a in argv[1:] if not a.startswith("-")] or list(DIAGRAMS)
    if "--all" in argv:
        wanted = list(DIAGRAMS)

    project = load_project(key)
    from rdm_diagrams import load_pipeline_data
    stages, nodes, edges = load_pipeline_data(project)

    ok = True
    for diagram in wanted:
        if diagram not in DIAGRAMS:
            print("no diagram called %r; choose from %s"
                  % (diagram, ", ".join(DIAGRAMS)))
            return 1
        print("")
        if score_diagram(project, diagram, stages, nodes, edges) is None:
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
