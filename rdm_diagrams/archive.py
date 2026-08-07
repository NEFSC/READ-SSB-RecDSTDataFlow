"""
archive.py
================================================================================
WHAT THIS FILE IS
--------------------------------------------------------------------------------
Keeps the PREVIOUS version of each picture, so a new one can be compared against
it instead of silently replacing it.

Every run redraws all three diagrams from scratch, which is what stops them
going stale -- but it also means the old picture is gone the moment the new one
is written. This module reads the old files into memory before anything
overwrites them, and afterwards writes a dated copy of any picture that actually
changed.

The archived files land in output/<project>/archive/ with the date appended:

    GroundfishRDM_simple_pipeline_diagram_2026-07-19_2127.png

The date is when that picture was GENERATED, not when it was archived -- it is
taken from the file's own timestamp. Sorting the folder by name therefore groups
each diagram together in date order, so you can see one picture's history at a
glance.

Nothing is ever deleted from the archive. If it grows unwieldy, delete versions
by hand.

--------------------------------------------------------------------------------
WHY ONLY THE PNG IS COMPARED
--------------------------------------------------------------------------------
Graphviz writes a byte-identical PNG when it is given a byte-identical graph:
there is no timestamp inside the file, so "the bytes differ" means "the picture
differs". That makes the comparison exact, and it is why re-running five times
without changing anything leaves one archived version rather than five copies of
the same image.

The SVG cannot be used this way. Two runs of identical code produce SVGs that
differ on ~136 lines, because the edge id numbers (edge32, edge88, ...) follow
the order the arrows happened to be created in, and that order comes from
iterating a Python set -- which varies from run to run. The picture is identical;
only the internal numbering moves. So the PNG decides whether anything changed,
and the SVG is archived alongside it whenever the PNG says yes.

--------------------------------------------------------------------------------
THE ORDER THINGS HAVE TO HAPPEN IN
--------------------------------------------------------------------------------
Rendering overwrites the pictures, and the extractor overwrites the pipeline
description, so BOTH have to be captured before either of those runs. Hence
snapshot_previous() is called first, holds the old bytes in memory (a few
megabytes), and archive_changed() writes them out at the end once we know what
changed. Nothing is written and then deleted, so an interrupted run cannot leave
a stray file behind.
================================================================================
"""

import datetime
import os


# The two files written for each diagram. The PNG decides whether the picture
# changed; the SVG comes along for the ride.
EXTENSIONS = ("png", "svg")


def stamp(when):
    """Format a timestamp for a filename: 2026-07-19_2127."""
    return datetime.datetime.fromtimestamp(when).strftime("%Y-%m-%d_%H%M")


def human(when):
    """Format a timestamp for reading: 2026-07-19 21:27."""
    return datetime.datetime.fromtimestamp(when).strftime("%Y-%m-%d %H:%M")


def _archived_path(project, filename, when):
    """Where one archived file goes, avoiding a collision within the same minute.

    Two runs that both change the picture inside one minute would otherwise
    produce the same name and the second would overwrite the first. Rare, but it
    happens while iterating -- so the seconds get appended if the minute-level
    name is already taken.
    """
    stem, ext = os.path.splitext(filename)
    base = os.path.join(project.archive_dir, "%s_%s%s" % (stem, stamp(when), ext))
    if not os.path.exists(base):
        return base
    precise = datetime.datetime.fromtimestamp(when).strftime("%Y-%m-%d_%H%M%S")
    return os.path.join(project.archive_dir, "%s_%s%s" % (stem, precise, ext))


def _read(path):
    """Return (bytes, mtime) for a file, or None if it is not there."""
    if not os.path.isfile(path):
        return None
    with open(path, "rb") as fh:
        return fh.read(), os.path.getmtime(path)


def snapshot_previous(project, files):
    """Read the current pictures into memory BEFORE they are overwritten.

    files maps each diagram about to be drawn to its filename stem, e.g.
    {"simple": "simple_pipeline_diagram"} -- so a run limited with --only=simple
    does not archive the other two. The stems come from each renderer's
    DIAGRAM_FILE, so there is no second copy of the names to keep in step.

    Returns {diagram name: {extension: (bytes, mtime)}}, holding only the files
    that actually exist. On a first run that is an empty dictionary.
    """
    snapshot = {}
    for name, stem in files.items():
        found = {}
        for ext in EXTENSIONS:
            existing = _read(project.output_base(stem) + "." + ext)
            if existing:
                found[ext] = existing
        if found:
            snapshot[name] = found
    return snapshot


def snapshot_data_module(project):
    """Read the current pipeline description before the extractor rewrites it."""
    return _read(project.data_module)


def _write(path, blob, when):
    """Write an archived copy and give it back the timestamp it had.

    Restoring the timestamp matters because the date is also in the filename:
    without this the file would claim, in Explorer, to have been created today
    while its name says otherwise.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(blob)
    os.utime(path, (when, when))


def archive_changed(project, snapshot, data_snapshot, files):
    """Archive the previous version of every picture whose PNG changed.

    Compares each freshly drawn PNG against the bytes captured before the run.
    Returns the list of diagram names that changed, so the caller can report it.
    """
    changed = []
    for name, previous in sorted(snapshot.items()):
        if "png" not in previous:
            continue          # nothing to compare against
        old_bytes, _old_when = previous["png"]
        current = _read(project.output_base(files[name]) + ".png")
        if current is None or current[0] == old_bytes:
            continue          # not redrawn this run, or redrawn identically
        changed.append(name)

    if not changed:
        return []

    for name in changed:
        for ext, (blob, when) in sorted(snapshot[name].items()):
            filename = project.output_name(files[name], ext)
            _write(_archived_path(project, filename, when), blob, when)

    # The pipeline description is archived once, alongside whichever pictures
    # changed -- it is the thing the written change report is diffed from, so it
    # has to stay in step with the images it produced.
    if data_snapshot:
        blob, when = data_snapshot
        _write(_archived_path(project, "pipeline_data_generated.py", when),
               blob, when)

    return changed


def latest_archived(project, stem, ext="png"):
    """Return the filename of the most recently archived copy of one diagram.

    Returns None when that diagram has never been archived. The filenames carry
    a zero-padded date, so the newest is simply the last one alphabetically --
    no need to read timestamps off disk.
    """
    if not os.path.isdir(project.archive_dir):
        return None
    prefix = project.output_prefix + stem + "_"
    suffix = "." + ext
    matches = sorted(f for f in os.listdir(project.archive_dir)
                     if f.startswith(prefix) and f.endswith(suffix))
    return matches[-1] if matches else None


def date_from_archived(filename):
    """Pull the date back out of an archived filename, for display.

    'GroundfishRDM_simple_pipeline_diagram_2026-07-19_2127.png'
        -> '2026-07-19 21:27'
    """
    stem = os.path.splitext(filename)[0]
    tail = stem.rsplit("_", 2)[-2:]          # ['2026-07-19', '2127'] or [..., '212700']
    if len(tail) != 2 or len(tail[0]) != 10:
        return "unknown date"
    day, clock = tail
    if len(clock) >= 4:
        return "%s %s:%s" % (day, clock[:2], clock[2:4])
    return day
