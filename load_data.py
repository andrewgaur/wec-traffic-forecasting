import csv
import sys
from hashlib import sha256
from pathlib import Path

import numpy as np
import pandas as pd

project_folder = Path(__file__).resolve().parent
source_data_folder = project_folder / "data" / "source_data"
race = "Le_Mans_2026"
folder = source_data_folder / race

csv_files = list(folder.glob("*.csv"))
if len(csv_files) != 1:
    raise FileNotFoundError(
        f"Expected exactly one CSV in {source_data_folder / race}, found {len(csv_files)}"
    )
lm_path = csv_files[0]

# load race data from raw csv file, add race id, return as a dataframe


def load_race_data(race_id, path):
    raw_race_data = pd.read_csv(path, sep=";", encoding="utf-8", dtype=str)
    raw_race_data.columns = raw_race_data.columns.str.strip()
    race_df = pd.DataFrame(raw_race_data)

    # add race id
    race_df.insert(0, "RACE_ID", race_id)

    return race_df


## source manifest??
# should include event, session, source URL, retrieval date, local path, etc
# no clue if this is the right process


def save_source_manifest(source_id, race_id, session, source_url, retrieval_date, path):
    with open("metadata/source_manifest.csv", "a", newline="") as file:
        writer = csv.writer(file)

        hash = sha256(Path(path).read_bytes()).hexdigest()
        writer.writerow(
            [source_id, race_id, session, source_url, retrieval_date, path, hash]
        )


# translate lap time and elapsed time to seconds
# convert lap number and driver number to numeric
# replace NaN with None


def parse_duration_seconds(df):

    df = df.replace({np.nan: None})

    for column in ("LAP_TIME", "ELAPSED"):

        times = df[column].str.strip()
        times = times.mask(times.str.count(":").eq(1), "00:" + times)

        df[f"{column}_SEC"] = pd.to_timedelta(times).dt.total_seconds()

    for column in ("LAP_NUMBER", "DRIVER_NUMBER"):
        df[column] = pd.to_numeric(df[column], errors="coerce")

    return df


# clean lap records removing duplicates based on race, car number, and lap number
def clean_lap_records(df):

    # check repeated records
    repeat_records = df.duplicated(
        subset=["RACE_ID", "NUMBER", "LAP_NUMBER"], keep="first"
    )

    if repeat_records.any():
        print(f"Dropping {repeat_records.sum()} repeated lap records.")
        df = df[~repeat_records]
    else:
        print("No repeated lap records found.")

    # check missing timing data and identifiers
    # lap time
    laps_all_float = df["LAP_TIME_SEC"].apply(lambda time: isinstance(time, float))
    missing_lap_time_id = {
        row["RACE_ID"]: row["LAP_NUMBER"] for _, row in df[~laps_all_float].iterrows()
    }

    if not laps_all_float.all():
        print(f"Missing lap time for the following laps: {missing_lap_time_id}")
        # df = df[lap_time_float]

    if not df["NUMBER"].notnull().all():
        missing_car_id = {
            row["RACE_ID"]: row["LAP_NUMBER"]
            for _, row in df[df["NUMBER"].isnull()].iterrows()
        }
        print(f"Missing car number for the following laps: {missing_car_id}")
        # df = df[df["NUMBER"].notnull()]

    # additional cleaning audits

    for col in ("LAP_TIME_SEC", "ELAPSED_SEC", "NUMBER", "LAP_NUMBER"):

        missing = df[col].isna()
        if missing.any():
            print(f"Missing data for column '{col}': {missing.sum()} rows")
            print(df.loc[missing, ["RACE_ID", "NUMBER", "LAP_NUMBER", col]].head())
        else:
            print(f"No missing data found in column '{col}'")

        """
        if not df[col].notnull().all():
            print(f"Missing data for column '{col}': {df[col].isnull().sum()}")

            df = df[df[col].notnull()]
        """

    # column-specific validity checks
    for col in df.columns:
        match col:
            case "LAP_TIME_SEC":
                if (df[col] <= 0).any() or np.isinf(df[col]).any():
                    print(
                        f"Invalid negative, zero, or infinite values found in column '{col}'"
                    )

            case "ELAPSED_SEC":
                if np.isinf(df[col]).any():
                    print(f"Invalid infinite values found in column '{col}'")

                ordered = df.sort_values(["RACE_ID", "NUMBER", "LAP_NUMBER"])
                ordered_by_car = ordered.groupby(["RACE_ID", "NUMBER"])

                elapsed_diff = ordered_by_car["ELAPSED_SEC"].diff()
                lap_diff = ordered_by_car["LAP_NUMBER"].diff()

                diff = (elapsed_diff - ordered["LAP_TIME_SEC"]).abs()
                invalid = lap_diff.eq(1) & diff.gt(0.002)

                if invalid.any():
                    print("Invalid lap time data found for the following laps:")
                    print(
                        ordered.loc[
                            invalid,
                            [
                                "RACE_ID",
                                "NUMBER",
                                "LAP_NUMBER",
                                "LAP_TIME_SEC",
                                "ELAPSED_SEC",
                            ],
                        ]
                    )

                if lap_diff.gt(1).any():
                    print("Non-consecutive laps found for the following cars:")
                    print(
                        ordered.loc[lap_diff > 1, ["RACE_ID", "NUMBER", "LAP_NUMBER"]]
                    )

                if (elapsed_diff <= 0).any():
                    print("Elapsed time did not strictly increase for following laps:")
                    print(
                        ordered.loc[
                            elapsed_diff <= 0,
                            ["RACE_ID", "NUMBER", "LAP_NUMBER", "ELAPSED_SEC"],
                        ]
                    )

            case "LAP_NUMBER":
                if (df[col] <= 0).any() or (
                    df[col].map(lambda row: type(row) is not int)
                ).any():
                    print(
                        f"Invalid non-positive or non-integer values found in column '{col}'"
                    )

    return df


