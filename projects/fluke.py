"""
fluke.py
================================================================================
Everything that is specific to the flukeRDM project, and nothing else.

Two kinds of thing live here:

  * The Project record at the BOTTOM of the file: where the source code sits,
    what to call the project in titles, and what to put on the front of the
    picture filenames.

  * The CURATION dictionary: the hand-maintained decisions about how this
    project's pipeline should be DRAWN. Everything above it in the toolchain
    reads the code; this is the part a human maintains.

The shared code that reads all of this is in rdm_diagrams/. Nothing there names
a project, so a change here cannot affect any other project's diagrams.

To draw these diagrams:  python make_fluke_diagrams.py
================================================================================
"""

from rdm_diagrams.config import Project


# ==============================================================================
# THE CURATION LAYER -- the hand-maintained part
# ==============================================================================
# The extractor reads flukeRDM's source code and works out the pipeline for
# itself. This dictionary supplies the handful of things the code has no way to
# say, because they are decisions about the PICTURE rather than facts about the
# PIPELINE:
#
#   * "these three files are really one thing, give them one box"
#   * "call this box cpt1 internally and print this two-line label in it"
#   * "this box belongs in the calibration panel"
#   * "Google Drive is worth drawing even though it is not a file"
#   * "this script is dead code"
#
# If the pipeline changes, this is the part a human may need to touch -- and the
# run report tells you exactly which entries are missing. Anything the code
# contains that is not mentioned here still gets drawn; it just also gets
# listed in the report under "NEW SINCE THE CURATION LIST WAS WRITTEN".

