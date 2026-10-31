import csv
import shutil
from pathlib import Path

COLUMNS = ["experiment_name", "feed_id", "scheduled_time", "timestamp", "matrix", "well",
           "larva_id", "well_state", "amount_ul", "est_volume_mm3", "est_height_mm",
           "alive", "photo_file"]


class FeedingLogger:
    def __init__(self, csv_path):
        self.csv_path = Path(csv_path)

    def log_well(self, **row):
        try:
            is_new = not self.csv_path.exists()
            with open(self.csv_path, "a", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=COLUMNS)
                if is_new:
                    writer.writeheader()
                writer.writerow(row)
        except OSError as e:
            # A logging problem (e.g. file open in Excel) must never stop the feeding
            print(f"[FEEDING_LOGGER]: WARNING - could not write to {self.csv_path}: {e}")

    def update_view_copy(self):
        """
        Copies the main log to feeding_log_view.csv (the file the user can open safely).
        Call it only when a feeding has finished. Never raises, so it can't stop the robot.
        """
        view_path = self.csv_path.with_name("feeding_log_OPEN_THIS.csv")
        try:
            if self.csv_path.exists():
                shutil.copyfile(self.csv_path, view_path)
        except OSError as e:
            # Usually means the view file is open in Excel; it will update after the next feeding
            print(f"[FEEDING_LOGGER]: WARNING - could not update {view_path}: {e}")