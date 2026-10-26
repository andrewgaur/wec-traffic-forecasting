# import csv
import statistics
import sys
from pathlib import Path

# import numpy as np
import pandas as pd

from load_data import clean_lap_records, load_race_data, parse_duration_seconds

# default path, same as in `load_data.py`

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


# record building function moved from `load_data.py`, first script should just load and clean data.


def build_records(clean_df: pd.DataFrame):
    r"""
    takes input `clean_df` of type pd.DataFrame. meant to be the cleaned df that is
    output from `clean_lap_records()`.

    builds dictionary of records for each race, keyed by race id and car number\n
    function sorts the cleaned dataframe input by elapsed time, so the df is in
    the order of finish line crossings.

    then for each row in the sorted dataframe, it saves the latest lap for that row's
    car in dictionary `state`, keyed by car number. If the class of the current row's
    car is `"HYPERCAR"`, then the row is appended to list `origin`.
    """

    # state is the latest completed observation for each car, keyed by car number
    # it is saved/changed/replaced after each lap (as you replay crossings)
    state = {}

    # saved opportunities, used to predict car's next lap
    # changes when car completes a lap (adds a new state)
    # at the moment, exclusively hypercars
    origins = []

    # pace_history should be a dict, keyed by car number, with each value containing a list of that
    # cars current pace history dictionaries.

    pace_history = {}

    elapsed_sort = clean_df.sort_values(["ELAPSED_SEC"])

    history = {}

    for row in range(len(elapsed_sort)):

        current = elapsed_sort.iloc[row]
        car_number = current["NUMBER"]
        lap_number = current["LAP_NUMBER"]

        lap_history_data = {
            "LAP_NUMBER": lap_number,
            "LAP_TIME_SEC": current["LAP_TIME_SEC"],
            "ELAPSED_TIME_SEC": current["ELAPSED_SEC"],
            "DRIVER_NUM": current["DRIVER_NUMBER"],
            "FLAG_AT_FL": current["FLAG_AT_FL"],
            "CROSS_FL_IN_PIT": current["CROSSING_FINISH_LINE_IN_PIT"],
            "PIT_TIME": current["PIT_TIME"],
        }

        # if the car already has prev lap data stored in history, just append lap data to existing
        # list. otherwise, initialize car number key in history dict with a value of a list of lap data

        if car_number in history.keys():
            history[car_number].append(lap_history_data)

        elif car_number not in history.keys():
            history[car_number] = [lap_history_data]

        prev = state.get(car_number)
        state[car_number] = current

        # append car pace to pace_history dict
        # if car is already in pace dictionary, then it has previous data, which should be input
        # into update_pace_history. else, there is no history, so this lap is the first lap in
        # pace history.

        if car_number in pace_history.keys():

            current_history = pace_history[car_number]
            new_history = update_pace_history(current, prev, current_history)

            pace_history[car_number] = new_history

        elif car_number not in pace_history.keys():

            new_history = update_pace_history(current, prev, None)

            pace_history[car_number] = new_history

        """
        if car_number == "51" and 218 <= lap_number <= 223:
            candidate_laps = [
                record["LAP_NUMBER"]
                for record in pace_history[car_number]
            ]

            print(lap_number, candidate_laps)
        """

        med_pace_baseline = calc_pace_baseline(pace_history[car_number])

        source_laps = tuple(
            record["LAP_NUMBER"]
            for record in pace_history[car_number][-5:]
        )

        if current["CLASS"] == "HYPERCAR":

            if any(
                observation["ELAPSED_SEC"] > current["ELAPSED_SEC"]
                for observation in state.values()
            ):
                raise ValueError(
                    "observation['ELAPSED_SEC'] is greater than current['ELAPSED_SEC']"
                )

            available_laps_now = history[car_number]
            count_available_now = len(available_laps_now)

            lmgt3_ct = sum(series["CLASS"] == "LMGT3" for series in state.values())
            lmp2_ct = sum(series["CLASS"] == "LMP2" for series in state.values())

            origins.append(
                {
                    "RACE_ID": current["RACE_ID"],
                    "NUMBER": car_number,
                    "CLASS": current["CLASS"],
                    "ORIGIN_ELAPSED_SEC": current["ELAPSED_SEC"],
                    "COMPLETED_LAP_NUMBER": lap_number,
                    "TARGET_LAP_NUMBER": lap_number + 1,
                    "KNOWN_CAR_COUNT": len(state),
                    "KNOWN_LMGT3_COUNT": lmgt3_ct,
                    "KNOWN_LMP2_COUNT": lmp2_ct,
                    "COMPLETED_LAP_COUNT": count_available_now,
                    "PACE_CANDIDATE_COUNT": len(pace_history[car_number]),
                    "PACE_BASELINE_SEC": med_pace_baseline,
                    "PACE_SOURCE_LAPS": source_laps,
                }
            )

        """
        elif current["CLASS"] == "LMGT3":
            lmgt3_ct += 1
        elif current["CLASS"] == "LMP2":
            lmp2_ct += 1
        """

    # print(f"STATE (007):\n{state["007"]}")
    return pd.DataFrame(origins), history, pace_history

