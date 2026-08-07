"""
extract.py
================================================================================
WHAT THIS FILE IS
--------------------------------------------------------------------------------
This module READS a project's source code and works out the pipeline's boxes
and arrows from what is actually written there.

It is the FIRST STEP in drawing the diagrams. The old way was a list of boxes
and arrows typed in by hand: accurate on the day it was written, and quietly
wrong from the first time somebody edited the source without retyping it. This
removes that gap -- the code is the pipeline of record.

You do not run this file directly. Run the wrapper for the project you want:

    python make_fluke_diagrams.py
    python make_groundfish_diagrams.py

Each of those extracts the pipeline and then draws the three diagrams. To read
the report without redrawing anything, add --check (see README.md).

See EXTRACTOR_NOTES.md for a plain-language walk-through of the report, and
SETUP_INSTRUCTIONS.md if this is your first time running Python at all.

--------------------------------------------------------------------------------
WHAT IT CAN AND CANNOT WORK OUT ON ITS OWN
--------------------------------------------------------------------------------
Three things come straight out of the code with no judgement required:

  1. WHICH SCRIPTS RUN, IN WHAT ORDER, AND BEHIND WHICH ON/OFF SWITCH.
     model_wrapper.do declares every switch in its Section D and then runs each
     step inside an "if <switch>" block in Section E. Reading those two sections
     gives the whole spine of the pipeline for free.

  2. WHICH SCRIPTS CALL WHICH OTHER SCRIPTS.
     Stata says   do "...somescript.do"
     R says       source(...)
     Both are easy to spot.

  3. WHICH DATA FILES EACH SCRIPT READS AND WRITES.
     Every pipeline script (bar one or two) carries a comment block at the top
     with "Inputs:" and "Outputs:" fields listing its files. We parse those.

One thing CANNOT come out of the code, and that is what the CURATION dictionary
is for. A diagram is a picture for humans, and a picture needs decisions the
code has no way to express: that three files written as a set should share one
box rather than have three; that a hundred numbered draw files are one box;
that Google Drive deserves a box even though it is not a file; that a script's
box should be labelled over two lines so it fits.

Those decisions live in one clearly-marked dictionary per project, in
projects/<name>.py, and nowhere else. Anything the code contains that CURATION
has not been told about still gets drawn -- it just also gets listed in the run
report under "NEW SINCE THE CURATION LIST WAS WRITTEN". That is the whole
point: a genuinely changed pipeline shows up loudly instead of being silently
dropped.

--------------------------------------------------------------------------------
NOTE FOR ANYONE EDITING THIS FILE
--------------------------------------------------------------------------------
Nothing here may name a specific project. Everything that varies arrives as the
`project` argument -- a Project record from config.py. That is what lets one
copy of this code serve every project; the two hand-maintained copies it
replaced had drifted apart, and a path fix that landed in only one of them left
the other reading an empty folder.
================================================================================
"""

import os
import sys
import re
import fnmatch


# ==============================================================================
# SECTION 1: READING THE COMMENT BLOCK AT THE TOP OF A SCRIPT
# ==============================================================================
# Every pipeline script opens with a header comment shaped like this.
#
#   Stata (.do)                          R (.R)
#   /* Script:  thing.do            */   # Script:       thing.R
#   /* Inputs:  a.dta               */   # Inputs:       a.dta,
#   /*          b.csv               */   #               b.csv
#   /* Outputs: c.dta               */   # Outputs:      c.dta
#
# Two different comment styles, same underlying shape: a field name, then its
# value, then any number of indented continuation lines underneath. So the
# parser below does exactly two things -- peel off the comment decoration, then
# read "Name: value" lines and their indented continuations.

HEADER_FIELDS = ("Script", "Purpose", "Inputs", "Outputs", "Dependencies",
                 "Pipeline", "Note")

_FIELD_RE = re.compile(r"^(\s*)(" + "|".join(HEADER_FIELDS) + r"):\s*(.*)$")


def _undecorate(line, ext):
    """Strip the comment characters off one header line, keeping indentation.

    Keeping the indentation matters: it is the only thing that tells us a line
    is a continuation of the field above rather than a new field.
    """
    s = line.rstrip("\n").rstrip()
    if ext == ".do":
        # Stata headers are drawn as a box: /* ...text... */
        stripped = s.lstrip()
        if stripped.startswith("/*"):
            # Remove "/*" but put back the space it was sitting in, so the
            # indentation of the text inside the box survives.
            s = " " * (len(s) - len(stripped)) + "  " + stripped[2:]
        if s.rstrip().endswith("*/"):
            s = s.rstrip()[:-2]
    else:
        # R headers are ordinary "#" comments.
        stripped = s.lstrip()
        if stripped.startswith("#"):
            s = " " * (len(s) - len(stripped)) + " " + stripped[1:]
    return s.rstrip()


