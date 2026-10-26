#import csv
#import statistics
import sys
from pathlib import Path
import time

# import numpy as np
#import pandas as pd

from pace_learn import full_race_data, build_records

# script 3, evaluating forecast accuracy compared to baselines from `pace_learn.py`

project_folder = Path(__file__).resolve().parent
source_data_folder = project_folder / "data" / "source_data"
race_default = "Le_Mans_2026"
folder_default = source_data_folder / race_default

csv_files = list(folder_default.glob("*.csv"))
if len(csv_files) != 1:
    raise FileNotFoundError(
        f"Expected exactly one CSV in {source_data_folder / race_default}, found {len(csv_files)}"
    )
default_path = csv_files[0]

def attach_target_laps(origins, race_data):

    target_results = race_data[
        ["RACE_ID", "NUMBER", "LAP_NUMBER", "LAP_TIME_SEC", "FLAG_AT_FL", "CROSSING_FINISH_LINE_IN_PIT", "PIT_TIME"]
    ].copy()

    # update to clarify the targets so pandas can merge columns to origin

    target_results = target_results.rename(
        columns = {
            "LAP_NUMBER": "TARGET_LAP_NUMBER",
            "LAP_TIME_SEC": "TARGET_LAP_TIME_SEC",
            "FLAG_AT_FL": "TARGET_FLAG_AT_FL",
            "CROSSING_FINISH_LINE_IN_PIT": "TARGET_PIT_CROSSING",
            "PIT_TIME": "TARGET_PIT_TIME"
        }
    )

    # attach target results belonging to each prediction's target lap

    eval_origins = origins.merge(
        target_results,
        on = ["RACE_ID", "NUMBER", "TARGET_LAP_NUMBER"],
        how = "left",
        validate = "one_to_one",
    )

    return eval_origins

def calc_prediction_errors(eval_origins):

    results = eval_origins.copy()

    results["SIGNED_ERROR_SEC"] = (
        results["TARGET_LAP_TIME_SEC"] - results["PACE_BASELINE_SEC"]
    )
    # pos error, lap took longer than predicted
    # neg error, lap took less time than predicted

    results["ABS_ERROR_SEC"] = results["SIGNED_ERROR_SEC"].abs()

    results["SCORABLE"] = (
        results["PACE_BASELINE_SEC"].notna()
        & results["TARGET_LAP_TIME_SEC"].notna()
    )

    return results

def result_summary(results):
    scored = results.loc[results["SCORABLE"]]

    observed_ct = results["TARGET_LAP_TIME_SEC"].notna().sum()
    scored_ct = results["SCORABLE"].sum()

    coverage = None
    mean_abs_error = None
    
    if not observed_ct:
        print("No observations to be counted")
    else:
        coverage = scored_ct/observed_ct

    if not scored_ct:
        print("No forecasts available to be evaluated")
    else:
        mean_abs_error = scored["ABS_ERROR_SEC"].mean()

    return mean_abs_error, coverage, observed_ct, scored_ct

def label_target_cond(results):

    labeled = results.copy()

    # return true if all the conditions are true, which requires
    # no events to occur on the target lap, so the target lap
    # would meet all conditions

    labeled["TARGET_PASSES_EVENT_CHECKS"] = (
        labeled["TARGET_LAP_TIME_SEC"].notna()
        & labeled["TARGET_FLAG_AT_FL"].isin(["GF", "FF"])
        & labeled["TARGET_PIT_CROSSING"].isna()
        & labeled["TARGET_PIT_TIME"].isna()
    )

    return labeled



def main():

    path = Path(sys.argv[1]) if len(sys.argv) > 1 else default_path
    race_id = sys.argv[2] if len(sys.argv) > 2 else race_default

    """ DATA LOADING AND CLEANING """

    (
        print(
            "Usage: python load_data.py <path_to_csv> <race_id>\nUsing default Race ID 'Le_Mans_2026'\n"
            f"Using default CSV Path [{default_path}]\n"
        )
        if len(sys.argv) < 3
        else None
    )

    race_data = full_race_data(race_id, path)
    """
    print("")
    print(race_data.head())
    """

    """ DATA ANALYSIS """

    origins, _, _ = build_records(race_data)
    eval_origins = attach_target_laps(origins, race_data)
    eval_origins = calc_prediction_errors(eval_origins)
    eval_origins = label_target_cond(eval_origins)

    """
    print("\nTESTING: Origins header with attached target data:")
    #print(eval_origins.head())

    sample = eval_origins.loc[
            eval_origins["NUMBER"].eq("51")
            & eval_origins["COMPLETED_LAP_NUMBER"].between(200, 220),
            ["COMPLETED_LAP_NUMBER",
            "TARGET_LAP_NUMBER",
            "PACE_BASELINE_SEC",
            "TARGET_LAP_TIME_SEC",
            "SIGNED_ERROR_SEC",
            "ABS_ERROR_SEC",
            "SCORABLE",
            "TARGET_FLAG_AT_FL",
            "TARGET_PIT_CROSSING",
            "TARGET_PIT_TIME",
            "TARGET_PASSES_EVENT_CHECKS"]
        ]
    
    print(sample)
    """

    print("\nTESTING: Result summaries, scorable targets passing event checks:\n")

    passing_targets = eval_origins.loc[
        eval_origins["TARGET_PASSES_EVENT_CHECKS"]
    ]

    eval_targets = passing_targets.loc[
        passing_targets["SCORABLE"]
    ]

    mae, coverage, obs_ct, scored_ct = result_summary(eval_targets)

    mae_text = "unavailable" if mae is None else f"{mae:.5f} seconds"
    coverage_text = (
        "unavailable" if coverage is None else f"{coverage:.2%}"
    )

    print(f"MAE: {mae_text}, Coverage: {coverage_text}")
    print(f"Laps Observed: {obs_ct}, Laps Scored: {scored_ct}")

    largest_error = eval_targets.sort_values(
        "ABS_ERROR_SEC",
        ascending = False,
    ).head(10)

    col2 = [
        "NUMBER",
        "COMPLETED_LAP_NUMBER",
        "TARGET_LAP_NUMBER",
        "PACE_BASELINE_SEC",
        "SIGNED_ERROR_SEC",
        "ABS_ERROR_SEC",
        "PACE_SOURCE_LAPS",
    ]

    print("\nTESTING: 10 Largest absolute error values:")
    print(largest_error[col2].to_string(index=False))

    """ Examination for one large error """

    example = largest_error.iloc[0]
    car = example["NUMBER"]
    target_lap = example["TARGET_LAP_NUMBER"]

    nearby_laps = race_data.loc[
        race_data["NUMBER"].eq(car)
        & race_data["LAP_NUMBER"].between(
            target_lap - 3,
            target_lap + 2
        ),
        [
            "LAP_NUMBER",
            "LAP_TIME_SEC",
            "ELAPSED_SEC",
            "DRIVER_NUMBER",
            "FLAG_AT_FL",
            "CROSSING_FINISH_LINE_IN_PIT",
            "PIT_TIME",
        ],
    ].sort_values("LAP_NUMBER")

    print(nearby_laps.to_string(index=False))

if __name__ == "__main__":

    start = time.perf_counter()
    main()
    end = time.perf_counter()

    runtime = end - start
    print(f"Runtime: {runtime:.4f} seconds")