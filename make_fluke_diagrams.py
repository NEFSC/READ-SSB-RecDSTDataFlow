"""make_fluke_diagrams.py

Rebuilds all three flukeRDM pipeline diagrams from the flukeRDM source code.
Double-click this file, or run:  python make_fluke_diagrams.py

Output lands in output/fluke/.

See README.md for what the three diagrams are and how to add a project, and
SETUP_INSTRUCTIONS.md if this is your first time running Python.
"""

import os
import sys

# Run from anywhere -- a double-click starts in an unpredictable folder, and
# without this the "import rdm_diagrams" below would fail.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rdm_diagrams import main
from projects import fluke

if __name__ == "__main__":
    sys.exit(main(fluke.PROJECT))
