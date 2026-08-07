# How to Generate the Data Flow Diagrams

This guide assumes you have **never used Python or a terminal before**. Every
step is spelled out. Nothing here requires you to write or understand any code —
you are copying and pasting a couple of commands.

**This guide is for Windows.** Every command below is written for PowerShell.

You only do steps 1–4 **once, ever**. After that, generating fresh diagrams is
just the single command in step 5.

The examples below use **GroundfishRDM**. The flukeRDM diagrams work exactly the
same way — one command, `python make_fluke_diagrams.py`, and output in
`diagrams\output\fluke\` instead. Both projects are drawn by one shared set of
code in the `diagrams` folder; see `diagrams\README.md` for how that is laid out
and how to add a third project.

---

## What you'll end up with

**Three diagrams**, each saved in two formats, in `diagrams\output\groundfish\`.

Each one answers a different question, so pick by what you're trying to find out:

| If you want to know… | Use |
|---|---|
| "Where exactly did this number come from?" | Diagram 1 — comprehensive |
| "Which script depends on which?" | Diagram 2 — simple |
| "What feeds into this data file?" | Diagram 3 — data-focused |

### Diagram 1 — the detailed one

| File | What it's for |
|---|---|
| `GroundfishRDM_comprehensive_pipeline_diagram.png` | An ordinary image. Double-click to open it. |
| `GroundfishRDM_comprehensive_pipeline_diagram.svg` | The same picture in "vector" form — it stays perfectly sharp no matter how far you zoom in. Best for reading the small text or printing a large copy. |

Shows **everything**: every script in the GroundfishRDM pipeline, every data
file it reads and writes, the order things run in, and which steps are optional
because they sit behind an on/off switch. This is the one to use when you need
to trace where a particular number came from.

It is genuinely big — about 80 boxes. Don't try to read it at full-page zoom;
open the SVG and zoom in on the part you care about.

### Diagram 2 — the simplified one, for presentations

| File | What it's for |
|---|---|
| `GroundfishRDM_simple_pipeline_diagram.png` | Fits on one page or one slide. Drop this into a deck or an email. |
| `GroundfishRDM_simple_pipeline_diagram.svg` | Vector version, for printing a clean copy. |

Shows the **scripts only** — the ~40 data-file boxes are folded away, which is
what makes it fit on a page. Nothing is lost about *what depends on what*: if a
script wrote a file and another script read it, the arrow between those two
scripts is still drawn. You just don't see the file's name.

Use this one to show someone the shape of the pipeline; use Diagram 1 when you
need the detail.

### Diagram 3 — the data-focused one

| File | What it's for |
|---|---|
| `GroundfishRDM_data_pipeline_diagram.png` | Answering "what feeds into this file, and what gets made from it?" |
| `GroundfishRDM_data_pipeline_diagram.svg` | Vector version, for zooming and printing. |

This is the **mirror image of Diagram 2**. That one keeps the scripts and folds
away the data files; this one keeps the data files and folds away the scripts,
turning each script into a *label on an arrow*. So instead of

```
gulf_atl_2022.dta  →  [survey_trip_costs.do]  →  trip_costs.dta
```

you simply get

```
gulf_atl_2022.dta  ──survey_trip_costs.do──▶  trip_costs.dta
```

Two things are deliberately different about this diagram:

- **All toggles are assumed ON.** The other two draw optional steps as dashed
  arrows. Here everything is drawn as if switched on, so you see the complete
  set of data relationships that *can* exist. No dashes, no switch names.
- **Dead code is left out entirely** — not just faded. `MRIP_lists.do` writes
  the very same four files that `tidyup_mrip_data_fromR.do` writes, so drawing
  it would make that data look like it has two sources. It doesn't.

A few scripts read and write a lot of files at once — `compare_calibration_data_to_MRIP.do`
reads 5 and writes 4. Connecting every input to every output would mean 20
near-identical arrows, so those scripts are drawn as a small **boxed script
name** instead: everything flowing in is read, everything flowing out is
written. Simple scripts still get the plain labelled arrow shown above.

---

## Step 0 — Open a terminal

A "terminal" is a window where you type commands instead of clicking buttons.

Press the Windows key, type `powershell`, and press Enter. A dark blue or black
window opens with a blinking cursor. That's it.

Everything below gets typed into that window, one line at a time, pressing Enter
after each. Don't worry about breaking anything — none of these commands can
damage your files.
---

## Software needed

NEFSC users will need helpdesk to install Python and node.js.

Python
node.js
mermaid
GraphViz - optional

## Step 1 — Check whether Python is already installed

Type this and press Enter:

```
python --version
```

**If you see something like `Python 3.14.4`** (any version starting with 3.10 or
higher is fine), Python is installed. Skip to Step 2.

**If you see** `'python' is not recognized...` — Python isn't installed yet, or
it was installed without the PATH option. Do Step 1b.

### Step 1b — Install Python (only if the check above failed)

1. Go to <https://www.python.org/downloads/>
2. Click the big yellow **Download Python** button and run the file it downloads.
3. **️ Important, and easy to miss:** on the very first screen of the installer,
   tick the checkbox at the bottom that says **"Add Python to PATH"** *before*
   clicking Install. If you skip this, the terminal won't be able to find Python
   afterwards and every command below will fail with "not recognized".
4. When it finishes, **close your terminal window and open a new one** (it only
   notices the new installation on startup), then re-run `python --version` to
   confirm.

---

## Step 2 — Install Mermaid, the drawing program the diagrams now use

The diagrams are drawn by Mermaid by default. Graphviz can be used for one
of the three diagrams (see Step 7b)

Mermaid runs on Node.js, which is a separate install:

1. Download Node.js from <https://nodejs.org> — take the button labelled
   **LTS** (the stable one), and click through the installer accepting the
   defaults.  
2. **Close your terminal and open a fresh one.** The installer adds Node to
   your PATH, and an already-open terminal will not have picked that up.
3. Type:

```
npm install -g @mermaid-js/mermaid-cli
```

This downloads a private copy of the Chrome browser that Mermaid draws with —
about 150 MB. On a slow connection it can take several minutes, and it prints
very little while it works. That is normal; let it finish.

### Confirm it worked

```
mmdc --version
```

You should see a version number like `11.16.0`. If you see "not recognized",
close the terminal and open a new one, then try again — that fixes it most of
the time. If it still fails, `npm root -g` will print where npm installs
things, and the folder above that one needs to be on your PATH.

If Mermaid is missing when you run the script, it stops with a message telling
you exactly this — it does not draw a half-finished picture.

---

## Step 3a — Install the Python `graphviz` package (Optional)

Type:

```
pip install graphviz
```

You'll see a few lines scroll past ending in `Successfully installed graphviz-...`.
If it says it's already installed, that's fine too.

This is the small piece of Python code that knows how to *describe* a diagram.

---

## Step 3b — Install the Graphviz **program** (Optional)

This trips almost everyone up the first time. There are **two separate things
both called "graphviz"**:

- the Python package from Step 3a — describes the diagram, but can't draw it;
- the Graphviz **program** — the actual drawing engine.

You need both. If you skip this step, running the script gives an error
mentioning `dot` or `ExecutableNotFound`.

In your terminal, type:

```
winget install Graphviz.Graphviz
```

A Windows security box will pop up asking *"Do you want to allow this app to make
changes to your device?"* — click **Yes**. (If you click No, the install silently
cancels and you'll hit the `dot` error later.)

If `winget` isn't available on your machine, download the installer manually from
<https://graphviz.org/download/> instead. During that installer, choose the option
**"Add Graphviz to the system PATH"** when offered — same idea as the Python
checkbox above.

### Confirm it worked

**Close your terminal and open a fresh one**, then type:

```
dot -V
```

You should see something like `dot - graphviz version 15.1.0`. If you instead see
"not recognized", the PATH option was missed — re-run the installer and make sure
you tick the PATH box.

---


## Step 4 — Navigate to the right folder

The terminal is always "sitting inside" some folder. You need it to sit inside the
this folder.

The easiest way to do this is to use windows explorer to find this folder, right click
and then "Open in Terminal."

> **Shortcut if you're ever unsure of the path:** open the folder in File Explorer,
> click the address bar at the top, and copy what's there. Paste it after `cd `.
> If the path contains spaces, wrap it in double quotes: `cd "C:\My Folder\Here"`.

Another way is to open a terminal and then use `cd` ("change directory"). Type `cd `, then a
space, then the folder path:

```
cd "full\path\to\this\folder
```
Press Enter. Nothing visible happens — that's success. The text to the left of your
cursor should now show that folder.

To check you're in the right place, type `dir` and press Enter. You should see
`make_groundfish_diagrams.py` in the list.

---

## Step 5 — Run the script

There is **one** command per project. It reads that project's code, works out
what the pipeline currently looks like, and draws all three diagrams:

```
python make_groundfish_diagrams.py
```

For the other project, the command is `python make_fluke_diagrams.py`. Nothing
else changes; everything in this guide applies to both.

> You can also just **double-click** `make_groundfish_diagrams.py` in File
> Explorer, which does the same thing without a terminal. The terminal is worth
> learning anyway, because it leaves the report on screen instead of closing the
> window when it finishes.

It takes a few seconds. First it reads the code:

```
Done. Read the GroundfishRDM code and wrote:
    ...\output\groundfish\pipeline_data_generated.py

