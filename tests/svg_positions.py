"""
svg_positions.py
================================================================================
Pull {node_id: (x, y)} out of a rendered SVG, for the two renderers that produce
one (Graphviz and Mermaid). visNetwork needs nothing from here -- its
coordinates are computed in Python before rendering, so they are already known.

Both parsers return the CENTRE of the node's drawn shape, in the SVG's own
coordinate system with y increasing downward. No normalisation happens here;
measure.normalise() owns that.
================================================================================
"""

import re
import xml.etree.ElementTree as ET


SVG_NS = "{http://www.w3.org/2000/svg}"
_NUM = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")


def _points_of(elem):
    """Every (x, y) pair implied by one drawn shape element.

    Graphviz draws boxes as <path> (rounded corners), <polygon> (plain) or
    <ellipse>; Mermaid uses <rect>, <path> and <polygon>. Rather than special-
    case each, pull the raw numbers and pair them off -- every one of those
    attributes is a flat sequence of x,y pairs, so the bounding box of the
    pairs is the shape's bounding box (over-large for curves, but the CENTRE,
    which is all that is wanted, is unaffected by that).
    """
    tag = elem.tag.replace(SVG_NS, "")
    if tag == "ellipse":
        return [(float(elem.get("cx", 0)), float(elem.get("cy", 0)))]
    if tag == "circle":
        return [(float(elem.get("cx", 0)), float(elem.get("cy", 0)))]
    if tag == "rect":
        x, y = float(elem.get("x", 0)), float(elem.get("y", 0))
        w, h = float(elem.get("width", 0)), float(elem.get("height", 0))
        return [(x, y), (x + w, y + h)]
    if tag in ("path", "polygon", "polyline"):
        raw = elem.get("d") or elem.get("points") or ""
        nums = [float(m.group()) for m in _NUM.finditer(raw)]
        return list(zip(nums[0::2], nums[1::2]))
    return []


def _centre(elem):
    """Centre of the bounding box of every shape inside `elem`."""
    pts = []
    for child in elem.iter():
        pts.extend(_points_of(child))
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0)


# ==============================================================================
# GRAPHVIZ
# ==============================================================================

def graphviz_positions(svg_path):
    """{node_id: (x, y)} from a Graphviz-generated SVG.

    Graphviz writes each node as <g class="node"><title>ID</title> shape...</g>,
    with the id verbatim in the title -- that is the hook. The y values are
    negative (Graphviz's own axis points up and it emits a compensating
    translate on the parent <g>); since the translate is a single constant for
    the whole page, raw y still orders nodes correctly top-to-bottom, and
    measure.normalise() removes the offset. So no sign flip is needed or wanted.
    """
    root = ET.parse(svg_path).getroot()
    out = {}
    for g in root.iter(SVG_NS + "g"):
        if g.get("class") != "node":
            continue
        title = g.find(SVG_NS + "title")
        if title is None or not title.text:
            continue
        centre = _centre(g)
        if centre is not None:
            out[title.text.strip()] = centre
    return out


# ==============================================================================
# MERMAID
# ==============================================================================

# Mermaid names a node group `<svgId>-flowchart-<node id>-<counter>`; the svg id
# prefix ("my-svg" by default) and the trailing counter are both Mermaid's, so
# both are stripped to recover the id this spike emitted. Non-greedy up to the
# LAST "flowchart-" so a prefix containing a dash cannot eat into the node id.
_MERMAID_ID = re.compile(r"^.*?flowchart-(.+?)-\d+$")
_TRANSLATE = re.compile(r"translate\(\s*(-?[\d.]+)[ ,]+(-?[\d.]+)\s*\)")


def mermaid_positions(svg_path):
    """{node_id: (x, y)} from a Mermaid-generated SVG.

    Mermaid names each node group `flowchart-<id>-<n>` (the trailing number is
    an internal counter, stripped here) and positions it with a translate()
    rather than by giving the shape absolute coordinates -- so the group's own
    transform IS the node centre, and the shape geometry inside it is relative
    to that. Nested <g> transforms are accumulated on the way down, because a
    node inside a subgraph inherits the subgraph group's translate too.
    """
    root = ET.parse(svg_path).getroot()
    out = {}

    def walk(elem, ox, oy):
        for child in elem:
            if child.tag != SVG_NS + "g":
                continue
            dx, dy = 0.0, 0.0
            m = _TRANSLATE.search(child.get("transform") or "")
            if m:
                dx, dy = float(m.group(1)), float(m.group(2))
            x, y = ox + dx, oy + dy
            cid = child.get("id") or ""
            match = _MERMAID_ID.match(cid)
            if match and "node" in (child.get("class") or ""):
                out[match.group(1)] = (x, y)
            walk(child, x, y)

    walk(root, 0.0, 0.0)
    return out
