"""
mermaid.py
================================================================================
WHAT THIS FILE IS
--------------------------------------------------------------------------------
The Mermaid half of the toolchain: a small builder for Mermaid `flowchart`
text, and the step that turns that text into a .png and a .svg.

It is the counterpart of what the `graphviz` Python package does for the other
engine -- the three renderer modules describe a picture, and this file is what
actually draws it. The shape of the toolchain does not change: Python emits
text, a command-line program turns the text into pictures.

Why Mermaid at all: see MERMAID_MIGRATION_PLAN.md and
diagram_spikes/results/RESULTS.md. In one line -- on the groundfish
comprehensive diagram it draws the same 82 boxes and 131 arrows with 41% fewer
line crossings than Graphviz, and it can be made to put the pipeline stages in
declared order, which Graphviz provably cannot.

--------------------------------------------------------------------------------
THE FOUR THINGS THAT BITE, ALL OF WHICH ARE HANDLED HERE
--------------------------------------------------------------------------------
1. Mermaid REFUSES to draw graphs it thinks are too big. The limits are
   `maxEdges` (default 500) and `maxTextSize` (default 50 000); this diagram is
   131 edges and several KB of label text, and fluke is bigger. Both are
   "secure" settings, which means Mermaid will only accept them from a config
   FILE -- never from the diagram's own front-matter. See CONFIG below.

2. If the ELK layout plugin cannot be loaded, Mermaid does not fail. It quietly
   falls back to its default engine, which orders the stages differently, and
   draws a confident-looking WRONG picture. Every render is therefore checked
   for the marker that only the ELK renderer emits.

3. Several characters in this data break the render or silently eat a label:
   `&` in "Setup & orchestration", the `<i>` in `calib_catch_draws_<i>.dta`
   (parsed as an italics tag, swallowing the rest of the label), quotes, and
   the embedded newlines the curation labels use. escape() handles all of them.

4. Mermaid has no per-edge colour attribute. Colours are applied afterwards by
   `linkStyle <index>`, where the index is the edge's position in declaration
   order -- so the builder has to keep count as it goes. Flowchart.edge() does
   that bookkeeping; nothing else should try to.

--------------------------------------------------------------------------------
WHAT IS DELIBERATELY NOT HERE
--------------------------------------------------------------------------------
Graphviz's `size` and `dpi` (scale the whole picture to fit a slide) have no
Mermaid equivalent -- Mermaid draws at natural size and `mmdc --scale` only
multiplies pixels. render_simple.py used `size="17,9.5"` to fit a 16:9 slide;
under this engine it cannot, and says so in its own docstring rather than
pretending otherwise.
================================================================================
"""

import json
import os
import shutil
import subprocess
import tempfile

from . import mermaid_path


# Mermaid config every diagram is rendered with. maxEdges/maxTextSize are the
# refusal limits described above; useMaxWidth=False stops Mermaid shrinking the
# drawing to the width of an imaginary browser window, which on a diagram this
# size makes the text unreadable.
CONFIG = {
    "layout": "elk",
    "maxEdges": 5000,
    "maxTextSize": 900000,
    "flowchart": {"useMaxWidth": False, "htmlLabels": True},
}

# The marker only Mermaid's ELK renderer puts in its output (its dagre renderer
# never emits a group with this class). Checked after every render -- see
# point 2 above.
_ELK_MARKER = 'class="subgraphs"'

# How long to wait for one render before giving up. A full 82-node ELK render
# takes ~3 s on the machine this was developed on; the timeout is set for a slow
# laptop having a bad day, not for a graph ten times this size.
_TIMEOUT_SECONDS = 900


# ==============================================================================
# SECTION 1: TEXT ESCAPING
# ==============================================================================

def escape(text):
    """Make a label safe inside a quoted Mermaid label.

    HTML labels are on (see CONFIG), so the label is read as HTML: `&` starts
    an entity, `<` starts a tag, and a literal newline ends the statement. Every
    one of those appears in this data, and each fails differently -- an
    unescaped `<i>` does not error, it turns the rest of the label italic and
    invisible.
    """
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("\\n", "<br/>")     # the curation lists use a literal \n
            .replace("\n", "<br/>"))


# ==============================================================================
# SECTION 2: THE FLOWCHART BUILDER
# ==============================================================================
# A thin wrapper over "append a line of text", doing only the bookkeeping that
# is easy to get wrong by hand: edge indices for linkStyle, class membership,
# and keeping the subgraph/edge/style blocks in the order Mermaid wants them.

