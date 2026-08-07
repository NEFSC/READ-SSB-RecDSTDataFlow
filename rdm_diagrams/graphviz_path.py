"""
graphviz_path.py
================================================================================
Make sure Python can find the Graphviz drawing program.

Why this exists: the Graphviz installer does not always tick the "add to PATH"
box, and when it doesn't, the diagram scripts fail with a confusing
"failed to execute 'dot'" error even though Graphviz IS installed. Rather than
make you fix your system settings, we check the handful of places the installer
normally puts it and add whichever ones exist, for this run only. This changes
nothing permanently on your computer.

This used to live inside the comprehensive-diagram script, and the other two
diagrams got it only as a side effect of importing that script. That was
fragile, and it stopped working the moment the diagrams were decoupled from
each other -- so it lives on its own here and all three call it.
================================================================================
"""

import os


_LIKELY_GRAPHVIZ_FOLDERS = [
    r"C:\Program Files\Graphviz\bin",
    r"C:\Program Files (x86)\Graphviz\bin",
    "/opt/homebrew/bin",   # Mac, Apple Silicon
    "/usr/local/bin",      # Mac, Intel
    "/usr/bin",            # Linux
]


def ensure_on_path():
    """Prepend every likely Graphviz folder that exists to PATH, for this run only."""
    for folder in _LIKELY_GRAPHVIZ_FOLDERS:
        if os.path.isdir(folder):
            os.environ["PATH"] = folder + os.pathsep + os.environ.get("PATH", "")