It contains 82 boxes and 131 arrows.
```

It then prints a short report — see Step 8 for what that means. Reading the code
changes nothing in `groundfishRDM/`.

Then it draws the three pictures in turn:

```
Success! The comprehensive diagram was generated.

  PNG (double-click to view): ...\GroundfishRDM_comprehensive_pipeline_diagram.png
  SVG (open in a web browser): ...\GroundfishRDM_comprehensive_pipeline_diagram.svg

  82 boxes and 131 arrows drawn.

Success! The simplified diagram was generated.

  PNG (for slides): ...\GroundfishRDM_simple_pipeline_diagram.png
  SVG (for printing): ...\GroundfishRDM_simple_pipeline_diagram.svg

  43 boxes and 90 arrows drawn.
  (39 data-file boxes were folded away to fit one page.)

Success! The data-focused diagram was generated.

  PNG (double-click to view): ...\GroundfishRDM_data_pipeline_diagram.png
  SVG (open in a web browser): ...\GroundfishRDM_data_pipeline_diagram.svg

  43 data boxes and 70 arrows drawn.
  29 arrows are labelled directly; 7 busy scripts use a junction box.
  2 dead-code scripts excluded; all toggles assumed ON.
```

Everything lands in `diagrams\output\groundfish\` (or `\fluke\`).

> **Why the pictures cannot go stale:** all three are drawn from one description
> of the pipeline, and that description is re-read from the source code every
> single time you run this. There is no step you can forget and no cached copy to
> refresh — if the diagram is wrong, the code changed.

> **If you only want one of the three**, add `--only=simple` (or
> `--only=comprehensive`, or `--only=data`) to the command.

---

## Step 6 — Look at the result

- **The PNG:** open the `diagrams\output\groundfish` folder in File Explorer and
  double-click `GroundfishRDM_comprehensive_pipeline_diagram.png`.
- **The SVG:** right-click `GroundfishRDM_comprehensive_pipeline_diagram.svg` → *Open with* → your web browser
  (Chrome, Edge, Firefox). Then use `Ctrl` + scroll wheel to zoom in as far as you
  like without the text going blurry. This is the better option for actually
  reading the diagram — it's a big picture.

### How to read the diagram

- **Blue rounded boxes** are Stata `.do` scripts.
- **Green rounded boxes** are R scripts.
- **The purple box** is the Shiny app — the end of the line, what users see.
- **Grey cylinders** are data files sitting on disk.
- **Yellow octagons** are things outside the code repository: Google Drive, the
  Oracle database, the Azure queue.
- **Thick orange arrows** mean "this script runs that script."
- **Thin grey arrows** show data being read from or written to disk.
- **Dashed orange arrows** with a label like `if pull_MRIP = 1 by default` are the
  optional steps — the label names the on/off switch in `model_wrapper.do` that
  controls them.
- **Red dotted arrows** are connections that exist in practice but *not* in the
  code — two scripts that agree on a shared folder, with nothing actually calling
  one from the other. These were flagged as unconfirmed by the Task 1 analysis, so
  treat them with more caution than the solid ones.
- **Faded, dashed boxes** are scripts the developers themselves labelled "dead
  code" — they're in the repo, but their switch is off by default so they don't run.

There's a **LEGEND panel** in the diagram itself repeating all of the above.

---

## Step 6b — Seeing what changed since last time

Every run replaces the pictures — so each run also keeps the old ones, and tells
you what moved.

**Read the "WHAT CHANGED SINCE THE LAST RUN" section** the script prints. It
names the boxes and arrows that were added or removed:

```
WHAT CHANGED SINCE THE LAST RUN
------------------------------------------------------------------------------
  Boxes added (1):
    * new_helper         new_helper.do              (calib panel)
  Arrows added (1):
    * model_wrapper   -> new_helper        calls, if do_helper = 1 by default
