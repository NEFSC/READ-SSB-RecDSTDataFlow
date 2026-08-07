# What is this repository

This repository contains python scripts create flow diagrams by parsing the headers in the two recDSTs.  

# Before you start

The code assumes that you have put this repository "next to" the groundfishRDM and fluke RDM repositories. 
It also assumes your repository names are "groundfishRDM" and "flukeRDM".

```
mega_folder/
├── groundfishRDM/ 
├── flukeRDM/  
├── recDST_DataFlow/          #This repository.
├── AnotherRepo/              #this folder is not scanned.

```

# Pipeline diagrams

One toolchain that draws pipeline diagrams for both RDM projects, and for any
project added later.

If you have never run Python before, read `../SETUP_INSTRUCTIONS.md` first —
it walks through installing Python and Graphviz. Everything below assumes that
is already done.

---

## Drawing the diagrams

Double-click the file for the project you want, or run it from a terminal:

```
python make_fluke_diagrams.py
python make_groundfish_diagrams.py
```

Each one reads its project's source code from scratch, works out the pipeline,
and writes six pictures plus a description file into `output/fluke/` or
`output/groundfish/`. It takes a few seconds. There is nothing to run first
and nothing to run afterwards.

Because the pipeline is re-read from the code on every run, the pictures cannot
quietly go out of date. If the diagram is wrong, the code changed — run it
again.

### Options

| Flag | What it does |
|---|---|
| *(none)* | Read the code, then draw all three diagrams. This is the normal case. |
| `--check` | Print the comparison and drift report. Draws nothing, writes nothing. |
| `--only=simple` | Draw just one diagram: `comprehensive`, `simple` or `data`. |
| `--no-extract` | Redraw from the description already in `output/`, without re-reading the source code. |
| `--no-archive` | Skip keeping the previous version, and do not write `compare.html`. |
| `--engine=graphviz` | Draw with Graphviz instead of Mermaid. See below. |

---

## Two drawing engines

The same three diagrams can be drawn by either of two programs. They read the
same lists and show the same boxes and arrows; what differs is where things are
placed on the page.

```
python make_groundfish_diagrams.py                     # Mermaid + ELK (default)
python make_groundfish_diagrams.py --engine=graphviz   # Graphviz
```

**Mermaid + ELK is the default.** It draws the comprehensive diagram with about
a third fewer line crossings (414 → 281 on Groundfish, measured with
`tests/check_layout.py`). It needs Node.js and one npm package:

```
npm install -g @mermaid-js/mermaid-cli
```

That download includes a private copy of the Chrome browser Mermaid draws with
(~150 MB, so allow a few minutes). If it is missing, the run stops with an
install message rather than a stack trace.

**Graphviz** is still here, one flag away, and needs no Node. Use it when:

* **You need the simplified diagram to fit a slide.** The Graphviz version
  scales the finished drawing down to a 16:9 page; Mermaid has no equivalent,
  so its PNG comes out at natural size. It is also the one diagram where
  Graphviz currently draws fewer crossings on Groundfish (196 vs 257).
* **You are on a machine without Node**, or Node is blocked.

Both engines write the same filenames, so archiving and `compare.html` work the
same way whichever you use — but they will treat a switch of engines as "the
picture changed", because it did. Expect one archived version the first time
you run after this change.

One known gap in the Mermaid version: **the stage order is close but not
exact** (on Groundfish the calibration panel is drawn above the stage that
feeds it). Getting it exact needs a handful of arrows drawn in reverse, and
Mermaid cannot draw a reversed arrow without also reversing its arrowhead —
which would state the wrong direction. The options are written up in
`../MERMAID_MIGRATION_PLAN.md` under "Open items".

To check what an engine actually produced, see `tests/` below.

---

## Comparing against the previous version

Every run replaces the pictures. So that the old ones are not simply lost, each
run also:

**1. Archives the previous version of any picture that changed.** Into
`output/<project>/archive/`, with the date it was generated appended to the
name:

```
GroundfishRDM_simple_pipeline_diagram_2026-07-19_2127.png
GroundfishRDM_simple_pipeline_diagram_2026-07-20_0915.png
```

Sorting that folder by name therefore groups each diagram together in date
order, so you can follow one picture's history down the list.