def _is_divider(text):
    """True for the ruled lines (****** or ######) that frame a header block.

    Careful: a BLANK line inside the box (Stata writes it as "/*      */",
    R as a bare "#") also comes out empty here, and that is not a divider --
    several headers have blank lines in the middle of them. So a divider has
    to actually contain ruling characters.
    """
    bare = text.strip()
    if not bare:
        return False
    return set(bare) <= set("*#/-=")


def read_header_block(path):
    """Return {'Inputs': '...', 'Outputs': '...', ...} for one script.

    Returns an empty dict for a script that has no structured header. Only the
    first 150 lines are examined -- the header is always at the very top, and
    reading further would start picking up ordinary code comments.
    """
    ext = os.path.splitext(path)[1].lower()
    fields = {}
    current = None
    started = False

    with open(path, encoding="utf-8", errors="replace") as fh:
        lines = fh.readlines()[:150]

    for raw in lines:
        text = _undecorate(raw, ext)

        if _is_divider(text):
            # A ruled line after we have started reading fields means the
            # header box has closed. Stop before we wander into the code.
            if started:
                break
            continue

        match = _FIELD_RE.match(text)
        if match:
            started = True
            current = match.group(2)
            fields[current] = [match.group(3).strip()]
            continue

        if started and current and text.startswith((" ", "\t")) and text.strip():
            # An indented line under a field is more of that field's value.
            fields[current].append(text.strip())
        elif started and text.strip() and not text.startswith((" ", "\t")):
            # Un-indented free text (e.g. the "Before running:" notes in
            # model_wrapper.do) ends the current field without starting a new one.
            current = None

    return {name: _join_wrapped(parts) for name, parts in fields.items()}


def _join_wrapped(parts):
    """Glue a field's lines back into one string.

    Normally a space between lines is right. But the header authors wrapped
    long paths mid-word, e.g.

        Inputs:  $input_data_cd/{WGOM_Cod,GOM_Haddock}_
                 {historical,projected}_NAA*.dta

    A space there would break the filename in half. So when a line ends on a
    character that clearly continues a path -- an underscore, a slash, a
    hyphen, an open brace -- we join with nothing instead.
    """
    text = ""
    for part in parts:
        if text and not text.endswith(("_", "/", "\\", "-", "{", ",")):
            text += " "
        text += part
    return text.strip()


# --- Pulling filenames out of a chunk of header text -------------------------
#
# The header text says things like
#     $misc_data_cd/mrip_dtrip_by_mode.dta
#     gf.data.dir/calib_catch_draws/calib_catch_draws_raw_<d>.dta
#     baseline_mrip_catch_processed.{xlsx,dta}
#     $calib_catch_draws_cd\calib_catch_draws_`i'.dta
# We want just the bare filename from each: the folder part is a Stata/R macro
# that varies by developer and tells us nothing about the shape of the pipeline.

_BRACE_RE = re.compile(r"\{([^{}]*,[^{}]*)\}")

_FILENAME_RE_CACHE = {}


def _filename_re(extensions):
    """The 'this token is a data filename' pattern, for one set of extensions.

    Built per project rather than once, because which extensions count as data
    is a project setting. Cached because it is rebuilt for every header field
    of every script.
    """
    key = tuple(extensions)
    if key not in _FILENAME_RE_CACHE:
        _FILENAME_RE_CACHE[key] = re.compile(
            r"[A-Za-z0-9_\-.<>*`'$\\/]*\.(?:" + "|".join(key) + r")\b"
        )
    return _FILENAME_RE_CACHE[key]


def _expand_braces(text):
    """Turn 'a.{xlsx,dta}' into 'a.xlsx a.dta' (and the same for {A,B}_x.dta).

    The header authors used shell-style braces as shorthand for a group of
    related files. Expanding them means we see each real filename.
    """
    while True:
        match = _BRACE_RE.search(text)
        if not match:
            return text
        # Find the whitespace-delimited token the braces sit inside.
        start = text.rfind(" ", 0, match.start()) + 1
        end = text.find(" ", match.end())
        if end == -1:
            end = len(text)
        token = text[start:end]
        inner = match.group(1)
        local = token.index("{")
        local_end = token.index("}") + 1
        pieces = [token[:local] + alt.strip() + token[local_end:]
                  for alt in inner.split(",")]
        text = text[:start] + " ".join(pieces) + text[end:]


