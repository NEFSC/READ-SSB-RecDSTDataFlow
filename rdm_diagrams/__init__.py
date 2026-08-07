"""
rdm_diagrams
================================================================================
The shared diagram toolchain. One copy of the code, one small settings record
per project (see projects/), and one thin wrapper script per project.

The only thing most people need from this package is run():

    from rdm_diagrams import run
    from projects import fluke
    run(fluke.PROJECT)

which reads the project's source code, writes its pipeline description, and
draws the three pictures into output/<project key>/.

--------------------------------------------------------------------------------
WHY IT IS SHAPED LIKE THIS
--------------------------------------------------------------------------------
There used to be two hand-maintained copies of this toolchain, one per project,
identical apart from name strings and the curation list. Every fix had to be
made twice, and one round of fixes that landed in only one copy left the other
reading the wrong folder for weeks. Everything project-specific now lives in
projects/<name>.py; nothing in this package names a project.
================================================================================
"""

import importlib.util
import os
import sys

from . import archive
from . import changes
from . import compare_page
from . import extract
from . import render_dataflow
from . import render_simple
from . import render_data


# The three pictures, in the order run() draws them. The key is what you pass
# to run(only=...) to draw just one of them.
RENDERERS = {
    "comprehensive": render_dataflow,
    "simple": render_simple,
    "data": render_data,
}

# Which drawing programs exist and which one is used when nobody says. Defined
# in config.py (the renderers need it too, and they are imported below, so
# defining it here would be a circular import); re-exported so that
# `from rdm_diagrams import DEFAULT_ENGINE` keeps working.
from .config import DEFAULT_ENGINE, ENGINES   # noqa: F401


def diagram_files(names):
    """Map each diagram name to the filename stem its renderer writes.

    Each renderer owns its own filename (its DIAGRAM_FILE), so archiving and the
    comparison page can find those files without a second list of names that
    could drift out of step with the renderers.
    """
    return {name: RENDERERS[name].DIAGRAM_FILE for name in names}


def load_pipeline_data(project):
    """Read back the pipeline description the extractor wrote.

    Loaded by file path rather than by name: it lives in the project's own
    output folder, not next to this code, so a plain 'import' would either miss
    it or -- worse, with two projects -- find the other project's copy.
    """
    path = project.data_module
    spec = importlib.util.spec_from_file_location(
        "pipeline_data_generated_" + project.key, path)
    module = importlib.util.module_from_spec(spec)

    # Loading a module normally leaves a __pycache__ folder beside it. Here
    # that would be inside the output folder, next to the pictures, where it
    # looks like something the run produced. Nothing needs the speed-up, so
    # turn it off for the load.
    was_off = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = was_off

    return module.STAGES, module.nodes, module.edges