Only versions that **actually differ** are kept: the new PNG is compared byte
for byte against the old one, so re-running five times without changing
anything leaves one archived version rather than five copies of the same
image. Nothing is ever deleted from the archive — if it grows unwieldy, delete
old versions by hand.

**2. Says in words what changed.** Added and removed boxes and arrows, named:

```
WHAT CHANGED SINCE THE LAST RUN
------------------------------------------------------------------------------
  Boxes added (1):
    * new_helper         new_helper.do              (calib panel)
  Arrows added (1):
    * model_wrapper   -> new_helper        calls, if do_helper = 1 by default
```

This is the part worth reading. The comprehensive diagram is about 5900 pixels
wide with 80-odd boxes, so a single new arrow in it is invisible unless you
already know where to look — but the description it is drawn from is an exact
list, so the difference can be stated precisely.

**3. Writes `output/<project>/compare.html`.** Double-click it. Previous and
current, with three ways to compare:

| Mode | Best for |
|---|---|
| **Swipe** | "Has this region changed at all?" Drag the divider across, or use the arrow keys. |
| **Side by side** | Changes of overall shape. Zoom in — at "Fit" a 5900-pixel diagram is squeezed to about 13% and the fine detail washes out. |
| **Blink** | Finding a small change in a large picture. It flips between the two versions in place: anything that moved flickers, everything else sits still. |

The page refers to the PNGs sitting beside it rather than embedding them, so it
stays small — but that means moving `compare.html` somewhere else on its own
will break the pictures.

### Why the PNG decides, and not the SVG

Graphviz writes a byte-identical PNG when given a byte-identical graph, and
embeds no timestamp, so "the bytes differ" means "the picture differs".

The SVG cannot be used this way. Two runs of *identical* code produce SVGs
differing on about 136 lines, because the edge id numbers (`edge32`, `edge88`,
…) follow the order the arrows happened to be created in, and that order comes
from iterating a Python set. The picture is identical; only the internal
numbering moves. So the PNG decides whether anything changed, and the SVG is
archived alongside it whenever the PNG says yes.

**Known exception: the simplified diagram.** For that one the set ordering
does not just move the numbering, it changes the drawing. `simplify()` builds
its bridged arrows by iterating a set of data-file ids, and Python shuffles
that order once per process, so two runs hand the layout engine the same
arrows in a different order and it draws them differently. Measured with
`tests/check_determinism.py`: the comprehensive and data diagrams are
byte-identical across runs, the simplified one is not — under **both** drawing
engines, for both projects. So the simplified diagram archives a new copy on
most runs even when nothing about the pipeline changed, and `compare.html`
reports a change that isn't one.

This is long-standing behaviour, not something the second engine introduced.
Setting `PYTHONHASHSEED=0` makes it deterministic again, which is how the
cause was confirmed. The proper fix is to sort at the point of iteration in
`render_simple.simplify()` — a one-line change, but one that alters every
future simplified diagram, so it is a deliberate decision rather than a
tidy-up, and it has not been made here.

---

## The three diagrams

Each answers a different question. All three are built from the same
description of the pipeline, so they can never disagree with each other.

| File | Question it answers |
|---|---|
| `<Prefix>comprehensive_pipeline_diagram` | "Where exactly did this number come from?" Every script and every data file. Big — open the SVG and zoom. |
| `<Prefix>simple_pipeline_diagram` | "Which script depends on which?" Data files folded away. Fits a slide. |
| `<Prefix>data_pipeline_diagram` | "What feeds into this file?" Scripts folded away, becoming labels on the arrows. |

Each is written twice: `.png` (an ordinary image, double-click to view) and
`.svg` (vector — stays sharp at any zoom, best for reading small text or
printing large).

---

## Adding a third project

Two files. Nothing in `rdm_diagrams/` changes.

**1. `projects/<name>.py`** — copy `projects/fluke.py` and edit the record at
the bottom:

```python
PROJECT = Project(
    key="bluefish",                    # the output subfolder name
    display_name="BluefishRDM",        # how it appears in titles and captions
    output_prefix="BluefishRDM_",      # goes on the front of the filenames
    repo=r"C:/path/to/bluefishRDM",
    curation=CURATION,
)
```

