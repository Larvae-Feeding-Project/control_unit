# Control System

This repo contains our implementation of the control system. 
It includes the control_unit module, Control enums, Control UI and logo.

## Dependencies

1. PySide6
2. enum
3. time
4. datetime
5. threading
6. string
7. json
8. csv
9. shutil
10. pathlib

## Control UI
This is the frontend implementation of our project. The system is designed for non-technical users, offering control over all wells and schedules without requiring
tinkering with the code.

## Feeding log (CSV)

Each experiment gets its own folder under `BASE_DATA_DIRECTORY`:

```
<BASE_DATA_DIRECTORY>/<experiment_name>/
    feeding_log_DO_NOT_OPEN.csv   <- main log, written by the robot
    feeding_log_OPEN_THIS.csv     <- copy for user viewing
    feed_<id>/MATRIX1_A1.jpg ...  <- photos of each feeding
```

- **Do not open `feeding_log_DO_NOT_OPEN.csv`.** Excel locks open files, and the robot could not write to it.
- Open `feeding_log_OPEN_THIS.csv` instead. It is refreshed after each completed feeding (not after an emergency stop). If it is open in Excel, the refresh is skipped until the next feeding.
- Nothing is logged in dev mode.
- Line 1 of the file is the experiment name. Line 2 is the header. Then there is one row per larva per feeding. In Python, read it with `pandas.read_csv(path, skiprows=1)`.

| Column | Meaning |
|---|---|
| feed_id | Feeding number (restarts at 1 each time the program starts) |
| scheduled_time | Time chosen in the UI |
| timestamp | Actual time the row was written |
| matrix, well | Plate panel (MATRIX1-3) and well (e.g. A1) |
| larva_id | Stable id of the larva across feedings (e.g. MATRIX1_A1) |
| well_state | MANUAL or CALCULATED |
| dx, dy | Larva offset from the well center in mm (can be negative); empty until the vision analysis is implemented |
| amount_ul | Food dispensed in microliters; empty for calculated wells for now |
| est_volume_mm3, est_height_mm | Larva size estimate; empty for now |
| alive | Empty (unknown) for now |
| photo_path | Full path of the photo taken before feeding; empty if there is no photo |

## TODO's
1. logic so that feeds cannot hit each other
2. outline between feeds for better visibility
3. more feed information (i.e feed_id, time, name of project/batch etc)
4. load feed (for changes)
5. control panel add excel directory and photo directories
6. stop button - needs fix
7. process progress indication - num of wells left


## Contributing - nees update

Asaf Shasha and Nitai Gildor