def lap_event_bools(lap):

    nongf = True if lap["FLAG_AT_FL"] != "GF" and lap["FLAG_AT_FL"] != "FF" else False
    pit_enter = True if lap["CROSSING_FINISH_LINE_IN_PIT"] is not None else False
    pit_exit = True if lap["PIT_TIME"] is not None else False

    event_bool = [nongf, pit_enter, pit_exit]

    return event_bool



def lap_decisions(lap_data):
    r"""
    will theoretically decide if a lap is a usable candidate to determine pace, if it's excluded due to
    some event, or if it is uncertain.

    If a lap has a flag that is NOT a green flag (GF), it should be excluded. SF indicates some kind of flag,
    though unsure which one. could be surface flag, for debris/poor track conditions, could be single flag,
    indicating a single sector flag. Either way, it presumably indicates that there is a flag, which
    significantly slows that lap; FCY indicates full course yellow, also significantly slowing that lap.
    Should also probably exclude 2 or 3 laps following a flag as well, due to inconsistencies with restarts, 
    debris on track, or other factors. Although they might signify good data that slow cars
    slow down faster classes, which is exacerbated because they are all close together.

    If a lap has data for crossing the pit finish line or has a pit time (so if either of these are not None),
    the lap should be excluded. The lap time is slightly extended on pit entry, so it shouldn't be considered
    for pace. The lap time is significantly extended that the pit time is counted as part of sector 1, so those
    laps should likewise not be considered.
    """

    lap_class = {}

    """
    lap classifications, should be keyed by a tuple of car number and driver number, with each car number item storing
    a nested dictionary of lap classification, keyed by the lap number

    i.e., structure:
    lap_class = {
        ("car_number", "driver_number): {
        
        "lap_num": eligible
        "lap_num 2": eligible
        "lap_num 3": excluded
        etc

        }

        etc
    }
    """

    for row in range(len(lap_data)):

        current = lap_data.iloc[row]
        lap = current["LAP_NUMBER"].item()
        car = current["NUMBER"]
        driver = current["DRIVER_NUMBER"].item()

        key = (car, driver)
        
        if key not in lap_class.keys():
            lap_class[key] = {}


        events = lap_event_bools(current)
        has_event = any(events)
        event_list = []

        # if lap has an event, find which event(s). If the car & driver aren't already in the lap classification
        # dictionary, add them, then add the exclusion
        if has_event:

            if events[0]:
                event_list.append(f"Flag: {current["FLAG_AT_FL"]}")
            if events[1]:
                event_list.append("Pit Line Crossed")
            if events[2]:
                event_list.append(f"Pit Stop Time: {current["PIT_TIME"]}")

            reason = ", ".join(event_list)

            lap_class[key][lap] = f"Excluded: {reason}"

        else:
            lap_class[key][lap] = "Candidate: No recorded exclusion event at FL"

    return lap_class


def update_pace_history(current, previous, pace_laps):
    active_driver = int(current["DRIVER_NUMBER"])
    current_lap = int(current["LAP_NUMBER"])
    # car = current["NUMBER"]
    current_data = {
        "LAP_NUMBER": current_lap,
        "LAP_TIME_SEC": float(current["LAP_TIME_SEC"]),
        "ELAPSED_SEC": float(current["ELAPSED_SEC"]),
        }

    race_pace = []

    if previous is not None:
        prev_driver = int(previous["DRIVER_NUMBER"])

    # prev_lap = previous["LAP_NUMBER"]
    if pace_laps:
        race_pace = pace_laps

    any_event = lap_event_bools(current)

    if any(any_event):
        # if there is any event, clear the pace history.
        # clearing on any non-green flag is rather conservative, but can be changed later
        race_pace.clear()

    elif (previous is not None) and active_driver != prev_driver:
        # if the current driver is different, there was a driver swap, so clear pace history
        race_pace.clear()

    elif (previous is not None) and (active_driver == prev_driver):
        # if the driver is the same as the previous driver, add the current lap to pace
        # race_pace = pace_laps
        # print("No pace history, starting new segment.")
        race_pace.append(current_data)

    else:
        # if there are no previous laps, just append the current lap to pace history
        race_pace.append(current_data)

    return race_pace




def calc_pace_baseline(pace_laps, window_size = 5, minimum_laps = 3):

    # latest 5 lap records (since window size is evaluated at 5 atm)
    latest_records = pace_laps[-window_size:]

    # return no baseline if there are not enough records to calculate one
    # cutoff determined at 3 pace lap records at the moment
    if len(latest_records) < minimum_laps:
        return None

    latest_times = [record["LAP_TIME_SEC"] for record in latest_records]
    med_latest_time = statistics.median(latest_times)

    return med_latest_time