```

This is worth reading even when you don't think anything changed. The detailed
diagram is about 5900 pixels wide with 80-odd boxes, so one new arrow in it is
genuinely impossible to spot by eye — but the script knows exactly which one it
is.

**To compare the pictures themselves**, double-click:

```
diagrams\output\groundfish\compare.html
```

It opens in your browser and shows the previous version next to the current one.
Three buttons across the top change how they're compared:

- **Swipe** — drag the orange divider across to reveal one version under the
  other. Good for "has this corner changed at all?"
- **Side by side** — both at once. Use the **+** zoom button; at "Fit" the whole
  diagram is squeezed into half the window and the small text washes out.
- **Blink** — flips between the two versions a couple of times a second.
  **This is the one to use for a small change:** whatever moved will flicker,
  and everything else sits perfectly still.

The old pictures are kept in `diagrams\output\groundfish\archive\`, with the
date they were made added to the filename, so you can always go back to an
earlier one. Only versions that genuinely look different are kept — running the
script five times without changing anything does not leave five copies. Nothing
is ever deleted from that folder; if it gets too full, delete old ones yourself.

---

## Step 7 — Regenerating the diagrams later

The whole point of this setup is that the diagrams are *generated*, not drawn by
hand — so they never have to go stale.

**If the pipeline changes** (a script is added, removed, or now reads a different
file), you don't have to update any list. Just re-run the same command from
Step 5:

```
python make_groundfish_diagrams.py
```

It re-reads `groundfishRDM/`, picks up the change, and redraws all three
diagrams. **There is no list to edit and nothing to keep in step by hand.**

Two things are worth knowing:

- **Read the report it prints before the pictures.** If it mentions a new script
  or a new data file, that new thing *has* been drawn, but with a name and a
  panel guessed from its filename — which may not be where you'd want it. See
  Step 8.
- **The pictures may re-arrange.** Graphviz decides the layout itself, so adding
  one box can shift others around. The content is what's guaranteed to be right,
  not the positions.

**If nothing changed** and you just want fresh copies of the pictures, running the
command again is still the right move, and still safe — it simply overwrites the
image files.

---

## Step 7b — The two drawing programs

The diagrams are drawn by **Mermaid**, which arranges the detailed diagram more
cleanly than the alternative — noticeably fewer arrows crossing each other.
That is what you get by default, and Step 3b below installs it.

**Graphviz** — the program Step 3 install — is still available and still
works. Add one flag:

```
python make_groundfish_diagrams.py --engine=graphviz
```

Two reasons to reach for it:

- **The simplified ("for presentations") diagram.** Graphviz shrinks the
  finished drawing to fit a 16:9 slide; Mermaid cannot, so its version comes
  out as a large image a slide will letterbox. If that is the diagram you need,
  use this flag.
- **You are on a machine where Node could not be installed.**

Everything else is identical: same folder, same filenames, same three diagrams.

---

## Step 8 — The report, and when to read it carefully

Step 5 prints a short report before it draws anything. You can also get that
report on its own, without writing or redrawing anything:

```
python make_groundfish_diagrams.py --check
```

**This version changes nothing at all** — no files written, no diagrams redrawn,
nothing touched in `groundfishRDM/`. Safe to run whenever you're curious.

Most of the time the report says "New scripts: none. New data files: none." and
there is nothing to do. The part worth reading is:

> **"WHAT THE CODE CONTAINS THAT THE CURATION LIST HAS NOT MET"**

Anything listed there is something new in `groundfishRDM/`. It **has** been drawn —
nothing gets silently dropped — but with a name and a panel guessed from its
filename and folder, which is often not where a human would put it. That's your
cue to tidy it up, and `EXTRACTOR_NOTES.md` explains where.

The report also has a **"HEADER vs CODE"** section. That one isn't about the
diagrams at all: it lists places where a script's `Inputs:`/`Outputs:` comment has
drifted from the code beneath it. It's a to-do list for whoever maintains
GroundfishRDM, not something you need to act on to get a correct picture.

**`EXTRACTOR_NOTES.md` walks through the whole report** — which parts should always
be empty, which differences are deliberate, and what to do about the rest. Read
that before acting on anything the report says.

You don't need anything extra installed for the `--check` version: it uses the same
Python from Step 1, and doesn't even need the Graphviz program from Step 3.

---

## If something goes wrong

| What you see | What it means | Fix |
|---|---|---|
| `'python' is not recognized` | Python isn't installed, or the "Add Python to PATH" box was missed | Redo Step 1b, ticking the PATH checkbox |
| `ModuleNotFoundError: No module named 'graphviz'` | Step 2 was skipped or ran against a different Python | Re-run `pip install graphviz` |
| `ExecutableNotFound` or a message mentioning `dot` | The Graphviz **program** from Step 3 is missing — this is the most common one | Redo Step 3, and open a **new** terminal afterwards |
| `can't open file ... No such file or directory` | The terminal is in the wrong folder | Redo Step 4, then `dir` to confirm you can see the `.py` file |
| Nothing at all happens | You may have forgotten to press Enter | Press Enter |

