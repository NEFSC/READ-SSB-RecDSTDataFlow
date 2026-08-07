"""
legend.py
================================================================================
Two small helpers for building an HTML-table legend, shared by whichever
renderers draw their legend that way (render_simple.py and render_data.py --
render_dataflow.py's legend is a cluster of real graph nodes instead, a
structurally different approach left as-is since it is not just the same
table redrawn).

Before this existed, render_simple.py had these two functions and
render_data.py had its own ~30-line hand-rolled HTML string doing the exact
same job with its own copy-pasted row layout. One row of drift there would
have been invisible until the two legends started looking different for no
reason.

Graphviz tables cannot draw a real arrow, so legend_line() fakes one with
dash characters coloured to match the arrows in the diagram. Only
long-established characters are used (em dash, en dash, middle dot, plain
">"). Fancier box-drawing and triangle characters look better but are
missing from some fonts, and a missing character renders as an empty
rectangle -- which would make the legend look broken on whichever machine
happens to lack the font.
================================================================================
"""


def legend_swatch(fill, border, text):
    """One row of the legend showing a coloured box next to its meaning."""
    return ('<TR>'
            '<TD BGCOLOR="' + fill + '" COLOR="' + border + '" WIDTH="26"></TD>'
            '<TD ALIGN="LEFT">&nbsp;' + text + '</TD>'
            '</TR>')


def legend_line(color, dash, text):
    """One row of the legend showing a sample line next to its meaning."""
    return ('<TR>'
            '<TD ALIGN="CENTER"><FONT COLOR="' + color + '" POINT-SIZE="13">'
            '<B>' + dash + '</B></FONT></TD>'
            '<TD ALIGN="LEFT">&nbsp;' + text + '</TD>'
            '</TR>')