def full_race_data(race_id, path):
    race_data = load_race_data(race_id, path)
    race_data = clean_lap_records(parse_duration_seconds(race_data))
    return race_data


def main():
    """
    Should use function definitions from data loading script:
    Select either user-input race or default race, and fetch the CSV path and race ID
    Load the CSV (`load_race_data()`) and convert duration columns (`parse_duration_seconds()`)
    Clean records (`clean_lap_records()`)

    Then pass resulting DataFrame through new pace functions defined in this script.
    """

    # if no race or path is specified when running this script, return to default race id and csv path
    # default is currently "Le_Mans_2026" and "../data/source_data/Le_Mans_2026/*.csv"
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
    print("")

    # CLEANED FULL DATAFRAME HEADER TESTING
    # print("\nTesting: Cleaned Race Data Head Laps:")
    # print(race_data.head())

    """ DATA/PACE GENERATION AND ANALYSIS"""


    """ BASELINE FUTURE DATA LEAKAGE TESTING """

    """
    not entirely sure but I think the idea of this is to compare splitting data BEFORE vs AFTER
    running build_records on the dataset. because running it before allows the potential for leakage,
    but running it after guarentees that the origin only sees the selected data. if the full dataset
    is run through build_records and returns the same origin as the limited dataset that is run through
    build_records, then there is no leakage.
    """


    full_data = race_data

    # Find when car 51 completes lap 223.
    cutoff_time = race_data.loc[
        race_data["NUMBER"].eq("51")
        & race_data["LAP_NUMBER"].eq(223),
        "ELAPSED_SEC",
    ].item()

    # Keep all cars' observations available at that moment.
    split_data = race_data.loc[
        race_data["ELAPSED_SEC"] <= cutoff_time
    ]

    full_data_origin = build_records(full_data)[0]
    split_data_origin = build_records(split_data)[0]

    columns = [
        "NUMBER",
        "COMPLETED_LAP_NUMBER",
        "PACE_BASELINE_SEC",
        "PACE_SOURCE_LAPS",
    ]

    print(f"Full Data Origin Testing:\n{full_data_origin.loc[
        full_data_origin["COMPLETED_LAP_NUMBER"].eq(223) & full_data_origin["NUMBER"].eq("51"),
        columns]}"
        )

    print(f"Split-First Data Origin Testing:\n{split_data_origin.loc[
        split_data_origin["COMPLETED_LAP_NUMBER"].eq(223) & split_data_origin["NUMBER"].eq("51"),
        columns]}"
        )



    """ ORIGIN PACE BASELINE TESTING

    origins, history, pace_history = build_records(race_data)
    print(f"\nTesting: Origins Car 51 Laps 218-223:\n{
        origins.loc[origins["COMPLETED_LAP_NUMBER"].between(218,223) & origins["NUMBER"].eq("51"),
            ["NUMBER", "ORIGIN_ELAPSED_SEC", "COMPLETED_LAP_NUMBER", "COMPLETED_LAP_COUNT",
            "PACE_CANDIDATE_COUNT", "PACE_BASELINE_SEC", "PACE_SOURCE_LAPS"]]
        }\n")

    """


    """ CANDIDATE ELIGIBILITY TESTING

    lap_eligibility = lap_decisions(race_data)
    print("Testing: Lap Eligibility (Lap 218-223):")
    for lap in range(218, 224):
        print(lap, lap_eligibility[("51", 2)][lap])


    sample = origins.loc[
        origins["NUMBER"].eq("51")
        & origins["COMPLETED_LAP_NUMBER"].between(218, 223),
        ["COMPLETED_LAP_NUMBER", "PACE_CANDIDATE_COUNT"],
    ]

    print(sample)

    """



    """ NOTES
    `origins` is a DataFrame of exclusively Hypercar lap data, stored in order of lap completion.
    i.e., the first row is the first Hypercar to complete a lap, then the next, and so on and so forth
    so it tracks the order of finish-line-crossings, not per-car lap history, so if car is lapped, that
    is technically able to be realized by looking at the car number order in `origins`. However, it is not
    explicitly saved or stated.

    `history` is a dictionary of lists, keyed by car number. each car number key is associated with a list
    of all lap data for that given car number. The list items consist of dictionaries containing lap data
    for the given lap that is appended to the list.

    like: dictionary {
        "car_number": list [

            {
            "lap_number": lap number
            "car_number": number
            "lap_time": time 1
            etc
            },

            {
            "lap_number": lap number 2
            "car_number": number
            "lap_time": time 2
            etc
            },

            etc

        ]
    }

    Technically, `history` contain all the data in `origins`, as well as LMGT3 data, but origins 
    is sorted chronologically, while history is sorted by car number.
    """


if __name__ == "__main__":
    main()