Then work through that file's `CURATION` dictionary, which is the copied
project's and will be wrong for yours. You do not have to get it right first
time: anything the extractor finds that `CURATION` has not been told about is
still drawn, and is also listed in the run report under "WHAT THE CODE CONTAINS
THAT THE CURATION LIST HAS NOT MET". Run it, read that list, and fill in the
entries it names.

**2. `make_<name>_diagrams.py`** — copy `make_fluke_diagrams.py` and change the
two occurrences of `fluke`.

That is the whole job. If you find yourself needing to edit anything in
`rdm_diagrams/` to make a new project work, that is a sign the thing you are
changing should have become a `Project` setting instead — say so rather than
special-casing it, because special-casing by project is exactly what this
layout exists to prevent.

---

## What is in here

| Path | What it is |
|---|---|
| `make_*_diagrams.py` | The double-clickable entry point, one per project. Four lines each. |
| `projects/*.py` | Everything specific to one project: where its code lives, what to call it, and its hand-maintained `CURATION` list. |
| `rdm_diagrams/config.py` | The `Project` record, and the defaults that are currently the same for every project. |
| `rdm_diagrams/extract.py` | Reads a project's `.do` and `.R` files and works out the boxes and arrows. The bulk of the toolchain. |
| `rdm_diagrams/render_dataflow.py` | Draws the comprehensive diagram. |
| `rdm_diagrams/render_simple.py` | Draws the simplified diagram. |
| `rdm_diagrams/render_data.py` | Draws the data-focused diagram. |
| `rdm_diagrams/graphviz_path.py` | Finds the Graphviz program when its installer did not add it to `PATH`. |
| `rdm_diagrams/mermaid.py` | The Mermaid engine: builds the diagram text and runs `mmdc` to turn it into pictures. |
| `rdm_diagrams/mermaid_path.py` | Finds `mmdc`, checks its ELK plugin is there, and explains how to install both if not. |
| `tests/check_layout.py` | Scores a drawn diagram: how many lines cross, and are the stages in declared order. Run it after a change to see whether the picture got better or worse instead of arguing about it. |
| `tests/check_determinism.py` | Draws the same diagram three times in three processes and checks the files come out identical — which is what archiving depends on. |
| `rdm_diagrams/layout.py` | Layout-only tricks shared by all three diagrams: pins stage panels into the declared order, and bundles a hub script's fan-out so it doesn't sweep across the whole page. |
| `rdm_diagrams/archive.py` | Keeps the previous version of each picture, and decides what changed. |
| `rdm_diagrams/changes.py` | Works out which boxes and arrows were added or removed. |
| `rdm_diagrams/compare_page.py` | Writes `compare.html`. |
| `output/<project>/` | The six pictures, `pipeline_data_generated.py`, and `compare.html`. |
| `output/<project>/archive/` | Previous versions, dated. Only appears once something has changed. |

`output/<project>/pipeline_data_generated.py` is machine-written and
overwritten on every run. It is kept as a readable file on purpose: it diffs
well, so you can see exactly what changed about the pipeline between two runs.
Do not edit it.

---

# NOAA Requirements
This repository is a scientific product and is not official communication of the National Oceanic and Atmospheric Administration, or the United States Department of Commerce. All NOAA GitHub project code is provided on an ‘as is’ basis and the user assumes responsibility for its use. Any claims against the Department of Commerce or Department of Commerce bureaus stemming from the use of this GitHub project will be governed by all applicable Federal law. Any reference to specific commercial products, processes, or services by service mark, trademark, manufacturer, or otherwise, does not constitute or imply their endorsement, recommendation or favoring by the Department of Commerce. The Department of Commerce seal and logo, or the seal and logo of a DOC bureau, shall not be used in any manner to imply endorsement of any commercial product or activity by DOC or the United States Government.”


1. who worked on this project:  Min-Yang Lee
1. when this project was created: August, 2026 
1. what the project does: Creates Data flow diagrams for groundfishRDM and flukeRDM
1. why the project is useful:  Helps people get oriented to the repos 
1. how users can get started with the project: Download and follow the readme
1. where users can get help with your project:  email me or open an issue
1. who maintains and contributes to the project. Min-Yang

# License file
See here for the [license file](License.txt)