def extract_filenames(text, extensions):
    """Return the bare data filenames mentioned anywhere in a piece of text."""
    if not text:
        return []
    found = []
    for match in _filename_re(extensions).finditer(_expand_braces(text)):
        name = match.group(0)
        pieces = re.split(r"[\\/]", name)
        # Normally we drop the folder part: it is a Stata/R macro that varies
        # by developer and says nothing about the shape of the pipeline. The
        # exception is a wildcard filename like "output/*.csv" -- there the
        # folder IS the identifying information, so we keep it.
        if pieces[-1].startswith("*") and len(pieces) > 1:
            name = pieces[-2] + "/" + pieces[-1]
        else:
            name = pieces[-1]
        name = name.strip("`'\"$,.;: ")
        if name and "." in name:
            found.append(name)
    # Preserve order but drop duplicates.
    seen = set()
    ordered = []
    for name in found:
        if name.lower() not in seen:
            seen.add(name.lower())
            ordered.append(name)
    return ordered


def normalise(name):
    """Reduce a real filename to a shape we can pattern-match on.

    Filenames in the code carry per-run bits: a draw number, a wave number, a
    date stamp. They appear as a Stata macro (`i'), a global ($ndraws), or a
    documentation placeholder (<date>). All three mean "something varies here",
    so we flatten them to a * wildcard.

    NOTE what this does NOT do: it leaves literal digits alone. An earlier
    version turned every digit into a *, which quietly made
    simulated_catch_totals.dta match the pattern for
    simulated_catch_totals3.dta -- two genuinely different files, one box.
    """
    out = name
    out = re.sub(r"`[^']*'", "*", out)      # Stata local macro:  `i'
    out = re.sub(r"<[^>]*>", "*", out)      # doc placeholder:    <date>
    out = re.sub(r"\$\{?\w+\}?", "*", out)  # global macro:       $ndraws
    out = re.sub(r"\{[^}]*\}", "*", out)    # R glue slot:        {date}
    out = re.sub(r"\*+", "*", out)          # collapse ** to *
    return out.lower()


# ==============================================================================
# SECTION 2: READING THE WRAPPER -- execution order and the on/off toggles
# ==============================================================================
# model_wrapper.do has two halves that matter to us:
#
#   Section D declares the switches:      loc estimate_dtrips = 1   // comment
#   Section E uses them:                  if `estimate_dtrips' {
#                                             do "$input_code_cd\directed_trips_calibration.do"
#                                         }
#
# Walking Section E in order therefore gives us, in one pass: the execution
# order of the whole pre-simulation pipeline, which script each step runs, and
# which switch turns that step on or off.

_TOGGLE_DECL_RE = re.compile(r"^\s*loc(?:al)?\s+(\w+)\s*=\s*(\d+)", re.IGNORECASE)
_IF_TOGGLE_RE = re.compile(r"^\s*if\s+`(\w+)'\s*\{")
# Both ways Stata launches something: "do" for another .do file, "rscript
# using" for an R script.
_DO_RE = re.compile(r'^\s*do\s+"([^"]+)"')
_RSCRIPT_RE = re.compile(r'rscript\s+using\s+"([^"]+)"', re.IGNORECASE)


def parse_wrapper(path):
    """Return (toggle defaults, ordered [(toggle, script filename), ...]).

    'toggle defaults' is {switch name: 0 or 1} straight from Section D, so we
    know which steps ship switched off. The ordered list is every script the
    wrapper runs, in the order the wrapper runs them; toggle is None for the
    handful of calls that sit outside any if-block and therefore always happen.
    """
    with open(path, encoding="utf-8", errors="replace") as fh:
        lines = fh.readlines()

    defaults = {}
    sequence = []
    active_toggle = None
    depth = 0

    for line in lines:
        decl = _TOGGLE_DECL_RE.match(line)
        if decl:
            defaults[decl.group(1)] = int(decl.group(2))
            continue

        opener = _IF_TOGGLE_RE.match(line)
        if opener:
            active_toggle = opener.group(1)
            depth = 1
            continue

        if active_toggle:
            # Track braces so we know when the if-block ends. The blocks here
            # are simple, so counting { and } is enough.
            depth += line.count("{") - line.count("}")
            if depth <= 0:
                active_toggle = None

        for regex in (_DO_RE, _RSCRIPT_RE):
            hit = regex.search(line)
            if hit:
                script = re.split(r"[\\/]", hit.group(1))[-1]
                sequence.append((active_toggle, script))

    return defaults, sequence


# R's way of running another script, in the three spellings the repos use:
#   source(here("Code", "sim", "thing.R"))
#   source(file.path(code_cd, "thing.R"))
#   source(here::here("RecDST/model_run.R"))
_SOURCE_RE = re.compile(r'^\s*source\s*\(.*?"([^"]+\.[Rr])"\s*\)?', re.MULTILINE)


