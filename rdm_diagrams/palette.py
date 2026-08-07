"""
palette.py
================================================================================
WHAT THIS FILE IS
--------------------------------------------------------------------------------
The one shared definition of what colour means what, across all three
diagrams.

Before this existed, each renderer kept its own copy of these colours, and
they quietly drifted apart: render_simple.py's blues, greens and oranges were
each a few shades off render_dataflow.py's, despite every renderer's own
comments promising "same colours as the other diagrams". A reader who
learned "blue = Stata script" from one diagram had no real guarantee the same
blue was waiting in the next one -- and a future palette change meant editing
three files and hoping none got missed.

--------------------------------------------------------------------------------
WHAT IS -- AND IS NOT -- SHARED HERE
--------------------------------------------------------------------------------
Only fill colour, border colour and the two "calls"/"inferred" line colours
live here. Shape, dash pattern, font colour and line weight are deliberately
NOT unified -- those vary between diagrams on purpose (render_simple.py uses
thinner lines and smaller arrowheads because it is built to fit a slide;
render_dataflow.py's shiny box uses shape="box3d" for a 3-D look that would be
overkill on the simplified view). Only the colour IDENTITY of each box or
arrow type is meant to be identical everywhere, so only that is centralised.
================================================================================
"""


# Fill and border colour for each kind of box, keyed by node type. Every
# renderer builds its own style dict on top of these two values, adding
# whatever shape/style/fontcolor that diagram needs.
NODE_COLORS = {
    "stata":    {"fillcolor": "#cfe3f7", "color": "#2d6ca2"},
    "r":        {"fillcolor": "#d4edcf", "color": "#3f7a35"},
    "shiny":    {"fillcolor": "#e2d4f0", "color": "#6b4c93"},
    "data":     {"fillcolor": "#ececec", "color": "#7a7a7a"},
    "external": {"fillcolor": "#fdf1d0", "color": "#b8860b"},
}

# Line colour for each kind of arrow. Penwidth, arrowsize and dash pattern are
# left to each renderer to decide, same reasoning as NODE_COLORS above.
EDGE_COLORS = {
    "calls":    "#e07b39",
    "reads":    "#8a8a8a",
    "writes":   "#8a8a8a",
    "inferred": "#c0392b",
}

# How a "dead code" box is faded, regardless of which diagram draws it. One
# shared look, so a script marked dead reads as "switched off" the same way
# everywhere instead of two different shades of grey depending which diagram
# you happen to be looking at.
DEAD_CODE_OVERRIDE = {
    "fillcolor": "#ececec",
    "color": "#a0a0a0",
    "fontcolor": "#8a8a8a",
}