def make_race_splits():
    r"""
    at the moment, manually defines and returns:

    `races`: dictionary keyed by race id containing race csv paths as the value

    `race_ids`: list of race ids

    `race_csvs`: list of race csv paths

    `train_races`: dictionary of designated training race ids and their csv file paths

    `test_races`: dictionary of designated testing race ids and their csv file paths
    """

    # race_csvs contains a list of paths to the csv files for each race
    # we can now designate, load, and clean them

    proj_folder = Path(__file__).resolve().parent
    source_data = proj_folder / "data" / "source_data"

    # source data folder should only ever contain race folders, no other files
    # so race_folders should only contain folders, no files

    """
    Following 21 lines are currently unused, previously used to compile a list of race data
    folders/files in source_data. Currently irrelevant since I'm listing the races
    and paths manually. May change in the future.
    """
    # race_folders = list(source_data.glob("*"))
    # races = []
    # race_csvs = []

    # this was either incorrect or was general for any races
    # and I changed it to manually use Le Mans and Imola
    # could be revised later when using more data
    """
    for folder in race_folders:
        csv_files = list(folder.glob("*.csv"))
        if len(csv_files) != 1:
            raise FileNotFoundError(
                f"Expected exactly one CSV file in {folder}, found {len(csv_files)}"
            )

        races.append(folder.name)
        race_csvs.append(Path(csv_files[0]).resolve())

    if len(race_csvs) != len(race_folders):
        raise FileNotFoundError(
            f"Expected exactly one CSV file in each race folder",
            f"found {len(race_csvs)} races and {len(race_folders)} folders"
        )
    """

    """TEMPORARY?"""
    imola_csv = list(source_data.glob("Imola_2026/*.csv"))[0]
    lemans_csv = list(source_data.glob("Le_Mans_2026/*.csv"))[0]

    races = {"Imola_2026": imola_csv, "Le_Mans_2026": lemans_csv}
    race_ids = ["Imola_2026", "Le_Mans_2026"]
    race_csvs = [imola_csv, lemans_csv]

    train_races = {"Imola_2026": imola_csv}
    test_races = {"Le_Mans_2026": lemans_csv}
    # test races will be the held-out races that the model is evaluated on

    return races, race_ids, race_csvs, train_races, test_races


