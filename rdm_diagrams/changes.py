"""
changes.py
================================================================================
WHAT THIS FILE IS
--------------------------------------------------------------------------------
Says, in words, what changed between the previous run and this one.

The pictures are hard to compare by eye -- the comprehensive diagram is about
5900 pixels wide and holds 80-odd boxes, so one new arrow in it is genuinely
invisible unless you already know where to look. But the description those
pictures are drawn from is an exact list of every box and every arrow, so the
two versions can simply be compared item by item. That is what this does.

The output looks like:

    WHAT CHANGED SINCE THE LAST RUN
    ---------------------------------------------------------------
      Boxes added (1):
        * new_helper       new_helper.do              (calib panel)
      Boxes removed: none
      Arrows added (2):
        * model_wrapper -> new_helper      calls, if do_helper = 1
        * new_helper    -> trip_costs      writes

--------------------------------------------------------------------------------
NOTE ON THE SIMILAR CODE IN extract.py
--------------------------------------------------------------------------------
extract.run_check() compares two sets of boxes and arrows in much the same way,
against the old hand-typed snapshot rather than against the previous run. The
vocabulary here deliberately matches it -- boxes keyed by id, arrows keyed by
(from, to, kind) -- so the two reports read alike. They are kept separate on
purpose for now: run_check's output is byte-for-byte the same as the toolchain
this replaced, which is worth not disturbing.
================================================================================
"""


def parse(blob):
    """Turn the bytes of a pipeline_data_generated.py into its three lists.

    Returns (stages, nodes, edges), or None if the bytes cannot be read as that
    file. The generated module is plain data -- three literal lists and nothing
    else -- so running it is just a way of parsing it.
    """
    if not blob:
        return None
    namespace = {}
    try:
        exec(compile(blob, "<archived pipeline_data_generated.py>", "exec"), namespace)
        return namespace["STAGES"], namespace["nodes"], namespace["edges"]
    except Exception:
        return None


def _edge_key(edge):
    """Two arrows are the same arrow if they join the same boxes the same way."""
    return (edge["from"], edge["to"], edge["kind"])


def _describe_edge(edge):
    """One arrow, in words: its kind, and the switch controlling it if any."""
    text = edge["kind"]
    if edge.get("toggle"):
        default = "0" if edge.get("default_off") else "1"
        text += ", if %s = %s by default" % (edge["toggle"], default)
    elif edge.get("note"):
        text += ", " + edge["note"]
    return text


def _describe_node(node):
    """One box, in words: the first line of its label, and which panel it is in."""
    label = node["label"].split("\n")[0]
    return "%-38s (%s panel)" % (label, node["stage"])


def compare(old, new):
    """Compare two (stages, nodes, edges) triples.

    Returns a dictionary of what differs. An empty value for every key means the
    pipeline is unchanged.
    """
    _, old_nodes, old_edges = old
    _, new_nodes, new_edges = new

    old_by_id = {n["id"]: n for n in old_nodes}
    new_by_id = {n["id"]: n for n in new_nodes}

    old_by_key = {_edge_key(e): e for e in old_edges}
    new_by_key = {_edge_key(e): e for e in new_edges}

    # A box that exists in both but whose label, panel, type or dead-code flag
    # moved is a real visible change, so it gets its own list rather than being
    # counted as unchanged.
    altered = []
    for node_id in sorted(set(old_by_id) & set(new_by_id)):
        a, b = old_by_id[node_id], new_by_id[node_id]
        for field in ("type", "stage", "label"):
            if a.get(field) != b.get(field):
                altered.append((node_id, field, a.get(field), b.get(field)))
        if bool(a.get("dead")) != bool(b.get("dead")):
            altered.append((node_id, "dead", bool(a.get("dead")), bool(b.get("dead"))))

    return {
        "boxes_added":   [new_by_id[i] for i in sorted(set(new_by_id) - set(old_by_id))],
        "boxes_removed": [old_by_id[i] for i in sorted(set(old_by_id) - set(new_by_id))],
        "boxes_altered": altered,
        "arrows_added":   [new_by_key[k] for k in sorted(set(new_by_key) - set(old_by_key))],
        "arrows_removed": [old_by_key[k] for k in sorted(set(old_by_key) - set(new_by_key))],
    }


def is_empty(diff):
    """True when nothing at all changed."""
    return not any(diff.values())


def summary_lines(old, new, previous_date=None):
    """Build the change report as a list of lines.

    Returned rather than printed so the same text can go both to the terminal
    and onto the comparison page. old is None on a first run.
    """
    lines = ["WHAT CHANGED SINCE THE LAST RUN", "-" * 78]

    if old is None:
        lines.append("  No previous version to compare against -- this is the first run.")
        lines.append("  From now on, each run will list what it changed.")
        return lines

    diff = compare(old, new)

    if previous_date:
        lines.append("  Comparing against the version generated %s." % previous_date)
        lines.append("")

    if is_empty(diff):
        lines.append("  The pipeline is unchanged since the last run.")
        return lines

    def block(title, items, render):
        if items:
            lines.append("  %s (%d):" % (title, len(items)))
            for item in items:
                lines.append("    * " + render(item))
        else:
            lines.append("  %s: none" % title)

    block("Boxes added", diff["boxes_added"],
          lambda n: "%-18s %s" % (n["id"], _describe_node(n)))
    block("Boxes removed", diff["boxes_removed"],
          lambda n: "%-18s %s" % (n["id"], _describe_node(n)))

    if diff["boxes_altered"]:
        lines.append("  Boxes changed (%d):" % len(diff["boxes_altered"]))
        for node_id, field, before, after in diff["boxes_altered"]:
            lines.append("    * %-18s %s: %r -> %r"
                         % (node_id, field,
                            _flatten(before), _flatten(after)))
    else:
        lines.append("  Boxes changed: none")

    lines.append("")
    block("Arrows added", diff["arrows_added"],
          lambda e: "%-18s -> %-18s %s"
                    % (e["from"], e["to"], _describe_edge(e)))
    block("Arrows removed", diff["arrows_removed"],
          lambda e: "%-18s -> %-18s %s"
                    % (e["from"], e["to"], _describe_edge(e)))

    return lines


def _flatten(value):
    """Put a two-line box label on one line, so the before/after fits a row."""
    if isinstance(value, str):
        return value.replace("\n", " / ")
    return value


def print_summary(old, new, previous_date=None):
    """Print the change report, and return the lines for reuse on the page."""
    lines = summary_lines(old, new, previous_date)
    print("")
    for line in lines:
        print(line)
    return lines