CURATION = {

    # --- Scripts -----------------------------------------------------------
    # filename -> (short id, label to print in the box, stage panel, dead?)
    # A label of None means "just print the filename".
    "scripts": {
        # Stage 0: the three entry points and their setup helpers.
        "model_wrapper.do":            ("model_wrapper", "model_wrapper.do\n(STATA WRAPPER - entry point 1)", "setup", False),
        "developer_setup_stata.do":    ("dev_setup_stata", None, "setup", False),
        "R code wrapper.R":            ("r_wrapper", "R code wrapper.R\n(R WRAPPER - entry point 2)", "setup", False),
        "developer_setup.R":           ("dev_setup_r", None, "setup", False),

        # Stage 1-3: pulling in raw data.
        "get_assessment_from_gdrive.do": ("get_assessment", None, "acquire", False),
        "MRIP_column_cases.do":          ("mrip_col_cases", None, "acquire", False),
        "MRIP_lists.do":                 ("mrip_lists_do", None, "acquire", False),

        # Stage 4-6: effort, costs, preferences.
        "directed_trips_calibration.do":  ("dtrips", None, "calib", False),
        "set_regulations.do":             ("set_regs", "set_regulations.do\n(UPDATE EVERY YEAR)", "calib", False),
        "survey_trip_costs.do":           ("trip_costs_do", None, "calib", False),
        "estimate_angler_preferences.do": ("angler_prefs", "estimate_angler_preferences.do\n(estimation block disabled)", "calib", False),

        # Stage 7-10: calibration catch-per-trip.
        "catch_per_trip_calibration_part1.do":  ("cpt1", None, "calib", False),
        "copula_modeling_calibration.R":        ("copula_calib", None, "calib", False),
        "calibration_catch_per_trip_part2.do":  ("cpt2", None, "calib", False),
        "compare_calibration_data_to_MRIP.do":  ("compare_calib", None, "calib", False),

        # Stage 11-12: catch-at-length.
        "calibration_catch_at_length.do": ("cal_catlen", None, "catlen", False),
        "projected_catch_at_length.do":   ("proj_catlen", None, "catlen", False),

        # Stage 13: projection catch-per-trip (one meta-toggle gates all four).
        "catch_per_trip_projection_part1.do": ("pcpt1", None, "proj", False),
        "copula_modeling_projection.R":       ("copula_proj", None, "proj", False),
        "catch_per_trip_projection_part2.do": ("pcpt2", None, "proj", False),
        "compare_projection_data_to_MRIP.do": ("compare_proj", None, "proj", False),

        # R calibration and projection.
        "calibrate_rec_catch0_optimized.R": ("calib0", "calibrate_rec_catch0_optimized.R\n(PASS 0 - strict compliance)", "sim", False),
        "calibration_routine_final.R":      ("calib_routine", "calibration_routine_final.R\n(search driver)", "sim", False),
        "calibrate_rec_catch1_final.R":     ("calib1", "calibrate_rec_catch1_final.R\n(PASS 1 - reallocation)", "sim", False),
        "predict_rec_catch_final.R":        ("predict_proj", None, "sim", False),

        # Shiny decision-support tool and the projection path it triggers.
        "app.R":                 ("app", "app.R\n(Shiny recDST)", "shiny", False),
        "Run_Model.R":           ("run_model", "Run_Model.R\n(entry point 3)", "shiny", False),
        # All nine per-state scripts share one id so they collapse into a
        # single box. They are near-identical; nine boxes would say nothing
        # that one box does not. Drop the shared id for nine separate boxes.
        "model_run_MA.R": ("model_run", "recDST/model_run_<ST>.R\n(9 near-identical per-state scripts)", "shiny", False),
        "model_run_RI.R": ("model_run", "recDST/model_run_<ST>.R\n(9 near-identical per-state scripts)", "shiny", False),
        "model_run_CT.R": ("model_run", "recDST/model_run_<ST>.R\n(9 near-identical per-state scripts)", "shiny", False),
        "model_run_NY.R": ("model_run", "recDST/model_run_<ST>.R\n(9 near-identical per-state scripts)", "shiny", False),
        "model_run_NJ.R": ("model_run", "recDST/model_run_<ST>.R\n(9 near-identical per-state scripts)", "shiny", False),
        "model_run_DE.R": ("model_run", "recDST/model_run_<ST>.R\n(9 near-identical per-state scripts)", "shiny", False),
        "model_run_MD.R": ("model_run", "recDST/model_run_<ST>.R\n(9 near-identical per-state scripts)", "shiny", False),
        "model_run_VA.R": ("model_run", "recDST/model_run_<ST>.R\n(9 near-identical per-state scripts)", "shiny", False),
        "model_run_NC.R": ("model_run", "recDST/model_run_<ST>.R\n(9 near-identical per-state scripts)", "shiny", False),
        # The in-progress refactor of the nine scripts above. Neither file is
        # sourced by anything, so both are marked dead.
        "run_state_model.R":         ("run_state_model", "run_state_model.R\n(refactor, NOT WIRED UP)", "shiny", True),
        "apply_directed_trips_regs.R": ("apply_regs", "apply_directed_trips_regs.R\n(NEVER SOURCED)", "shiny", True),

        # Not wrapper-controlled.
        "check calibration convergence.do": ("check_conv", "check calibration convergence.do\n(manual, interactive)", "standalone", False),
        "compare_savedregs_output.R":       ("compare_savedregs", "compare_savedregs_output.R\n(SYNTAX ERROR - does not parse)", "standalone", True),
        "generate_coastwide_data.R":        ("coastwide", None, "standalone", False),
        "rdb_catch_per_trip_to_drive.R":    ("rdb_push", "rdb_catch_per_trip_to_drive.R\n(toggle exists, never called)", "standalone", True),
    },

    # --- Scripts left off the picture entirely -----------------------------
    "skip_scripts": {
        "googledrivesetup.R",     # one-time OAuth setup, entirely commented out
        "required_packages.R",    # one-time package install
    },

    # --- Calls that exist but are not worth an arrow -----------------------
    "skip_calls": {
        ("copula_modeling_calibration.R", "developer_setup.R"),
        ("copula_modeling_projection.R", "developer_setup.R"),
        ("rdb_catch_per_trip_to_drive.R", "developer_setup.R"),
    },

    # --- Data files --------------------------------------------------------
    # One entry per BOX. Patterns are matched longest-first, so a specific
    # pattern always wins over a looser one regardless of the order here.
    "data_groups": [
        # ---- Raw inputs ----
        {"id": "mrip_lists", "stage": "acquire",
         "label": "$triplist $catchlist\n$b2list $sizelist\n(MRIP trip/catch/size extracts)",
         "files": ["trip_*.dta", "catch_*.dta", "size_*.dta", "size_b2_*.dta"]},
        {"id": "naa_files", "stage": "acquire",
         "label": "assessment numbers-at-age\nfit_NAA_* / fit_proj_NAA_* / J1_*",
         "files": ["fit_naa_*.csv", "fit_proj_naa_*.csv", "j1_*.csv"]},
        {"id": "trawl_svy", "stage": "acquire",
         "label": "NEFSC trawl survey data.csv",
         "files": ["nefsc trawl survey data.csv", "data.csv"]},
        {"id": "fes_dems", "stage": "calib",
         "label": "fes_person_final_<year><wave>.dta\n(FES 12-month, not public)",
         "files": ["fes_person_final_*.dta"]},
        {"id": "exp_survey", "stage": "calib",
         "label": "gulf_atl_2022.dta\nprim1.dta / prim2.dta",
         "files": ["gulf_atl_*.dta", "prim1.dta", "prim2.dta"]},
        {"id": "vas_length", "stage": "catlen",
         "label": "CT/NJ/RI volunteer survey\n+ ALS tag length workbooks",
         "files": ["*vas*.xlsx", "*als*.xlsx", "bsb.xlsx", "*sfl scup bsb*.xlsx"]},
        {"id": "lw_conv", "stage": "sim", "label": "L_W_Conversion.csv",
         "files": ["l_w_conversion.csv"]},

        # ---- MRIP aggregates written by the Stata calibration ----
        {"id": "mrip_dtrip_agg", "stage": "calib",
         "label": "mrip_dtrip_calib_*.dta\n(state / mode / wave / month)",
         "files": ["mrip_dtrip_calib_*.dta"]},
        {"id": "mrip_catch_agg", "stage": "calib",
         "label": "mrip_catch_calib_*.dta\n(state / mode / wave)",
         "files": ["mrip_catch_calib_*.dta"]},
        {"id": "mrip_processed", "stage": "calib",
         "label": "baseline_ / projected_\nmrip_catch_processed.xlsx",
         "files": ["baseline_mrip_catch_processed.xlsx", "projected_mrip_catch_processed.xlsx"]},

        # ---- Effort calendar ----
        {"id": "dtrips_calib", "stage": "calib",
         "label": "directed_trips_calibration_<ST>\n.csv / .fst",
         "files": ["directed_trips_calibration_*.csv", "directed_trips_calibration_*.fst",
                   "directed_trips_calibration_*.feather",
                   "directed_trips_imputations_*.dta"]},
        {"id": "cal_adj", "stage": "calib",
         "label": "proj_year_calendar_adjustments_<ST>.csv",
         "files": ["proj_year_calendar_adjustments_*.csv"]},

        # ---- Costs and preferences ----
        {"id": "trip_costs", "stage": "calib", "label": "trip_costs.dta",
         "files": ["trip_costs.dta"]},
        {"id": "pref_params", "stage": "calib", "label": "preference_params.dta",
         "files": ["preference_params.dta"]},
        {"id": "angler_dems", "stage": "calib", "label": "angler_dems.dta",
         "files": ["angler_dems.dta"]},

        # ---- Catch draws. raw = copula output, plain = expanded to trips ----
        {"id": "calib_draws_raw", "stage": "calib",
         "label": "calib_catch_draws_raw_<ST>_<i>.dta\n(copula output)",
         "files": ["calib_catch_draws_raw_*.dta"]},
        {"id": "calib_draws", "stage": "calib",
         "label": "calib_catch_draws_<ST>_<i>\n.dta / .fst",
         "files": ["calib_catch_draws_*.dta", "calib_catch_draws_*.fst"]},
        {"id": "proj_draws_raw", "stage": "proj",
         "label": "proj_catch_draws_raw_<ST>_<i>.dta\n(copula output)",
         "files": ["proj_catch_draws_raw_*.dta"]},
        {"id": "proj_draws", "stage": "proj",
         "label": "proj_catch_draws_<ST>_<i>\n.dta / .fst / .feather",
         "files": ["proj_catch_draws_*.dta", "proj_catch_draws_*.fst",
                   "proj_catch_draws_*.feather"]},

        # ---- Simulated totals and comparisons ----
        {"id": "sim_totals", "stage": "calib",
         "label": "simulated_catch_totals.dta\n(+ _totals3, projected means)",
         "files": ["simulated_catch_totals*.dta", "simulated_projected_catch_means*.dta"]},

        # ---- Catch-at-length ----
        {"id": "baseline_cal", "stage": "catlen",
         "label": "baseline_catch_at_length\n.csv / _region.dta / _state.csv",
         "files": ["baseline_catch_at_length*.csv", "baseline_catch_at_length*.dta",
                   "baseline_observed_catch_at_length.csv"]},
        {"id": "projected_cal", "stage": "catlen",
         "label": "projected_catch_at_length.csv\n(+ _state, _new)",
         "files": ["projected_catch_at_length*.csv", "proj_catch_at_length_state.csv"]},

        # ---- R calibration outputs ----
        {"id": "calib_comparison", "stage": "sim", "label": "calibration_comparison.fst",
         "files": ["calibration_comparison.fst"]},
        {"id": "calib_stats", "stage": "sim",
         "label": "calibrated_model_stats\n.fst / .xlsx / .rds",
         "files": ["calibrated_model_stats*.fst", "calibrated_model_stats*.xlsx",
                   "calibrated_model_stats*.csv", "calibrated_model_stats*.rds"]},
        {"id": "base_outcomes", "stage": "sim",
         "label": "base_outcomes_<ST>_<md>_<i>\n+ n_choice_occasions_<ST>_<md>_<i>",
         "files": ["base_outcomes*", "n_choice_occasions*"]},
        {"id": "good_draws", "stage": "standalone",
         "label": "calibration_good_draws\n.xlsx (+ _extras)",
         "files": ["calibration_good_draws*.xlsx"]},

        # ---- Shiny ----
        {"id": "saved_regs", "stage": "shiny",
         "label": "saved_regs/regs_<Run_Name>.csv",
         "files": ["*regs_*.csv", "saved_regs/*"]},
        {"id": "outputs", "stage": "shiny",
         "label": "output/output_<ST>_<Run_Name>_<time>.csv",
         "files": ["output*.csv", "output/*"]},
        {"id": "rdb_rds", "stage": "standalone",
         "label": "rdb_catch_per_trip_<date>.Rds",
         "files": ["rdb_catch_per_trip*.rds", "rdb_sim_catch_per_trip.dta"]},
        {"id": "figures", "stage": "calib", "label": "figures (.png)",
         "files": ["*.png"]},
    ],

    # --- Stata globals that stand for a whole set of files -----------------
    "macros": {
        "triplist": "mrip_lists",
        "catchlist": "mrip_lists",
        "b2list": "mrip_lists",
        "sizelist": "mrip_lists",
    },

    # --- Data files to leave off entirely ----------------------------------
    "skip_data": [
        "*.ster",          # saved estimation results, handled as an extra node
    ],

    # --- Boxes that are not files or scripts -------------------------------
    "extra_nodes": [
        {"id": "gdrive_in",  "label": "Google Drive\n(mounted at D:)",              "type": "external", "stage": "acquire"},
        {"id": "gdrive_out", "label": "Google Drive\n(rec dashboard folder)",       "type": "external", "stage": "standalone"},
        {"id": "azure",      "label": "Azure Storage queue\n(worker picks up run)", "type": "external", "stage": "shiny"},
        # The 2022 choice experiment fit. Not a data extension the parser
        # recognizes (.ster), and the code that would rebuild it is commented
        # out, so nothing in the repo produces it.
        {"id": "ce_fit", "label": "m0_SFSBSB.ster\n(2022 choice experiment fit,\nno script regenerates it)",
         "type": "data", "stage": "calib"},
    ],

    # --- Arrows the code cannot show us ------------------------------------
    "extra_edges": [
        {"from": "gdrive_in", "to": "get_assessment", "kind": "reads"},
        {"from": "rdb_rds", "to": "gdrive_out", "kind": "writes"},
        {"from": "app", "to": "azure", "kind": "writes"},
        {"from": "azure", "to": "run_model", "kind": "inferred", "note": "worker picks up job"},
        {"from": "ce_fit", "to": "angler_prefs", "kind": "reads"},

        # The three entry points are never chained in code. These arrows are
        # the manual ordering an operator has to know, and are the single most
        # important thing the diagram can say about this repo.
        {"from": "model_wrapper", "to": "r_wrapper", "kind": "inferred",
         "note": "MANUAL - no code path; operator must run in this order"},
        {"from": "r_wrapper", "to": "run_model", "kind": "inferred",
         "note": "MANUAL - no code path; operator must run in this order"},
    ],

    # --- Arrows to suppress -------------------------------------------------
    "skip_edges": [
        # MRIP_column_cases.do lower-cases the MRIP extracts in place, so its
        # header lists the same files as input and output. Drawn honestly that
        # is a box with an arrow to itself.
        ("mrip_lists", "mrip_col_cases", None, "in-place rewrite"),
        # get_assessment_from_gdrive.do copies the NAA files off Drive. Drive
        # is the real input, so drop the read arrow and keep the write.
        ("naa_files", "get_assessment", None, "Drive is the input, not the local copies"),
        # compare_projection_data_to_MRIP.do rewrites the projection draws in
        # place in its Step 3, stripping unused columns.
        ("proj_draws", "compare_proj", None, "in-place column strip; keep the write arrow"),
    ],

    # --- The panels, in the order they should appear ------------------------
    "stages": [
        ("setup",      "STAGE 0 - Setup & orchestration (3 UNCHAINED entry points)"),
        ("acquire",    "STAGE 1-3 - Pull raw data (assessment + MRIP)"),
        ("calib",      "STAGE 4-10 - Calibration (effort, costs, preferences, catch-per-trip)"),
        ("catlen",     "STAGE 11-12 - Catch-at-length (baseline + projection)"),
        ("proj",       "STAGE 13 - Projection catch-per-trip (one meta-toggle)"),
        ("sim",        "R CALIBRATION & PROJECTION (Code/sim)"),
        ("shiny",      "SEPARATE PATH - Shiny decision-support tool & projection"),
        ("standalone", "NOT WRAPPER-CONTROLLED - standalone / manual scripts"),
    ],
}