def laps_near_event(lap_data: pd.DataFrame):
    r"""
    find several laps around an event (pit stop, non-green flag, collision)
    For the meantime, the function only checks for non-GF values and rows with pit
    markers.

    It's worth noting that the pit time values are recorded in the lap AFTER the pit
    finish line is crossed. So is a car is marked to have crossed the finish line in
    the pits on lap 10, the pit time will be in lap 11, since the finish line is at
    the start of the pitlane.

    For reference, in the original CSVs and most derived dataframes, the columns for
    these values are `"FLAG_AT_FL"` and `"CROSSING_FINISH_LINE_IN_PIT"`. Pit time can
    also be found in `"PIT_TIME"` assuming the car pitted
    """

    key_laps = []  # ??
    event_laps = {}
    # should be dictionary keyed by lap row, with the value established as the event
    # ie {9: "Yellow Flag", 10: "Pit lane finish line crossed"}

    lap_data = lap_data.sort_values("LAP_NUMBER")
    for row in range(len(lap_data)):
        current = lap_data.iloc[row]
        lap_num = current["LAP_NUMBER"]

        # flag, pit finish, pit time
        event_options = [
            current["FLAG_AT_FL"] != "GF",
            current["CROSSING_FINISH_LINE_IN_PIT"] is not None,
            current["PIT_TIME"] is not None,
        ]

        is_event = True if any(event_options) else False

        if is_event:
            key_laps.append(lap_num)

            events = []

            # event_options = [bool, bool, bool] where [0] is a flag, [1] is a pit finish, [2] is a pit time
            # must be multiple, separate if statements in case of multiple events (ie pit cross and full course yellow)
            if event_options[0]:
                events.append(f"Flag: {current["FLAG_AT_FL"]}")

            if event_options[1]:
                events.append("Pit Line Crossed")

            if event_options[2]:
                events.append(f"Pit Stop Time: {current["PIT_TIME"]}")

            event_laps[lap_num] = ", ".join(events)

    key_laps = np.array(key_laps).tolist()
    flagged_laps = []
    for lap_num in key_laps:
        flagged_laps.append(lap_num)
        flagged_laps.append(lap_num + 1)
        flagged_laps.append(lap_num - 1)

    flagged_laps = sorted(list(set(flagged_laps)))

    return event_laps, key_laps  # , flagged_laps


def print_near_laps(lap_data: pd.DataFrame, lap: int):
    r"""
    prints the surrounding laps given a center lap and data.

    prints two laps in each direction from the center lap input
    """

    close_data = lap_data.loc[lap_data["LAP_NUMBER"].between(lap - 2, lap + 2)]

    print(f"\nLap data surrounding lap {lap}:\n")
    print(close_data)


def main():

    path = Path(sys.argv[1]) if len(sys.argv) > 1 else lm_path
    race_id = sys.argv[2] if len(sys.argv) > 2 else race
    (
        print(
            "Usage: python load_data.py <path_to_csv> <race_id>\nUsing default Race ID 'Le_Mans_2026'\n"
        )
        if len(sys.argv) < 3
        else None
    )

    race_data = load_race_data(race_id, path)
    race_data = clean_lap_records(parse_duration_seconds(race_data))

    print(f"\nTesting: Race Data Head: \n{race_data.head()}")

    # origins, history = build_records(race_data)
    # print(f"\nRecords Data Head:\n{origins.head()}\n")

    # print(f"\nHistory Data Part:\n{history["51"][:3]}\n")

    # race_records = build_records(race_data)
    # print(f"\nRecords Data Car 51:\n{race_records.iloc[race_records["NUMBER"] == 51]}")

    # races, race_ids, race_csvs, train, test = make_race_splits()
    # print(f"{{Race: Race CSV}}: \n{races}")
    # print(f"\nTrain Races: {train.keys()}\nTest Races: {test.keys()}")

    # print(f"Testing: Records Data Row 130:\n{origins.iloc[129]}\n")

    # sample testing with one car:

    col = [
        "LAP_NUMBER",
        "LAP_TIME_SEC",
        "FLAG_AT_FL",
        "CROSSING_FINISH_LINE_IN_PIT",
        "PIT_TIME",
        "DRIVER_NUMBER",
    ]

    # using car 51 as an example
    # take only car 51's data
    # which is done by selecting only the data points where the row's "NUMBER" column is
    # equivalent to 51, and where the columns are the ones specified above.
    # data is then sorted by lap number and the indices are reset

    car51 = (
        race_data.loc[race_data["NUMBER"].eq("51"), col]
        .sort_values("LAP_NUMBER")
        .reset_index(drop=True)
    )

    print(f"Car 51 Header:\n{car51.head()}\n")

    event_laps, key_laps = laps_near_event(car51)
    print_near_laps(car51, key_laps[43])


if __name__ == "__main__":

    main()
