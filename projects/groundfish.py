"""
groundfish.py
================================================================================
Everything that is specific to the GroundfishRDM project, and nothing else.

Two kinds of thing live here:

  * The Project record at the BOTTOM of the file: where the source code sits,
    what to call the project in titles, and what to put on the front of the
    picture filenames.

  * The CURATION dictionary: the hand-maintained decisions about how this
    project's pipeline should be DRAWN. Everything above it in the toolchain
    reads the code; this is the part a human maintains.

The shared code that reads all of this is in rdm_diagrams/. Nothing there names
a project, so a change here cannot affect any other project's diagrams.

To draw these diagrams:  python make_groundfish_diagrams.py
================================================================================
"""

from rdm_diagrams.config import Project


# ==============================================================================
# THE CURATION LAYER -- the hand-maintained part
# ==============================================================================
# The extractor reads GroundfishRDM's source code and works out the pipeline for
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
        # Stage 0: the two wrappers and their setup helpers.
        "model_wrapper.do":            ("model_wrapper", "model_wrapper.do\n(MASTER WRAPPER - Stata)", "setup", False),
        "developer_setup_stata.do":    ("dev_setup_stata", None, "setup", False),
        "R code wrapper.R":            ("r_wrapper", "R code wrapper.R\n(R WRAPPER)", "setup", False),
        "developer_setup.R":           ("dev_setup_r", None, "setup", False),

        # Stage 1-2: pulling in raw data.
        "get_assessment_from_gdrive.do": ("get_assessment", None, "acquire", False),
        "get_mrip_oracle.R":             ("get_mrip", None, "acquire", False),
        "tidyup_mrip_data_fromR.do":     ("tidyup_mrip", None, "acquire", False),
        "MRIP_column_cases.do":          ("mrip_col_cases", None, "acquire", True),
        "MRIP_lists.do":                 ("mrip_lists_do", None, "acquire", True),

        # Stage 5-11: the main calibration chain.
        "directed_trips_calibration.do":      ("dtrips", None, "calib", False),
        "set_regulations.do":                 ("set_regs", "set_regulations.do\n(nested call - edit yearly)", "calib", False),
        "survey_trip_costs.do":               ("trip_costs_do", None, "calib", False),
        "estimate_angler_preferences.do":     ("prefs_do", None, "calib", False),
        "calibration_catch_per_trip_part1.do": ("cpt1", None, "calib", False),
        "copula_modeling_calibration.R":      ("copula", None, "calib", False),
        "calibration_catch_per_trip_part2.do": ("cpt2", None, "calib", False),
        "additional_angler_dems.do":          ("add_dems", None, "calib", False),
        "compare_calibration_data_to_MRIP.do": ("compare_mrip", None, "calib", False),

        # Stage 15 & 18: catch-at-length.
        "catch_at_length_calibration.do": ("cal_len", None, "catlen", False),
        "catch_at_length_projection.do":  ("proj_len", None, "catlen", False),

        # Stage 12-14, 16-17: dashboard prep and the Google Drive pushes.
        "rdb_processing_catch_per_trip.do": ("rdb_cpt", None, "dashboard", False),
        "rdb_catch_per_trip_to_drive.R":    ("rdb_cpt_drive", None, "dashboard", False),
        "rdb_catch_at_length.do":           ("rdb_cal", None, "dashboard", False),
        "rdb_catch_at_len_to_drive.R":      ("rdb_cal_drive", None, "dashboard", False),

        # Stage 19: the R simulation stage.
        "calibrate_rec_catch0.R":  ("rec0", "calibrate_rec_catch0.R\n(STEP 1 - pass 0)", "sim", False),
        "calibration_routine.R":   ("routine", "calibration_routine.R\n(STEP 2 - driver)", "sim", False),
        "calibrate_rec_catch1.R":  ("rec1", "calibrate_rec_catch1.R\n(re-sourced inside loops)", "sim", False),
        "export_to_GoogleDrive.R": ("export_gdrive", None, "sim", False),

        # The separate Shiny / projection path.
        "app.R":                        ("app", "app.R\n(SHINY DECISION-SUPPORT TOOL)", "shiny", False),
        "Run_Model.R":                  ("run_model", "Run_Model.R\n(command-line entry point)", "shiny", False),
        "model_run.R":                  ("model_run", "RecDST/model_run.R", "shiny", False),
        "predict_rec_catch_functions.R": ("predict_fns", None, "shiny", False),

        # Standalone: present in the repo, but no wrapper runs them.
        "compile_input_data_for_dashboard.do": ("compile_dash", "compile_input_data_for_dashboard.do\n(hardcoded paths)", "standalone", False),
        "get_cod_assessment_data.R":     ("get_cod", None, "standalone", False),
        "get_haddock_assessment_data.R": ("get_hadd", None, "standalone", False),
        "RP_data_analysis.do":           ("rp_analysis", None, "standalone", False),
        "baseline_and_projected_NAL.do": ("base_nal", None, "standalone", False),
        "get_commercial_landings.R":     ("comm_landings", None, "standalone", False),
        "required_packages.R":           ("req_pkgs", "required_packages.R\n(run once, by hand)", "standalone", False),
    },

    # Scripts in the repo that deliberately get no box. These are one-off
    # developer conveniences (set up a Google Drive token, install a particular
    # WHAM build, hunt for a file id) or, in flukeapp.R's case, belong to the
    # other project entirely. They are real code; they are just not pipeline.
    "skip_scripts": {
        "fetch_NAA_from_google.R",
        "find_files_on_googledrive.R",
        "googledrivesetup.R",
        "naa_helpers.R",
        "wham_version_installer.R",
        "flukeapp.R",
    },

    # Calls that exist in the code but are left off the picture. Every one of
    # these is boilerplate: near enough every R script begins by sourcing
    # developer_setup.R to find out where the data lives. Drawing all of them
    # would add a dozen arrows that say nothing about the flow of data.
    # Format: (calling script, called script).
    "skip_calls": {
        ("copula_modeling_calibration.R", "developer_setup.R"),
        ("get_mrip_oracle.R", "developer_setup.R"),
        ("rdb_catch_per_trip_to_drive.R", "developer_setup.R"),
        ("rdb_catch_at_len_to_drive.R", "developer_setup.R"),
        ("get_cod_assessment_data.R", "naa_helpers.R"),
        ("get_haddock_assessment_data.R", "naa_helpers.R"),
    },

    # --- Data files --------------------------------------------------------
    # One entry per BOX. "files" lists the real filenames that box stands for;
    # a * in a pattern matches a run number, wave number or date stamp.
    #
    # This is where "three files, one box" gets decided. The pipeline writes
    # mrip_dtrip_by_mode.dta, _by_mode_month.dta and _by_mode_season.dta as a
    # set, always together, always consumed together -- so they get one box.
    # Likewise calib_catch_draws_1.dta ... _101.dta is 101 real files and one
    # idea.
    "data_groups": [
        {"id": "naa_files", "stage": "acquire",
         "label": "WGOM_Cod / GOM_Haddock\nhistorical + projected NAA .dta",
         "files": ["WGOM_Cod_historical_NAA*.dta", "WGOM_Cod_projected_NAA*.dta",
                   "GOM_Haddock_historical_NAA*.dta", "GOM_Haddock_projected_NAA*.dta",
                   "WGOM_Cod_historical_NAA*.Rds", "WGOM_Cod_projected_NAA*.Rds",
                   "GOM_Haddock_historical_NAA*.Rds", "GOM_Haddock_projected_NAA*.Rds",
                   "*NAA_*.dta"]},
        {"id": "mrip_raw", "stage": "acquire",
         "label": "mrip_trip / catch /\nsize / size_b2 .dta",
         "files": ["mrip_trip.dta", "mrip_catch.dta", "mrip_size.dta",
                   "mrip_size_b2.dta", "mrip_pull*.Rds"]},
        {"id": "mrip_lists", "stage": "acquire",
         "label": "$triplist $catchlist\n$b2list $sizelist\n(tidied MRIP extracts)",
         "files": ["trip_*.dta", "catch_*.dta", "size_*.dta", "size_b2_*.dta"]},

        {"id": "site_list", "stage": "calib", "label": "MRIP_COD_ALL_SITE_LIST.csv",
         "files": ["MRIP_COD_ALL_SITE_LIST.csv"]},
        {"id": "dtrip_draws", "stage": "calib", "label": "directed_trip_draws.csv",
         "files": ["directed_trip_draws.csv"]},
        {"id": "cal_adj", "stage": "calib", "label": "next_year_calendar_adjustments.csv",
         "files": ["next_year_calendar_adjustments.csv"]},
        {"id": "open_season", "stage": "calib", "label": "cod_open_season_dates.dta",
         "files": ["cod_open_season_dates.dta"]},
        {"id": "mrip_dtrip", "stage": "calib",
         "label": "mrip_dtrip_by_mode /\n_month / _season .dta",
         "files": ["mrip_dtrip_by_mode.dta", "mrip_dtrip_by_mode_month.dta",
                   "mrip_dtrip_by_mode_season.dta"]},
        {"id": "exp_survey", "stage": "calib",
         "label": "gulf_atl_2022.dta\nprim1.dta, prim2.dta",
         "files": ["gulf_atl_2022.dta", "prim1.dta", "prim2.dta",
                   "atl_states_2017_expsurvey.dta", "trip_master_final.dta"]},
        {"id": "trip_costs", "stage": "calib", "label": "trip_costs.dta",
         "files": ["trip_costs.dta"]},
        {"id": "ce_survey", "stage": "calib", "label": "CE_survey_data.dta",
         "files": ["CE_survey_data.dta"]},
        {"id": "pref_params", "stage": "calib", "label": "preference_params.dta",
         "files": ["preference_params.dta"]},
        {"id": "baseline_xlsx", "stage": "calib",
         "label": "baseline_mrip_catch_processed\n.xlsx / .dta",
         "files": ["baseline_mrip_catch_processed.xlsx",
                   "baseline_mrip_catch_processed.dta"]},
        {"id": "mrip_catch_by", "stage": "calib",
         "label": "mrip_catch_by_mode /\n_month / _season .dta",
         "files": ["mrip_catch_by_mode.dta", "mrip_catch_by_mode_month.dta",
                   "mrip_catch_by_mode_season.dta"]},
        {"id": "draws_raw", "stage": "calib", "label": "calib_catch_draws_raw_<i>.dta",
         "files": ["calib_catch_draws_raw_*.dta"]},
        {"id": "fes", "stage": "calib", "label": "fes_person_final_2023<w>.dta\n(waves 1-6)",
         "files": ["fes_person_final_*.dta"]},
        {"id": "angler_dems", "stage": "calib", "label": "angler_dems.dta",
         "files": ["angler_dems.dta"]},
        {"id": "draws", "stage": "calib", "label": "calib_catch_draws_<i>.dta\n(i = 1..$ndraws)",
         "files": ["calib_catch_draws_*.dta", "calib_catch_draws_*.xlsx"]},
        {"id": "choice_dems", "stage": "calib", "label": "choice_exp_angler_dems.dta",
         "files": ["choice_exp_angler_dems.dta"]},
        {"id": "sim_totals3", "stage": "calib", "label": "simulated_catch_totals3.dta",
         "files": ["simulated_catch_totals3.dta"]},
        {"id": "sim_totals", "stage": "calib", "label": "simulated_catch_totals.dta",
         "files": ["simulated_catch_totals.dta"]},
        {"id": "sim_totals_len", "stage": "calib",
         "label": "simulated_catch_totals\n_for_catch_length.dta",
         "files": ["simulated_catch_totals_for_catch_length.dta"]},
        {"id": "figures", "stage": "calib", "label": "diagnostic comparison\nfigures (.png)",
         "files": ["*.png"]},

        {"id": "bcal_obs", "stage": "catlen", "label": "baseline_catch_at_length_observed.csv",
         "files": ["baseline_catch_at_length_observed.csv"]},
        {"id": "bcal", "stage": "catlen", "label": "baseline_catch_at_length.csv",
         "files": ["baseline_catch_at_length.csv"]},
        {"id": "trawl", "stage": "catlen", "label": "NEFSC_cruises.csv\nNEFSC_trawl_cod / _hadd.csv",
         "files": ["NEFSC_cruises.csv", "NEFSC_trawl_cod.csv", "NEFSC_trawl_hadd.csv"]},
        {"id": "proj_cal", "stage": "catlen", "label": "projected_catch_at_length.csv",
         "files": ["projected_catch_at_length.csv"]},

        {"id": "rdb_cpt_dta", "stage": "dashboard", "label": "rdb_sim_catch_per_trip.dta",
         "files": ["rdb_sim_catch_per_trip.dta"]},
        {"id": "rdb_cpt_rds", "stage": "dashboard", "label": "rdb_catch_per_trip_<date>.Rds",
         "files": ["rdb_catch_per_trip*.Rds"]},
        {"id": "rdb_cal_dta", "stage": "dashboard", "label": "rdb_cat_len.dta",
         "files": ["rdb_cat_len.dta"]},
        {"id": "rdb_cal_rds", "stage": "dashboard", "label": "rdb_catch_at_length_<date>.Rds",
         "files": ["rdb_catch_at_length*.Rds"]},

        {"id": "discard_csv", "stage": "sim", "label": "Discard_Mortality.csv",
         "files": ["Discard_Mortality.csv"]},
        {"id": "fst_inputs", "stage": "sim",
         "label": ("FST copies of the inputs\n(directed_trip_draws.fst,\n"
                   "calib_catch_draws_<i>.fst,\nDiscard_Mortality.fst,\ncalendar_adj.fst)"),
         "files": ["directed_trip_draws.fst", "calib_catch_draws_*.fst",
                   "Discard_Mortality.fst", "calendar_adj.fst"]},
        {"id": "calib_comp", "stage": "sim", "label": "calibration_comparison.fst",
         "files": ["calibration_comparison.fst"]},
        {"id": "model_stats", "stage": "sim", "label": "calibrated_model_stats.fst",
         "files": ["calibrated_model_stats.fst"]},
        {"id": "base_outcomes", "stage": "sim",
         "label": "base_outcomes_<s>_<md>_<i>.fst\nn_choice_occasions_<s>_<md>_<i>.fst",
         "files": ["base_outcomes*.fst", "n_choice_occasions*.fst"]},

        {"id": "saved_regs", "stage": "shiny", "label": "saved_regs/regs_<Run_Name>.csv",
         "files": ["regs_*.csv", "saved_regs/*.csv"]},
        {"id": "output_csv", "stage": "shiny",
         "label": "output/output_<name>_<time>.csv\ndirected_trips_before/after.csv",
         "files": ["output_*.csv", "directed_trips_before.csv",
                   "directed_trips_after.csv", "output/*.csv"]},

        {"id": "mean_cpt", "stage": "standalone", "label": "mean_catch_per_trip.csv",
         "files": ["mean_catch_per_trip.csv"]},
    ],

    # Some headers name a file only through the Stata global that holds its
    # path -- "Inputs: $triplist, $catchlist" -- so there is no filename to
    # find. model_wrapper.do defines what those globals point at, but the
    # boxes they belong to is still a judgement call, so they are listed here.
    # macro name (no $) -> the box it stands for
    "macros": {
        "triplist": "mrip_lists",
        "catchlist": "mrip_lists",
        "b2list": "mrip_lists",
        "sizelist": "mrip_lists",
    },

    # Data files mentioned in a header that should NOT get a box. These are
    # either the other project's files or side outputs (an OAuth token cache,
    # a commercial-landings extract for a different model) that would clutter
    # the picture without adding a step to the pipeline.
    "skip_data": [
        "commercial_*_removals*.Rds",
        "*Projections_*.Rds",
        "mod_*.rds",
        "waa_pred*.xlsx",
        "*.DAT",
    ],

    # --- Boxes that are not files or scripts -------------------------------
    # Nothing in the code can tell us these exist as separate things: they are
    # places outside the repository that the pipeline talks to.
    "extra_nodes": [
        {"id": "gdrive_in",  "label": "Google Drive\n(mounted at D:)",          "type": "external", "stage": "acquire"},
        {"id": "oracle",     "label": "MRIP Oracle database",                   "type": "external", "stage": "acquire"},
        {"id": "gdrive_out", "label": "Google Drive\n(rec dashboard folder)",   "type": "external", "stage": "dashboard"},
        {"id": "azure",      "label": "Azure Storage queue\n(worker picks up run)", "type": "external", "stage": "shiny"},

        # Not external, but it has to be listed here for the same reason: the
        # one pipeline script with no Inputs:/Outputs: header is
        # estimate_angler_preferences.do, so the survey file it reads is
        # invisible to the extractor. See "extra_edges" below.
        {"id": "ce_survey",  "label": "CE_survey_data.dta", "type": "data", "stage": "calib"},
    ],

    # --- Arrows the code cannot show us ------------------------------------
    # Two sorts live here. The first are the arrows to and from the external
    # boxes above. The second are the "inferred" connections that Task 1
    # flagged: two steps that clearly hand data to each other via a shared
    # folder or a queue message, with no line of code joining them. They are
    # drawn dotted and red precisely because they are unconfirmed.
    "extra_edges": [
        {"from": "gdrive_in", "to": "get_assessment", "kind": "reads"},
        {"from": "oracle", "to": "get_mrip", "kind": "reads"},
        {"from": "rdb_cpt_rds", "to": "gdrive_out", "kind": "writes"},
        {"from": "rdb_cal_rds", "to": "gdrive_out", "kind": "writes"},
        {"from": "export_gdrive", "to": "gdrive_out", "kind": "writes"},
        {"from": "app", "to": "azure", "kind": "writes"},

        {"from": "azure", "to": "run_model", "kind": "inferred", "note": "worker picks up job"},
        {"from": "base_outcomes", "to": "predict_fns", "kind": "inferred", "note": "shared folder"},
        {"from": "draws", "to": "compile_dash", "kind": "inferred", "note": "per-draw xlsx, unconfirmed trigger"},
        {"from": "get_cod", "to": "naa_files", "kind": "inferred", "note": "believed to produce the NAA files"},
        {"from": "get_hadd", "to": "naa_files", "kind": "inferred", "note": "believed to produce the NAA files"},

        # --- Arrows a header states in words but not in filenames -----------
        # These scripts describe their files in prose ("local FST/CSV/XLSX/DTA
        # files in the final_process_* folders", "the same files, overwritten
        # in place"). A human reads that and knows exactly what is meant; a
        # parser has nothing to grab.
        #
        # This list shrinks as headers improve. "R code wrapper.R" used to need
        # an entry here for the FST copies it writes; its Outputs field now
        # names those four files outright, so the extractor finds them itself
        # and the hand-written line was deleted. That is the direction of
        # travel -- fix the header in groundfishRDM/ and delete the entry here.
        {"from": "model_stats", "to": "export_gdrive", "kind": "reads"},
        {"from": "base_outcomes", "to": "export_gdrive", "kind": "reads"},
        {"from": "mrip_raw", "to": "tidyup_mrip", "kind": "reads"},
        {"from": "tidyup_mrip", "to": "mrip_lists", "kind": "writes"},
        {"from": "mrip_lists_do", "to": "mrip_lists", "kind": "writes"},

        # --- The one script with no header block ----------------------------
        # estimate_angler_preferences.do carries no Inputs:/Outputs: comment,
        # so these two arrows are the only ones in the whole diagram that come
        # from nowhere but this list. If a header is ever added to that script,
        # delete these two lines and the extractor will find them itself.
        {"from": "ce_survey", "to": "prefs_do", "kind": "reads"},
        {"from": "prefs_do", "to": "pref_params", "kind": "writes"},
    ],

    # Read/write arrows the headers imply but the picture leaves out, each for
    # a stated reason. Format: (from id, to id, kind or None for any, why).
    "skip_edges": [
        # tidyup_mrip_data_fromR.do rewrites the MRIP extracts in place, so its
        # header lists the same files as both input and output. Drawing that
        # honestly gives a box with an arrow to itself, which tells a reader
        # nothing. The picture instead shows the raw pull going in and the
        # tidied extracts coming out, which is what "tidy up" means to a human.
        ("mrip_lists", "tidyup_mrip", None, "in-place rewrite; raw goes in, tidied comes out"),
        # Same in-place-rewrite story, for the two dead-code scripts. We keep
        # the arrow showing what MRIP_lists.do WOULD produce, and drop the rest.
        ("mrip_lists", "mrip_col_cases", None, "dead code, in-place rewrite"),
        ("mrip_col_cases", "mrip_lists", None, "dead code, in-place rewrite"),
        ("mrip_lists", "mrip_lists_do", None, "dead code; only its output arrow is drawn"),
        ("mrip_raw", "mrip_col_cases", None, "dead code, in-place rewrite"),
        ("mrip_raw", "mrip_lists_do", None, "dead code reading the raw files"),
        ("mrip_col_cases", "mrip_raw", None, "dead code, in-place rewrite"),
        # get_assessment_from_gdrive.do copies NAA files off Drive into the
        # local data folder. Drive is the input box, the local NAA files are
        # the output box -- so the "reads" side is the Drive arrow, not this.
        ("naa_files", "get_assessment", "reads", "the Google Drive box is the input here"),
        # get_cod / get_haddock write NAA files into the repo's input_data
        # folder; the pipeline reads NAA files out of the shared data folder.
        # Almost certainly the same numbers, but nothing in the code joins the
        # two locations, so the connection stays drawn as dotted "inferred".
        ("get_cod", "naa_files", "writes", "unconfirmed hand-off, drawn as inferred instead"),
        ("get_hadd", "naa_files", "writes", "unconfirmed hand-off, drawn as inferred instead"),
        # compile_input_data_for_dashboard.do reads per-draw .xlsx copies of
        # the draw files. Nothing writes those, and nothing calls this script,
        # so the link stays dotted rather than becoming a solid read.
        ("draws", "compile_dash", "reads", "unconfirmed trigger, drawn as inferred instead"),
        # model_run.R writes the output CSVs; app.R reads them. The header of
        # Run_Model.R also mentions them, one level removed.
        ("output_csv", "model_run", "reads", "model_run.R writes these; app.R is the reader"),
        ("saved_regs", "run_model", "reads", "Run_Model.R passes the name through; "
                                             "model_run.R is what opens the file"),
        # app.R lists previously-submitted regulation sets back to the user.
        # That is a convenience in the interface, not a step in the pipeline,
        # and drawing it would reverse the arrow that matters (the app is what
        # PRODUCES a regulation set).
        ("saved_regs", "app", "reads", "UI convenience; the app is the producer here"),
        # "R code wrapper.R" says in its Outputs field that the downstream .fst
        # files are "written by the sourced scripts". True, and the picture
        # credits those scripts -- so the wrapper does not also get the arrow.
        ("r_wrapper", "calib_comp", "writes", "written by calibrate_rec_catch0.R"),
        ("r_wrapper", "model_stats", "writes", "written by calibration_routine.R"),
        ("r_wrapper", "base_outcomes", "writes", "written by calibrate_rec_catch1.R"),
        # predict_rec_catch_functions.R lists everything the projection loads.
        # The picture attributes the shared-folder inputs to model_run.R, its
        # caller, and keeps only the two arrows Task 1 flagged as inferred.
        ("fst_inputs", "predict_fns", "reads", "attributed to its caller, model_run.R"),
        ("model_stats", "predict_fns", "reads", "attributed to its caller, model_run.R"),
        ("discard_csv", "predict_fns", "reads", "attributed to its caller, model_run.R"),
        ("draws", "predict_fns", "reads", "attributed to its caller, model_run.R"),
    ],

    # The panels the boxes are grouped into, top to bottom.
    "stages": [
        ("setup",      "STAGE 0 - Setup & orchestration"),
        ("acquire",    "STAGE 1-2 - Pull raw data (assessment + MRIP)"),
        ("calib",      "STAGE 5-11 - Pre-simulation calibration (Stata + R)"),
        ("catlen",     "STAGE 15 & 18 - Catch-at-length (baseline + projection)"),
        ("dashboard",  "STAGE 12-14, 16-17 - Dashboard prep & Google Drive push"),
        ("sim",        "STAGE 19 - R simulation / calibration routine"),
        ("shiny",      "SEPARATE PATH - Shiny decision-support tool & projection"),
        ("standalone", "NOT WRAPPER-CONTROLLED - standalone / legacy scripts"),
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
    # the reader's eye should start at the wrappers and the raw-data pulls.
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

PROJECT = Project(
    key="groundfish",
    display_name="GroundfishRDM",
    output_prefix="GroundfishRDM_",
    repo=r"C:/Users/minya/Documents/Recreational/groundfishRDM",
    curation=CURATION,

    # No reference_module: the hand-typed snapshot this used to compare
    # against (generate_dataflow_diagram_from_DATAFLOW.py, in
    # groundfish_diagrams/) was deleted, and groundfish_diagrams/ along with
    # it. --check now falls back to the same "nothing configured" path fluke
    # already uses -- it prints the extraction report with no comparison.
)
