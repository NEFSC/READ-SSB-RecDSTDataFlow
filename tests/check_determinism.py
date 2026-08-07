"""
check_determinism.py
================================================================================
Draw the same diagram three times and check the files come out byte-identical.

WHY THIS MATTERS MORE THAN IT SOUNDS
--------------------------------------------------------------------------------
archive.py decides whether to keep a copy of the previous picture by comparing
the PNG's BYTES. If a renderer produces a slightly different file every time --
different generated element ids, a timestamp, a font rasterised a hair
differently -- then:

  * every run archives a "changed" picture, so the archive fills with
    identical images, and
  * compare.html reports a difference on every run, which trains everyone to
    ignore it.

Graphviz is deterministic, so this has never been a question. Mermaid draws
through a headless browser, which is exactly the kind of pipeline where it
might not be -- so it has to be checked before the engine is trusted, not
after someone notices the archive growing.

EACH RUN IS A SEPARATE PROCESS, AND THAT IS THE WHOLE POINT
--------------------------------------------------------------------------------
An earlier version of this file drew all three copies inside one Python
process and declared everything deterministic. It was wrong, and it was wrong
in the exact way that matters: Python randomises the iteration order of a set
of strings ONCE PER PROCESS. Anything that iterates a set therefore gives the
same answer all day inside one process and a different answer tomorrow
morning -- which is precisely the "identical run, different file" case
archive.py cares about. Real runs are separate processes, so the test has to
be too.

WHAT IT DOES NOT TOUCH
--------------------------------------------------------------------------------
Everything is rendered into a temporary folder and deleted afterwards. This
never writes to output/, never archives anything, and never runs the extractor.

USAGE
--------------------------------------------------------------------------------
    py tests/check_determinism.py groundfish mermaid
    py tests/check_determinism.py groundfish graphviz
    py tests/check_determinism.py fluke mermaid comprehensive

Exit code 0 means every run produced identical bytes.
================================================================================
"""

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
DIAGRAMS_DIR = os.path.dirname(HERE)
sys.path.insert(0, DIAGRAMS_DIR)

DIAGRAMS = ("comprehensive", "simple", "data")
RUNS = 3


def digest(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def render_once(project, diagram, stages, nodes, edges, engine, base):
    """Draw one diagram to an arbitrary base path, bypassing output/.

    The renderers write to project.output_base(...), which is fixed. Rather
    than add a parameter to every renderer purely for this test, the build
    step and the write step are called separately -- which is possible because
    both engines keep those two apart.
    """
    from rdm_diagrams import RENDERERS, mermaid
    module = RENDERERS[diagram]

    if engine == "mermaid":
        if diagram == "comprehensive":
            text = module.build_mermaid(project, stages, nodes, edges)
        elif diagram == "simple":
            kept, simple_edges = module.simplify(nodes, edges)
            text = module.build_mermaid(project, stages, kept, simple_edges)
        else:
            text = module.build_mermaid(project, stages,
                                        module.fold_scripts(nodes, edges))
        return mermaid.render_text(text, base, description=diagram)

    from rdm_diagrams.graphviz_path import ensure_on_path
    ensure_on_path()
    if diagram == "comprehensive":
        dot = module.build_graph(project, stages, nodes, edges)
    elif diagram == "simple":
        kept, simple_edges = module.simplify(nodes, edges)
        dot = module.build_graph(project, stages, kept, simple_edges)
    else:
        dot = module.build_graph(project, stages,
                                 module.fold_scripts(nodes, edges))
    return (dot.render(filename=base, format="png", cleanup=True),
            dot.render(filename=base, format="svg", cleanup=True))


def check(key, diagram, engine):
    """True if RUNS renders of one diagram are byte-identical.

    Each render is a fresh subprocess (see the docstring): same interpreter,
    same arguments, nothing shared but the files on disk.
    """
    workdir = tempfile.mkdtemp(prefix="rdm_determinism_")
    try:
        digests = []
        for run in range(RUNS):
            base = os.path.join(workdir, "%s_%d" % (diagram, run))
            proc = subprocess.run(
                [sys.executable, os.path.abspath(__file__), "--render",
                 key, engine, diagram, base],
                capture_output=True, text=True)
            if proc.returncode != 0:
                print("    run %d FAILED to render:" % (run + 1))
                print("    " + (proc.stdout + proc.stderr).strip()[:1200]
                      .replace("\n", "\n    "))
                return False
            png_path, svg_path = base + ".png", base + ".svg"
            digests.append((digest(png_path), digest(svg_path)))
            print("    run %d: png %s...  svg %s..."
                  % (run + 1, digests[-1][0][:12], digests[-1][1][:12]))

        png_same = len({d[0] for d in digests}) == 1
        svg_same = len({d[1] for d in digests}) == 1
        if png_same and svg_same:
            print("    OK -- all %d runs identical" % RUNS)
            return True

        print("    NOT DETERMINISTIC: %s differ between runs."
              % (" and ".join(x for x, same in (("PNG", png_same),
                                                ("SVG", svg_same)) if not same)))
        print("    archive.py compares PNG bytes, so every run archives a new")
        print("    copy and compare.html claims a change that isn't one.")
        print("")
        print("    Re-run with PYTHONHASHSEED=0 set. If it passes with the seed")
        print("    fixed, the cause is code iterating a set (or a dict keyed off")
        print("    one) somewhere in the build: Python randomises that order per")
        print("    process, the elements come out in a different order, and the")
        print("    layout engine draws a different picture from the same data.")
        print("    Sorting at the point of iteration is the fix -- but it changes")
        print("    the drawing, so it is a deliberate change, not a tidy-up.")
        print("    See MERMAID_MIGRATION_PLAN.md, Phase 3.")
        return False
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def render_worker(key, engine, diagram, base):
    """One render, in this process. Invoked as a subprocess by check()."""
    import importlib
    project = importlib.import_module("projects." + key).PROJECT
    from rdm_diagrams import load_pipeline_data
    stages, nodes, edges = load_pipeline_data(project)
    render_once(project, diagram, stages, nodes, edges, engine, base)
    return 0


def main(argv):
    if argv and argv[0] == "--render":
        return render_worker(*argv[1:])

    if not argv:
        print(__doc__.strip().split("USAGE")[1].strip())
        return 1

    key = argv[0]
    engine = argv[1] if len(argv) > 1 else "mermaid"
    wanted = [a for a in argv[2:] if not a.startswith("-")] or list(DIAGRAMS)

    print("")
    print("Drawing each diagram %d times (one process each) with %s "
          "and comparing the bytes." % (RUNS, engine))
    ok = True
    for diagram in wanted:
        print("")
        print("  %s:" % diagram)
        if not check(key, diagram, engine):
            ok = False

    print("")
    print("Determinism: %s" % ("OK" if ok else "FAILED -- see above"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
