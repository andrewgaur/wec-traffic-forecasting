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


def load_race_data(path):
    raw_race_data = pd.read_csv(path, sep = ";", encoding = "utf-8", dtype=str)
    raw_race_data.columns = raw_race_data.columns.str.strip()
    race_df = pd.DataFrame(raw_race_data)
    return race_df

## source manifest??
# would/should include event, session, source URL, retrieval date, local path, etc
# no clue if this is the right process

def save_source_manifest(source_id, race_id, session, source_url, retrieval_date, path):
    with open("metadata/source_manifest.csv", "a", newline="") as file:
        writer = csv.writer(file)

        hash = sha256(Path(path).read_bytes()).hexdigest()
        writer.writerow([source_id, race_id, session, source_url, retrieval_date, path, hash])

def parse_duration_seconds(df):

    lap = df.loc['LAP_TIME'].strip().split(':')
    df["LAP_SEC"] = float(lap[0]) * 60 + float(lap[1])
    

    for row in df:
        lap = df.loc[row, 'LAP_TIME']
        lap = lap.strip().split(':')
        elapsed = df.loc[row, 'ELAPSED'].strip().split(':')
        
        lap_seconds = float(lap[0]) * 60 + float(lap[1])
        elapsed_seconds = float(elapsed[0]) * 60 + float(elapsed[1])

        df["LAP_SEC"][row] = lap_seconds
        df["ELAPSED_SEC"][row] = elapsed_seconds

if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else lm_path
    race_data = load_race_data(path)
    parse_duration_seconds(race_data)
    print(race_data.head())