def parse_calls(path):
    """Return the scripts this one script runs directly.

    Commented-out calls are ignored -- "R code wrapper.R" has a disabled
    #source(...) line for the projection step, and drawing an arrow for a step
    that does not run would be actively misleading.
    """
    called = []
    ext = os.path.splitext(path)[1].lower()
    with open(path, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    # Same reason as in scan_statements: a `do "..."` sitting inside a
    # /* ... */ block is disabled code, and drawing an arrow for it would put
    # a step on the picture that never runs.
    if ext == ".do":
        text = _strip_block_comments(text)
    for line in text.splitlines():
        bare = line.strip()
        if ext in (".R", ".r"):
            if bare.startswith("#"):
                continue
            hit = _SOURCE_RE.match(line)
            if hit:
                called.append(re.split(r"[\\/]", hit.group(1))[-1])
        else:
            if bare.startswith("*") or bare.startswith("//"):
                continue
            for regex in (_DO_RE, _RSCRIPT_RE):
                hit = regex.search(line)
                if hit:
                    called.append(re.split(r"[\\/]", hit.group(1))[-1])
    # Drop duplicates, keep order.
    seen = set()
    ordered = []
    for name in called:
        if name.lower() not in seen:
            seen.add(name.lower())
            ordered.append(name)
    return ordered


# ==============================================================================
# SECTION 3: THE CROSS-CHECK -- what the code actually touches
# ==============================================================================
# Sections 1 and 2 trust the header comments. Comments can go out of date. So
# this section ignores the comments entirely and looks at the real read/write
# statements instead, purely so we can compare the two and complain when they
# disagree.
#
# Nothing in this section feeds the diagram. Its only output is the
# "HEADER vs CODE" part of the report. That is deliberate: a header that has
# drifted is a thing for a human to fix in the source, not for this script to
# paper over.

# Stata statements that read a file, and the ones that write.
_STATA_READ = re.compile(
    r'^\s*(?:use|u|append\s+using|import\s+delimited\s+using|import\s+excel\s+using|'
    r'import\s+delimited|merge\s+[\w:]+\s+[^"]*using)\s+"([^"]+)"', re.IGNORECASE)
_STATA_WRITE = re.compile(
    r'^\s*(?:save|saveold|export\s+delimited\s+using|export\s+delimited|'
    r'export\s+excel|graph\s+export)\s+"([^"]+)"', re.IGNORECASE)

# R functions that read a file, and the ones that write. In R the filename is
# often on a following line, so we search a window of text after the call
# rather than the same line.
_R_READ_FUNCS = ("read_fst", "read_dta", "read_csv", "read.csv", "read_excel",
                 "readRDS", "read_feather", "fread")
_R_WRITE_FUNCS = ("write_fst", "write_dta", "write_csv", "write.csv", "saveRDS",
                  "write_feather", "fwrite", "ggsave")


def _strip_block_comments(text):
    """Blank out /* ... */ spans in Stata source, keeping the line count.

    This matters more than it looks. Stata developers disable a whole section
    by wrapping it in /* ... */, and several scripts here do exactly that with
    their diagnostic figure code. Skipping only lines that START with * or //
    misses those entirely, so a commented-out `graph export` reads as a live
    write -- and the checker then accuses a perfectly accurate header of
    having drifted. Two of the three findings it originally reported were this
    bug, not real drift.

    Newlines inside the span are preserved so the line-anchored patterns below
    still see the file's real line structure.
    """
    def blank(match):
        return "\n" * match.group(0).count("\n")
    return re.sub(r"/\*.*?\*/", blank, text, flags=re.DOTALL)


def _same_file(a, b):
    """True if two normalised filenames plausibly refer to the same file.

    Both sides can contain wildcards, and they often use DIFFERENT conventions
    for the varying part. The header of RP_data_analysis.do writes the MRIP
    files as trip_YYYYW.dta; the code writes them as trip_`year'`wave'.dta,
    which normalises to trip_*.dta. Those are the same file described two ways.

    Comparing the two strings for equality -- which is what this did at first --
    reported every such pair as drift, and buried the two or three genuine
    findings in false alarms. So we glob each against the other.
    """
    return a == b or fnmatch.fnmatch(a, b) or fnmatch.fnmatch(b, a)


def scan_statements(path, extensions):
    """Return (files read, files written) according to the actual code."""
    ext = os.path.splitext(path)[1].lower()
    reads, writes = [], []

    with open(path, encoding="utf-8", errors="replace") as fh:
        text = fh.read()

    if ext == ".do":
        for line in _strip_block_comments(text).splitlines():
            bare = line.strip()
            if bare.startswith("*") or bare.startswith("//"):
                continue
            for regex, bucket in ((_STATA_READ, reads), (_STATA_WRITE, writes)):
                hit = regex.match(line)
                if hit:
                    bucket.extend(extract_filenames(hit.group(1), extensions))
    else:
        for funcs, bucket in ((_R_READ_FUNCS, reads), (_R_WRITE_FUNCS, writes)):
            for func in funcs:
                for match in re.finditer(re.escape(func) + r"\s*\(", text):
                    # Look at the next ~300 characters: enough to cover a call
                    # split across several lines, short enough not to run into
                    # the next statement.
                    window = text[match.end():match.end() + 300]
                    line_start = text.rfind("\n", 0, match.start()) + 1
                    if text[line_start:match.start()].lstrip().startswith("#"):
                        continue
                    names = extract_filenames(window, extensions)
                    if names:
                        bucket.append(names[0])

    return sorted(set(reads)), sorted(set(writes))


# ==============================================================================
# SECTION 4: PUTTING IT TOGETHER
# ==============================================================================
# Sections 1-3 read the code, the project's CURATION dictionary supplies the
# human decisions. This section combines them into the nodes and edges lists a
# diagram needs.

def find_scripts(project):
    """Return {filename: full path} for every script in the pipeline folders."""
    found = {}
    for dirpath, dirnames, filenames in os.walk(project.repo):
        dirnames[:] = [d for d in dirnames if d not in project.skip_folders]
        for name in filenames:
            if name.lower().endswith((".do", ".r")):
                if name in project.curation["skip_scripts"]:
                    continue
                found[name] = os.path.join(dirpath, name)
    return found


def script_type(filename):
    """Blue Stata box, green R box, or the one purple Shiny box."""
    if filename == "app.R":
        return "shiny"
    return "stata" if filename.lower().endswith(".do") else "r"


def auto_id(filename):
    """Make a usable box id from a filename, for scripts CURATION has not met."""
    stem = os.path.splitext(filename)[0]
    return re.sub(r"[^A-Za-z0-9_]", "_", stem).strip("_").lower()


def folder_stage(path, project):
    """Guess which panel a newly-appeared script belongs in, from its folder."""
    rel = os.path.relpath(path, project.repo).replace("\\", "/").lower()
    if "code/sim" in rel:
        return "sim"
    if "recdst" in rel:
        return "shiny"
    if "code/helpers" in rel:
        return "setup"
    if "code/pre_sim" in rel:
        return "calib"
    return "standalone"


def build_data_index(project):
    """Return a list of (compiled pattern, group id) for matching filenames."""
    index = []
    for group in project.curation["data_groups"]:
        for pattern in group["files"]:
            index.append((normalise(pattern), group["id"]))
    # Longest pattern first, so mrip_dtrip_by_mode_season.dta is tested before
    # a looser pattern can claim it.
    index.sort(key=lambda pair: -len(pair[0]))
    return index


def match_data(filename, index, project):
    """Map a real filename onto the box it belongs to, or None if unknown."""
    flat = normalise(filename)
    for pattern in project.curation["skip_data"]:
        if fnmatch.fnmatch(flat, normalise(pattern)):
            return "__skip__"
    for pattern, group_id in index:
        if fnmatch.fnmatch(flat, pattern):
            return group_id
    return None


def build(project):
    """Read the code and return (stages, nodes, edges, report)."""
    curation = project.curation
    extensions = project.data_extensions

    report = {
        "new_scripts": [],      # scripts with no CURATION entry
        "new_data": [],         # data files with no CURATION group
        "no_header": [],        # scripts with no Inputs:/Outputs: block
        "drift": [],            # header says one thing, code says another
    }

    scripts = find_scripts(project)
    data_index = build_data_index(project)

    # --- Which box does each script get? ------------------------------------
    script_node = {}    # filename -> box id
    nodes = []
    for filename in sorted(scripts):
        entry = curation["scripts"].get(filename)
        if entry:
            node_id, label, stage, dead = entry
        else:
            node_id = auto_id(filename)
            label, stage, dead = None, folder_stage(scripts[filename], project), False
            report["new_scripts"].append(filename)
        script_node[filename] = node_id
        node = {"id": node_id, "label": label or filename,
                "type": script_type(filename), "stage": stage}
        if dead:
            node["dead"] = True
        nodes.append(node)

    # --- Execution order, toggles, and every "runs" arrow -------------------
    toggles, sequence = parse_wrapper(project.wrapper)
    edges = []

    def add_edge(edge):
        """Add an arrow unless CURATION says to leave it out or it duplicates.

        Two boxes get at most one arrow between them, and the first one wins.
        Without that rule a pair can end up with, say, both a solid "writes"
        and a dotted "inferred" arrow saying the same thing twice.
        """
        for src, dst, kind, _why in curation["skip_edges"]:
            if (src, dst) == (edge["from"], edge["to"]) and \
                    (kind is None or kind == edge["kind"]):
                return
        for existing in edges:
            if (existing["from"], existing["to"]) == (edge["from"], edge["to"]):
                return
        edges.append(edge)

    wrapper_id = script_node.get("model_wrapper.do", "model_wrapper")
    for toggle, called in sequence:
        if called not in script_node:
            continue
        edge = {"from": wrapper_id, "to": script_node[called], "kind": "calls"}
        if toggle:
            edge["toggle"] = toggle
            if toggles.get(toggle, 1) == 0:
                edge["default_off"] = True
        add_edge(edge)

    # --- Every other "script runs script" arrow -----------------------------
    for filename, path in sorted(scripts.items()):
        if filename == "model_wrapper.do":
            continue           # already handled above, with its toggles
        for called in parse_calls(path):
            if called not in script_node:
                continue
            if (filename, called) in curation["skip_calls"]:
                continue
            add_edge({"from": script_node[filename],
                      "to": script_node[called], "kind": "calls"})

    # --- Which data files does each script read and write? ------------------
    data_used = {}      # group id -> the stage we think it belongs to
    for filename, path in sorted(scripts.items()):
        header = read_header_block(path)
        if "Inputs" not in header and "Outputs" not in header:
            report["no_header"].append(filename)
            continue

        this_node = script_node[filename]
        this_stage = next(n["stage"] for n in nodes if n["id"] == this_node)

        for field, kind in (("Inputs", "reads"), ("Outputs", "writes")):
            field_text = header.get(field, "")
            # Filenames named outright, plus the ones named only through a
            # Stata global that CURATION["macros"] tells us how to resolve.
            names = extract_filenames(field_text, extensions)
            macro_groups = [curation["macros"][m]
                            for m in re.findall(r"\$(\w+)", field_text)
                            if m in curation["macros"]]
            for group_id in dict.fromkeys(macro_groups):
                if kind == "reads":
                    add_edge({"from": group_id, "to": this_node, "kind": "reads"})
                else:
                    add_edge({"from": this_node, "to": group_id, "kind": "writes"})

            for name in names:
                group_id = match_data(name, data_index, project)
                if group_id == "__skip__":
                    continue
                if group_id is None:
                    group_id = auto_id(name)
                    report["new_data"].append((filename, name))
                    data_used.setdefault(group_id, this_stage)
                    nodes.append({"id": group_id, "label": name,
                                  "type": "data", "stage": this_stage})
                if kind == "reads":
                    add_edge({"from": group_id, "to": this_node, "kind": "reads"})
                else:
                    add_edge({"from": this_node, "to": group_id, "kind": "writes"})

        # --- The cross-check: does the code agree with the header? ----------
        code_reads, code_writes = scan_statements(path, extensions)
        header_all = {normalise(n) for n in
                      extract_filenames(header.get("Inputs", ""), extensions) +
                      extract_filenames(header.get("Outputs", ""), extensions)}
        for name in code_reads + code_writes:
            if match_data(name, data_index, project) == "__skip__":
                continue
            if not any(_same_file(normalise(name), listed) for listed in header_all):
                report["drift"].append((filename, name, "in code, not in header"))

    # --- Add the data boxes that were actually used -------------------------
    drawn = {n["id"] for n in nodes}
    for group in curation["data_groups"]:
        if group["id"] in drawn:
            continue
        touched = any(e["from"] == group["id"] or e["to"] == group["id"]
                      for e in edges) or \
            any(e["from"] == group["id"] or e["to"] == group["id"]
                for e in curation["extra_edges"])
        if touched:
            nodes.append({"id": group["id"], "label": group["label"],
                          "type": "data", "stage": group["stage"]})
            drawn.add(group["id"])

    # --- Add the external boxes and the arrows the code cannot show ---------
    for node in curation["extra_nodes"]:
        if node["id"] not in drawn:
            nodes.append(dict(node))
            drawn.add(node["id"])
    for edge in curation["extra_edges"]:
        if edge["from"] in drawn and edge["to"] in drawn:
            add_edge(dict(edge))

    # --- Sort into pipeline order, not alphabetical -------------------------
    stage_order = {sid: i for i, (sid, _) in enumerate(curation["stages"])}
    type_order = {"stata": 0, "r": 0, "shiny": 0, "data": 1, "external": 2}
    nodes.sort(key=lambda n: (stage_order.get(n["stage"], 99),
                              type_order.get(n["type"], 9), n["id"]))

    return curation["stages"], nodes, edges, report


# ==============================================================================
# SECTION 5: WRITING THE RESULT OUT, AND THE --check REPORT
# ==============================================================================

def _py(value):
    """Render a Python value as source text, keeping \\n readable in labels."""
    return repr(value)


def write_module(stages, nodes, edges, path, project):
    """Write pipeline_data_generated.py in the same shape as the hand list."""
    lines = [
        '"""',
        "pipeline_data_generated.py",
        "=" * 78,
        "MACHINE-WRITTEN -- DO NOT EDIT BY HAND.",
        "",
        "Every line below was produced by rdm_diagrams/extract.py reading the",
        "%s source. Edit that script (or the code it reads) instead; any"
        % project.display_name,
        "change made here is lost the next time the extractor runs.",
        "",
        "The three lists below are what every renderer in rdm_diagrams/ draws from.",
        "The shape dates from the hand-typed list this replaced, so an old snapshot",
        "of that list can still be compared against it.",
        '"""',
        "",
        "STAGES = [",
    ]
    for stage_id, title in stages:
        lines.append("    (%s, %s)," % (_py(stage_id), _py(title)))
    lines.append("]")
    lines.append("")
    lines.append("nodes = [")
    for node in nodes:
        parts = ", ".join("%s: %s" % (_py(k), _py(v)) for k, v in node.items())
        lines.append("    {%s}," % parts)
    lines.append("]")
    lines.append("")
    lines.append("edges = [")
    for edge in edges:
        parts = ", ".join("%s: %s" % (_py(k), _py(v)) for k, v in edge.items())
        lines.append("    {%s}," % parts)
    lines.append("]")
    lines.append("")

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


def print_report(report, project):
    """Print the things a human may need to act on."""
    print("")
    print("-" * 78)
    print("WHAT THE CODE CONTAINS THAT THE CURATION LIST HAS NOT MET")
    print("-" * 78)
    if report["new_scripts"]:
        print("  New scripts (drawn with an auto-generated label and panel):")
        for name in report["new_scripts"]:
            print("    * " + name)
    else:
        print("  New scripts: none.")

    if report["new_data"]:
        print("  New data files (each got its own box):")
        for script, name in sorted(set(report["new_data"])):
            print("    * %-34s (named in %s)" % (name, script))
    else:
        print("  New data files: none.")

    if report["no_header"]:
        print("  Scripts with no Inputs:/Outputs: header -- their reads and writes")
        print("  could not be read, so their box has no data arrows:")
        for name in report["no_header"]:
            print("    * " + name)

    print("")
    print("-" * 78)
    print("HEADER vs CODE -- files the code touches that the header does not list")
    print("-" * 78)
    print("These are not extractor errors. Each one is a header comment in")
    print("%s/ that has drifted from the code underneath it, or a file"
          % project.repo_name)
    print("read through a macro the header describes in words rather than by name.")
    if report["drift"]:
        by_script = {}
        for script, name, _ in report["drift"]:
            by_script.setdefault(script, set()).add(name)
        for script in sorted(by_script):
            print("  " + script)
            for name in sorted(by_script[script]):
                print("      " + name)
    else:
        print("  None -- every file the code touches appears in its header.")


def run_check(stages, nodes, edges, report, project):
    """Compare what we extracted against the hand-typed list, and print both.

    A project with no hand-typed snapshot (project.reference_module is None)
    has nothing to compare against, and says so. The older version of this code
    fell back to comparing against the live diagram script -- which reads the
    extraction, so the comparison would report a perfect match no matter what
    the source code said. An alarm that can never go off is worse than none.
    """
    if not project.reference_module:
        print("")
        print("No reference list configured for %s, so there is nothing to"
              % project.display_name)
        print("compare the extraction against. Only the report below is available.")
        print("(Set reference_module in projects/%s.py if a hand-typed snapshot"
              % project.key)
        print(" of this project's boxes and arrows is ever written.)")
        print_report(report, project)
        return

    reference = None
    problem = None
    try:
        reference = _import_reference(project)
    except ImportError:
        reference = None
    except Exception as exc:   # graphviz missing, most likely
        problem = exc

    if reference is None:
        print("Could not read the hand-typed list for comparison: %s"
              % (problem or "no reference file found"))
        print("(--check may need the graphviz package, because an older diagram")
        print(" script imports it. A plain run does not.)")
        return

    ref_nodes = {n["id"]: n for n in reference.nodes}
    new_nodes = {n["id"]: n for n in nodes}

    def edge_key(e):
        return (e["from"], e["to"], e["kind"])

    ref_edges = {edge_key(e): e for e in reference.edges}
    new_edges = {edge_key(e): e for e in edges}

    print("")
    print("=" * 78)
    print("COMPARISON WITH THE HAND-TYPED LIST (the Task 1 snapshot)")
    print("=" * 78)
    print("hand-typed: %3d boxes, %3d arrows" % (len(reference.nodes), len(reference.edges)))
    print("extracted : %3d boxes, %3d arrows" % (len(nodes), len(edges)))

    # The "calls" arrows are the mechanical part -- read straight out of the
    # wrapper -- so any difference here is a real bug, not a judgement call.
    ref_calls = {k for k in ref_edges if k[2] == "calls"}
    new_calls = {k for k in new_edges if k[2] == "calls"}
    print("")
    print("--- RUNS arrows (the mechanical part -- these should match exactly) ---")
    if ref_calls == new_calls:
        print("  All %d match." % len(ref_calls))
    else:
        for key in sorted(ref_calls - new_calls):
            print("  only in hand-typed: %s -> %s" % (key[0], key[1]))
        for key in sorted(new_calls - ref_calls):
            print("  only in extracted : %s -> %s" % (key[0], key[1]))
    # Toggle names attached to those arrows.
    toggle_diff = []
    for key in sorted(ref_calls & new_calls):
        a, b = ref_edges[key], new_edges[key]
        if a.get("toggle") != b.get("toggle") or \
           bool(a.get("default_off")) != bool(b.get("default_off")):
            toggle_diff.append((key, a.get("toggle"), b.get("toggle"),
                                a.get("default_off"), b.get("default_off")))
    if toggle_diff:
        print("  Toggle differences:")
        for key, ta, tb, da, db in toggle_diff:
            print("    %s -> %s : hand=%s%s extracted=%s%s"
                  % (key[0], key[1], ta, " (off)" if da else "",
                     tb, " (off)" if db else ""))
    else:
        print("  Every toggle name and default matches.")

    print("")
    print("--- BOXES ---")
    only_ref = sorted(set(ref_nodes) - set(new_nodes))
    only_new = sorted(set(new_nodes) - set(ref_nodes))
    if not only_ref and not only_new:
        print("  Same set of boxes.")
    for node_id in only_ref:
        print("  only in hand-typed: %-16s (%s)" % (node_id, ref_nodes[node_id]["label"].replace("\n", " / ")))
    for node_id in only_new:
        print("  only in extracted : %-16s (%s)" % (node_id, new_nodes[node_id]["label"].replace("\n", " / ")))

    attr_diff = []
    for node_id in sorted(set(ref_nodes) & set(new_nodes)):
        a, b = ref_nodes[node_id], new_nodes[node_id]
        for field in ("type", "stage", "label"):
            if a.get(field) != b.get(field):
                attr_diff.append((node_id, field, a.get(field), b.get(field)))
        if bool(a.get("dead")) != bool(b.get("dead")):
            attr_diff.append((node_id, "dead", a.get("dead"), b.get("dead")))
    if attr_diff:
        print("  Boxes that exist in both but differ:")
        for node_id, field, a, b in attr_diff:
            print("    %-16s %-6s hand=%r extracted=%r" % (node_id, field, a, b))

    print("")
    print("--- READS / WRITES / INFERRED arrows ---")
    only_ref_e = [k for k in ref_edges if k not in new_edges and k[2] != "calls"]
    only_new_e = [k for k in new_edges if k not in ref_edges and k[2] != "calls"]

    # An arrow between the same two boxes drawn in a different STYLE is not a
    # missing arrow and a new arrow -- it is one connection whose confidence
    # changed. Almost always that means Task 1 could only guess at a link, and
    # a header added since then now states it outright. Worth its own heading,
    # because a reader scanning the two lists below would otherwise count the
    # same connection twice and think something had gone wrong.
    ref_pairs = {k[:2]: k[2] for k in only_ref_e}
    new_pairs = {k[:2]: k[2] for k in only_new_e}
    restyled = sorted(set(ref_pairs) & set(new_pairs))
    only_ref_e = sorted(k for k in only_ref_e if k[:2] not in new_pairs)
    only_new_e = sorted(k for k in only_new_e if k[:2] not in ref_pairs)

    if restyled:
        print("  Same connection, drawn differently:")
        for pair in restyled:
            print("    %-16s -> %-16s hand=%-8s extracted=%s"
                  % (pair[0], pair[1], ref_pairs[pair], new_pairs[pair]))
    if not only_ref_e and not only_new_e and not restyled:
        print("  Same set of arrows.")
    for key in only_ref_e:
        print("  only in hand-typed: %-16s -%s-> %s" % (key[0], key[2], key[1]))
    for key in only_new_e:
        print("  only in extracted : %-16s -%s-> %s" % (key[0], key[2], key[1]))

    print_report(report, project)
    print("")
    print("This is a report, not a test. Differences are expected -- see")
    print("EXTRACTOR_NOTES.md for which ones are deliberate and which mean the")
    print("diagrams have gone stale.")


def _import_reference(project):
    """Import the project's hand-typed snapshot module.

    The snapshot files were never moved into this folder -- they are session
    records of an abandoned approach and belong where they were written. So we
    load one by path rather than by import name.
    """
    import importlib.util

    from .config import TOOLCHAIN_DIR

    name = project.reference_module
    path = os.path.join(project.reference_dir or TOOLCHAIN_DIR, name + ".py")
    if not os.path.isfile(path):
        raise ImportError("no file at " + path)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)

    # Do not leave a __pycache__ folder behind. The snapshot lives in a folder
    # this toolchain otherwise only reads, and dropping a new folder into it
    # would look like something we changed there. Nothing needs the speed-up.
    was_off = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = was_off

    return module
