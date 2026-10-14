# load the race data from source files into the data folder

import pandas as pd
import numpy as np
import sys, csv
from pathlib import Path
from hashlib import sha256

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
    raw_race_data = pd.read_csv(path, sep = ";", encoding = "utf-8", dtype=str)
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
        writer.writerow([source_id, race_id, session, source_url, retrieval_date, path, hash])

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
    repeat_records = df.duplicated(subset=["RACE_ID", "NUMBER", "LAP_NUMBER"], keep="first")
    if repeat_records.any():
        print(f"Dropping {repeat_records.sum()} repeated lap records.")
        df = df[~repeat_records]
    else:
        print("No repeated lap records found.")

    # check missing timing data and identifiers
    # lap time
    laps_all_float = df["LAP_TIME_SEC"].apply(lambda time: isinstance(time, float))
    missing_lap_time_id = {row["RACE_ID"]: row["LAP_NUMBER"] for _, row in df[~laps_all_float].iterrows()}

    if not laps_all_float.all():
        print(f"Missing lap time for the following laps: {missing_lap_time_id}")
        # df = df[lap_time_float]
    
    if not df["NUMBER"].notnull().all():
        missing_car_id = {row["RACE_ID"]: row["LAP_NUMBER"] for _, row in df[df["NUMBER"].isnull()].iterrows()}
        print(f"Missing car number for the following laps: {missing_car_id}")
        # df = df[df["NUMBER"].notnull()]

    return df

if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else lm_path
    race_id = sys.argv[2] if len(sys.argv) > 2 else race
    print("Usage: python load_data.py <path_to_csv> <race_id>") if len(sys.argv) < 3 else None
    
    race_data = load_race_data(race_id, path)
    race_data = clean_lap_records(parse_duration_seconds(race_data))
    print(f"Race Data Head: \n{race_data.head()}")