def run(project, extract_first=True, only=None, check=False, keep_previous=True,
        engine=DEFAULT_ENGINE):
    """Extract the pipeline from the source code, then draw the diagrams.

    project        a Project record, e.g. projects.fluke.PROJECT
    extract_first  re-read the source code first (the normal case). False
                   redraws from the pipeline description already on disk.
    only           draw just one diagram: "comprehensive", "simple" or "data".
                   None draws all three.
    check          print the comparison report instead of drawing anything.
    keep_previous  archive the previous version of any picture that changed,
                   and write the comparison page. False skips both.
    engine         which drawing program to use: "graphviz" (the default) or
                   "mermaid". Both write the same filenames, so everything
                   downstream -- archiving, the comparison page -- is unaffected
                   by the choice. See MERMAID_MIGRATION_PLAN.md.

    Returns 0 when everything worked, 1 when it did not -- so a wrapper script
    can pass that straight to sys.exit().
    """
    problem = project.problem()
    if problem:
        print("")
        print(problem)
        return 1

    if engine not in ENGINES:
        print("")
        print("There is no drawing engine called %r. Choose one of: %s"
              % (engine, ", ".join(ENGINES)))
        return 1

    # Checked before anything is drawn rather than at the first render: a
    # missing renderer should be one clear message at the start, not a failure
    # two diagrams into a run that has already overwritten a picture.
    if not check and engine == "mermaid":
        from . import mermaid_path
        mermaid_problem = mermaid_path.problem()
        if mermaid_problem:
            print("")
            print(mermaid_problem)
            return 1

    if check:
        stages, nodes, edges, report = extract.build(project)
        extract.run_check(stages, nodes, edges, report, project)
        return 0

    wanted = [only] if only else list(RENDERERS)
    for name in wanted:
        if name not in RENDERERS:
            print("")
            print("There is no diagram called %r. Choose one of: %s"
                  % (name, ", ".join(RENDERERS)))
            return 1

    # Capture the previous version FIRST. Both the extractor and the renderers
    # overwrite in place, so a moment later there would be nothing left to
    # compare against. Held in memory (a few MB) and written out at the end,
    # only for the pictures that actually changed -- so an interrupted run
    # cannot leave a half-made archive behind.
    files = diagram_files(wanted)
    previous = archive.snapshot_previous(project, files) if keep_previous else {}
    previous_data = archive.snapshot_data_module(project) if keep_previous else None

    if extract_first:
        print("")
        print("Reading the %s source code..." % project.display_name)
        stages, nodes, edges, report = extract.build(project)
        extract.write_module(stages, nodes, edges, project.data_module, project)
        print("")
        print("Done. Read the %s code and wrote:" % project.display_name)
        print("    " + project.data_module)
        print("")
        print("It contains %d boxes and %d arrows." % (len(nodes), len(edges)))
        extract.print_report(report, project)
    elif not os.path.isfile(project.data_module):
        print("")
        print("There is no pipeline description to draw from yet:")
        print("    " + project.data_module)
        print("Run without extract_first=False to create it.")
        return 1

    # Read the description back off disk rather than using the lists still in
    # memory. It costs nothing, and it means the pictures are drawn from the
    # same bytes a reader would open -- if the written file were ever wrong,
    # the diagrams would show it rather than hide it.
    stages, nodes, edges = load_pipeline_data(project)

    for name in wanted:
        RENDERERS[name].render(project, stages, nodes, edges, engine=engine)

    if keep_previous:
        _keep_previous_versions(project, previous, previous_data,
                                (stages, nodes, edges), files)

    print("")
    print("All output is in:")
    print("    " + project.output_dir)
    print("")
    print("If the pipeline changes, just run this script again. The pictures are")
    print("redrawn from the source code every time, so they cannot go stale. Do")
    print("not edit pipeline_data_generated.py by hand -- it is overwritten on")
    print("every run.")
    return 0


def _keep_previous_versions(project, previous, previous_data, current_data, files):
    """Archive what changed, say what changed, and write the comparison page."""
    changed = archive.archive_changed(project, previous, previous_data, files)

    # The written summary is diffed from the pipeline description captured
    # before the extractor overwrote it -- not from the archive, which may be
    # older if this run changed nothing.
    old = changes.parse(previous_data[0]) if previous_data else None
    previous_date = archive.human(previous_data[1]) if previous_data else None
    summary = changes.print_summary(old, current_data, previous_date)

    print("")
    if changed:
        print("The previous version of %s changed, so it was archived to:"
              % _and_list(changed))
        print("    " + project.archive_dir)
    else:
        print("The pictures are identical to the previous run, so nothing was")
        print("archived. (The archive only keeps versions that actually differ.)")

    # Every diagram gets a tab, not just the ones this run drew: the archive
    # may hold a previous version of the others worth looking at.
    path = compare_page.write(project, diagram_files(list(RENDERERS)), summary)
    print("")
    print("To see previous and current side by side, open:")
    print("    " + path)


def _and_list(names):
    """['a', 'b', 'c'] -> 'a, b and c'."""
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " and " + names[-1]


def main(project, argv=None):
    """Command-line front end for a project's wrapper script.

    Supported flags:
        --check         print the comparison report, draw nothing
        --no-extract    redraw from the existing pipeline description
        --only=NAME     draw one diagram: comprehensive, simple or data
        --no-archive    do not archive the previous pictures, and do not
                        write compare.html
        --engine=NAME   which drawing program to use: graphviz (default)
                        or mermaid
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    only = None
    engine = DEFAULT_ENGINE
    for arg in argv:
        if arg.startswith("--only="):
            only = arg.split("=", 1)[1]
        elif arg.startswith("--engine="):
            engine = arg.split("=", 1)[1]
    return run(project,
               extract_first="--no-extract" not in argv,
               only=only,
               check="--check" in argv,
               keep_previous="--no-archive" not in argv,
               engine=engine)