class Flowchart:
    """Accumulates Mermaid `flowchart` source.

    Usage mirrors the graphviz Digraph the other engine builds:

        chart = Flowchart(title="...")
        with chart.panel("calib", "STAGE 5-11 ..."):
            chart.node("directed_trips", "directed_trips_calibration.do", "stata")
        chart.edge("a", "b", color="#e07b39", width=2.0)
        text = chart.text()

    Node and edge STYLE is applied per element rather than through Mermaid's
    `classDef` mechanism wherever a value varies (colours differ per node type
    AND per node state), because a Mermaid node can only carry one class
    cleanly and dead-code styling has to override type styling.
    """

    def __init__(self, title=None, subtitle=None, direction="TB"):
        self._title = title
        self._subtitle = subtitle
        self._direction = direction
        self._panels = []          # [(stage_id, title, [node lines])]
        self._loose = []           # nodes declared outside any panel
        self._current = None
        self._edges = []           # ["  a --> b", ...] in declaration order
        self._link_styles = {}     # edge index -> style string
        self._node_styles = []     # ["  style id fill:#fff,...", ...]

    # --- structure ------------------------------------------------------------

    class _Panel:
        """Context manager so a panel reads like the Graphviz `with` blocks."""

        def __init__(self, chart, stage_id, title, fill, stroke):
            self.chart = chart
            self.stage_id = stage_id
            self.title = title
            self.fill = fill
            self.stroke = stroke

        def __enter__(self):
            self.chart._panels.append([self.stage_id, self.title, []])
            self.chart._current = self.chart._panels[-1][2]
            # Mermaid's default cluster fill is a pale yellow that reads as
            # "highlighted"; the Graphviz diagrams use a near-white panel on a
            # grey border, so the panels recede and the boxes carry the colour.
            self.chart._node_styles.append(
                "  style sg_%s fill:%s,stroke:%s"
                % (self.stage_id, self.fill, self.stroke))
            return self.chart

        def __exit__(self, *exc):
            self.chart._current = None
            return False

    def panel(self, stage_id, title, fill="#fbfbfd", stroke="#9aa5b1"):
        """Open one labelled group of boxes (a pipeline stage)."""
        return self._Panel(self, stage_id, title, fill, stroke)

    # --- content --------------------------------------------------------------

    def node(self, node_id, label, shape="round", fill=None, stroke=None,
             text_color=None, dashed=False):
        """One box.

        `shape` is one of the keys in SHAPES below; anything else falls back to
        a rounded box rather than raising, because a new node type appearing in
        the curation list should not stop the diagram being drawn.
        """
        open_s, close_s = SHAPES.get(shape, SHAPES["round"])
        line = "    %s%s%s%s" % (node_id, open_s, escape(label), close_s)
        (self._current if self._current is not None else self._loose).append(line)

        bits = []
        if fill:
            bits.append("fill:%s" % fill)
        if stroke:
            bits.append("stroke:%s" % stroke)
        if text_color:
            bits.append("color:%s" % text_color)
        if dashed:
            bits.append("stroke-dasharray:4 3")
        if bits:
            self._node_styles.append("  style %s %s" % (node_id, ",".join(bits)))

    def point(self, node_id):
        """A deliberately invisible box.

        Used for the tap points hub bundling introduces and for the legend's
        sample arrows -- both need a node to attach an edge to, and neither
        should be visible. Mermaid has no `shape=point`, so it is an empty
        rounded box styled out of existence.
        """
        line = '    %s(" ")' % node_id
        (self._current if self._current is not None else self._loose).append(line)
        self._node_styles.append(
            "  style %s fill:none,stroke:none,color:#00000000" % node_id)

    def edge(self, src, dst, label=None, color=None, width=None, dotted=False,
             dashed=False, arrow=True):
        """One arrow. Returns its index, which is what `linkStyle` addresses.

        `dotted` and `dashed` pick the line pattern; `arrow=False` draws a plain
        line with no arrowhead (the data diagram's junction inputs, which feed
        in rather than produce).
        """
        if dotted or dashed:
            connector = "-.->" if arrow else "-.-"
        else:
            connector = "-->" if arrow else "---"

        if label:
            line = '  %s %s|"%s"| %s' % (src, connector, escape(label), dst)
        else:
            line = "  %s %s %s" % (src, connector, dst)
        self._edges.append(line)
        index = len(self._edges) - 1

        bits = []
        if color:
            # stroke and fill both: Mermaid uses `fill` for the arrowhead
            # marker on some renderers, and leaving it unset gives a
            # black-headed coloured line.
            bits.append("stroke:%s" % color)
            bits.append("fill:none")
        if width:
            bits.append("stroke-width:%gpx" % width)
        if bits:
            self._link_styles[index] = ",".join(bits)
        return index

    # --- output ---------------------------------------------------------------

    def text(self):
        """The finished Mermaid source."""
        out = []

        # Front matter carries the title. Mermaid has no equivalent of
        # Graphviz's multi-line graph label, so a caption longer than a title
        # belongs in a node (see the legend panels the renderers build).
        if self._title:
            # Always double-quoted: the front matter is parsed as YAML, and a
            # bare scalar containing a colon-space (as any title with a
            # "generated from: ..." clause does) is a YAML syntax error, which
            # surfaces from mmdc as an unexplained "YAMLException".
            safe = (self._title.replace("\n", " ")
                               .replace("\\", "\\\\")
                               .replace('"', '\\"'))
            out.append("---")
            out.append('title: "%s"' % safe)
            out.append("---")

        out.append("flowchart %s" % self._direction)

        for stage_id, title, lines in self._panels:
            out.append('  subgraph sg_%s["%s"]' % (stage_id, escape(title)))
            # Without this a wide panel can come back rotated relative to the
            # page -- ELK is free to lay a subgraph out sideways otherwise.
            out.append("    direction TB")
            out.extend(lines)
            out.append("  end")

        out.extend(self._loose)

        if self._edges:
            out.append("")
            out.extend(self._edges)

        if self._node_styles:
            out.append("")
            out.extend(self._node_styles)

        # linkStyle indices are edge declaration order. Identical styles are
        # merged into one statement, which keeps the tail of the file short on
        # a diagram where most edges share four or five looks.
        if self._link_styles:
            out.append("")
            by_style = {}
            for index, style in sorted(self._link_styles.items()):
                by_style.setdefault(style, []).append(index)
            for style, indices in by_style.items():
                out.append("  linkStyle %s %s"
                           % (",".join(str(i) for i in indices), style))

        return "\n".join(out) + "\n"


