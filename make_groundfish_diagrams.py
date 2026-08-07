"""make_groundfish_diagrams.py

Rebuilds all three GroundfishRDM pipeline diagrams from the groundfishRDM
source code. Double-click this file, or run:
    python make_groundfish_diagrams.py

Output lands in output/groundfish/.

See README.md for what the three diagrams are and how to add a project, and
SETUP_INSTRUCTIONS.md if this is your first time running Python.
"""

import os
import sys

# Run from anywhere -- a double-click starts in an unpredictable folder, and
# without this the "import rdm_diagrams" below would fail.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rdm_diagrams import main
from projects import groundfish

if __name__ == "__main__":
    sys.exit(main(groundfish.PROJECT))
