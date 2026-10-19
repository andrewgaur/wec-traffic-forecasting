# WEC Traffic Forecasting

This project explores whether slower-class traffic helps predict a Hypercar's next lap time more accurately than recent pace alone. You can use the current program to inspect race timing data and the observations available at each forecast point. Model training and traffic-aware forecast evaluation are still in development.

`load_data.py` loads official timing CSVs, converts time fields to seconds, checks lap records, and replays finish-line crossings in elapsed-time order. It also identifies pit and non-green-flag laps for inspection.

### Current Race Directory

Race data is stored in `wec-traffic-forecasting/data/source_data/` and is grouped by race. Each race folder contains a folder of hour-specific data and a .csv file of the final timing data.

### Races:

|  Race   | Year |  Use  |  Status  |
|---------|------|-------|----------|
| Le Mans | 2026 | Test  |  Current |
|  Imola  | 2026 | Train |  Current |
|   Spa   | 2026 | Train |  Future  |
| C.O.T.A | 2026 | Train |  Future  |
|  Imola  | 2025 | Test  |  Future  |

### Try the browser demo

Open the [live replay demo](https://andrewgaur.github.io/wec-traffic-forecasting/), or open `release/index.html` locally. You don't need to install anything.

Choose a Hypercar and completed lap to move the forecast cutoff. Inspect the latest known laps, then select "Reveal next lap" to compare the recent-pace estimate with the outcome. The demo uses invented data and a median pace baseline. It runs separately from the Python program.

### Run the Python program

Use Python 3.12 or newer. From the repository root, install the dependencies:

```sh
python -m pip install pandas numpy
```

Download the Le Mans 2026 race analysis CSV from [Al Kamel's WEC timing site](https://fiawec.alkamelsystems.com/). Place exactly one final analysis CSV directly inside `data/source_data/Le_Mans_2026/`. Keep additional hourly files in a subfolder so the default loader finds only one CSV. The official timing files aren't included in this repository.

Run the program from the repository root:

```sh
python load_data.py
```

The program prints data checks and sample lap records in your terminal. Its current inspection example uses car #51 and a fixed event index. Other inputs may require adjusting that example, and files with fewer event laps can raise an `IndexError`.