# Mermaid node shapes, chosen to read as closely as possible to the Graphviz
# shapes each diagram already uses. Mermaid has no cylinder-with-a-lid or
# octagon, so `[( )]` (a database drum) stands in for cylinder and `{{ }}` (a
# hexagon) for octagon.
SHAPES = {
    "round":    ('("', '")'),        # rounded box: scripts
    "box":      ('["', '"]'),        # square box
    "cylinder": ('[("', '")]'),      # data file
    "hexagon":  ('{{"', '"}}'),      # outside the code
    "subroutine": ('[["', '"]]'),    # emphasised box: the Shiny endpoint
}


# ==============================================================================
# SECTION 3: DRAW IT
# ==============================================================================

def render_text(text, output_base, description="diagram"):
    """Turn Mermaid source into `<output_base>.png` and `<output_base>.svg`.

    Returns (png_path, svg_path).

    The .mmd source is written to a temporary folder and deleted afterwards,
    matching what the Graphviz path does with its intermediate .gv file: the
    output folder is for pictures, and an intermediate left lying there looks
    like something a reader is supposed to open. Set KEEP_MERMAID_SOURCE=1 in
    the environment to keep it instead, which is the first thing to do when a
    render fails.
    """
    problem = mermaid_path.problem()
    if problem:
        raise MermaidNotInstalled(problem)

    png_path = output_base + ".png"
    svg_path = output_base + ".svg"

    workdir = tempfile.mkdtemp(prefix="rdm_mermaid_")
    keep = os.environ.get("KEEP_MERMAID_SOURCE")
    try:
        mmd_path = os.path.join(workdir, "diagram.mmd")
        with open(mmd_path, "w", encoding="utf-8") as fh:
            fh.write(text)
        config_path = os.path.join(workdir, "config.json")
        with open(config_path, "w", encoding="utf-8") as fh:
            json.dump(CONFIG, fh, indent=2)

        if keep:
            kept = output_base + ".mmd"
            shutil.copyfile(mmd_path, kept)
            print("  (kept the Mermaid source: %s)" % kept)

        for out_path in (svg_path, png_path):
            _run_mmdc(mmd_path, out_path, config_path, description)

        _check_elk_ran(svg_path, description)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    return png_path, svg_path


def _run_mmdc(mmd_path, out_path, config_path, description):
    """One mmdc invocation, with the failure turned into something readable."""
    cmd = ["mmdc", "-i", mmd_path, "-o", out_path, "-c", config_path,
           "--backgroundColor", "white"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=_TIMEOUT_SECONDS,
                              # shell=True on Windows: the installed thing is
                              # mmdc.cmd, which CreateProcess will not run
                              # directly.
                              shell=(os.name == "nt"))
    except subprocess.TimeoutExpired:
        raise MermaidFailed(
            "Mermaid took longer than %d seconds to draw the %s and was stopped."
            % (_TIMEOUT_SECONDS, description))

    if proc.returncode != 0 or not os.path.exists(out_path):
        raise MermaidFailed(
            "Mermaid could not draw the %s.\n\n%s"
            % (description, ((proc.stdout or "") + (proc.stderr or "")).strip()))


def _check_elk_ran(svg_path, description):
    """Fail loudly if the picture was drawn by the fallback engine.

    See point 2 in the module docstring: a dagre fallback is a wrong picture,
    not a missing one, and it is completely silent. This is the only thing
    standing between that and a diagram nobody realises is misordered.
    """
    with open(svg_path, "r", encoding="utf-8") as fh:
        if _ELK_MARKER in fh.read():
            return
    raise MermaidFailed(
        "The %s was drawn, but NOT by the ELK layout engine -- Mermaid fell\n"
        "back to its default engine, which puts the pipeline stages in a\n"
        "different order. The picture would be wrong, so it is being treated\n"
        "as a failure.\n\n%s" % (description, mermaid_path.INSTALL_HINT))


class MermaidNotInstalled(RuntimeError):
    """Raised when mmdc or its ELK plugin is missing."""


class MermaidFailed(RuntimeError):
    """Raised when mmdc ran but did not produce a usable picture."""
