"""
mermaid_path.py
================================================================================
Make sure Python can find the Mermaid drawing program, and say something useful
when it cannot.

Same job as graphviz_path.py, for the other engine. `mmdc` is the Mermaid
command-line renderer; it is installed with npm, and npm's global bin folder is
frequently not on PATH on Windows -- exactly the failure graphviz_path.py exists
to absorb, so it is absorbed the same way here.

Two things this checks that Graphviz has no equivalent of:

  * that `mmdc` runs at all, and
  * that the ELK layout plugin is installed alongside it.

The second matters more than it looks. If `layout: elk` cannot be resolved,
Mermaid does not fail -- it silently falls back to its default dagre engine and
draws a picture. Dagre puts the stages in a different order, so the result would
be a WRONG diagram rather than a missing one, and nothing on screen would say
so. Checking here turns that into an install message; render_mermaid.py checks
the rendered file as well, in case a future version changes how it resolves.
================================================================================
"""

import os
import shutil
import subprocess


# Where npm puts global command-line tools when the installer has not put them
# on PATH. The Windows entry is the one that actually bites.
_LIKELY_NPM_BIN_FOLDERS = [
    os.path.join(os.environ.get("APPDATA", ""), "npm"),          # Windows
    os.path.expanduser("~/.npm-global/bin"),                     # npm prefix override
    "/opt/homebrew/bin",                                         # Mac, Apple Silicon
    "/usr/local/bin",                                            # Mac, Intel / Linux
]

INSTALL_HINT = (
    "Mermaid's renderer was not found. To install it (once, per machine):\n"
    "\n"
    "    npm install -g @mermaid-js/mermaid-cli\n"
    "\n"
    "That needs Node.js (https://nodejs.org), and it downloads a private copy\n"
    "of the Chrome browser that Mermaid draws with -- roughly 150 MB, so give\n"
    "it a few minutes on a slow connection.\n"
    "\n"
    "If it IS installed and you are still seeing this, npm's folder is not on\n"
    "your PATH. Run `npm root -g` to find it and add the folder above it."
)


def ensure_on_path():
    """Prepend every likely npm global-bin folder that exists to PATH.

    For this run only -- nothing on the machine is changed permanently.
    """
    for folder in _LIKELY_NPM_BIN_FOLDERS:
        if folder and os.path.isdir(folder):
            os.environ["PATH"] = folder + os.pathsep + os.environ.get("PATH", "")


def find_mmdc():
    """Full path to the `mmdc` executable, or None."""
    ensure_on_path()
    # shutil.which honours PATHEXT on Windows, which matters: the thing that is
    # actually executable there is `mmdc.cmd`, not a bare `mmdc`.
    return shutil.which("mmdc")


def elk_plugin_folder():
    """Folder of the installed `@mermaid-js/layout-elk`, or None.

    Looked up through `npm root -g` rather than by guessing paths, because the
    plugin can be either its own global package or -- as it currently is --
    vendored inside mermaid-cli's own node_modules. Both count as installed.
    """
    try:
        root = subprocess.run(["npm", "root", "-g"], capture_output=True,
                              text=True, timeout=60,
                              shell=(os.name == "nt")).stdout.strip()
    except Exception:
        return None
    if not root:
        return None
    candidates = [
        os.path.join(root, "@mermaid-js", "layout-elk"),
        os.path.join(root, "@mermaid-js", "mermaid-cli", "node_modules",
                     "@mermaid-js", "layout-elk"),
    ]
    for path in candidates:
        if os.path.isdir(path):
            return path
    return None


def problem():
    """Plain-language description of the first thing that is wrong, or None.

    Mirrors Project.problem(): callers print it and stop, rather than letting a
    missing tool surface as a traceback three frames deep.
    """
    if find_mmdc() is None:
        return INSTALL_HINT
    if elk_plugin_folder() is None:
        return (
            "Mermaid's renderer is installed, but its ELK layout plugin is not.\n"
            "Without ELK, Mermaid would silently draw the diagram with its\n"
            "default engine, which puts the pipeline stages in the wrong order --\n"
            "a wrong picture rather than an error. To install it:\n"
            "\n"
            "    npm install -g @mermaid-js/layout-elk\n"
            "\n"
            "(Recent versions of @mermaid-js/mermaid-cli already include it. If\n"
            "you have just upgraded, try reinstalling mermaid-cli first.)"
        )
    return None