---

## What each file in this set is for

| File | Purpose |
|---|---|
| `diagrams\make_groundfish_diagrams.py` | What you run. Reads the GroundfishRDM code and draws all three diagrams. `make_fluke_diagrams.py` is the same thing for the other project. |
| `diagrams
dm_diagrams\` | The shared code all projects use: the extractor that reads the source, and one file per diagram that draws it. You should not need to open these. |
| `diagrams\projects\groundfish.py` | Everything specific to GroundfishRDM: where its code lives, and the hand-maintained CURATION list that decides how the pipeline is drawn. This is the file to edit when the report says a new script or data file needs a home. |
| `diagrams\output\groundfish\GroundfishRDM_comprehensive_pipeline_diagram.png` / `.svg` | The detailed picture, in image and zoomable-vector form. |
| `diagrams\output\groundfish\GroundfishRDM_simple_pipeline_diagram.png` / `.svg` | The one-page picture for slides, in image and zoomable-vector form. |
| `diagrams\output\groundfish\GroundfishRDM_data_pipeline_diagram.png` / `.svg` | The data-focused picture, in image and zoomable-vector form. |
| `diagrams\output\groundfish\pipeline_data_generated.py` | The pipeline description the extractor wrote, which all three pictures are drawn from. Machine-written and overwritten on every run — don't edit it by hand. |
| `diagrams\README.md` | How the shared toolchain is laid out, and how to add a third project. |
| `diagrams\output\groundfish\compare.html` | Previous version next to the current one, for spotting what a run changed (Step 6b). |
| `diagrams\output\groundfish rchive\` | Earlier versions of the pictures, with the date in the filename. Only appears once something has changed. |
| `fluke_diagrams\` | The **previous** setup for Fluke: a separate copy of the toolchain, superseded by `diagrams\`, kept for reference. Nothing in the new folder reads it. Groundfish's counterpart, `groundfish_diagrams\`, has been deleted; `--check` for Groundfish no longer has a hand-typed snapshot to compare against, and reports that instead. |
| `SETUP_INSTRUCTIONS.md` | This guide. |
| `EXTRACTOR_NOTES.md` | How to read the `--check` report, and why part of the extractor is still maintained by hand. |
| `DATAFLOW_GROUNDFISH.md` | The written Task 1 analysis the diagram is based on. The diagram is the visual summary; this is the detail. |