# ==============================================================================
# THE LAYOUT CHOICES -- where the panels land on the page
# ==============================================================================
# Deliberately NOT part of CURATION: nothing here changes what the diagrams
# depict (no box, arrow or label), only the geometry of where panels are
# drawn. Read by rdm_diagrams/layout.py; see DIAGRAM_LAYOUT_PLAN.md Phase 3
# for why these two pins exist and what they cost.

LAYOUT = {
    # Drawn as one contiguous block, alone in a band at the top of the page:
    # the reader's eye should start at the entry points and the raw-data pulls.
    "top_group": ("setup", "acquire"),
    # Drawn in a band of its own at the bottom: the Shiny decision-support
    # tool is where the pipeline's results end up in front of a user.
    "last_stage": "shiny",
}


# ==============================================================================
# THE PROJECT RECORD
# ==============================================================================
# Everything the shared code needs to know about this project. Settings not
# named here take the defaults in rdm_diagrams/config.py -- which folders to
# skip, which extensions count as data, and where the master Stata wrapper
# sits inside the repository.

from pathlib import Path

# Path(__file__).resolve() gets the full path of groundfish.py
# .parents[2] moves up 3 levels from the file (or 2 levels up from its directory):
#   parents[0] -> ...\projects
#   parents[1] -> ...\recDST_DataFlow
#   parents[2] -> ...\RecreationalDST
REPO_PATH = Path(__file__).resolve().parents[2] / "flukeRDM"



PROJECT = Project(
    key="fluke",
    display_name="flukeRDM",
    output_prefix="FlukeRDM_",
    repo=str(REPO_PATH),
    curation=CURATION,
)
