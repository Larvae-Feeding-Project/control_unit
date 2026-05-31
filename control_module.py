import threading
import time
from datetime import datetime
from control_enums import *
from pathlib import Path
import json
import string

# Subsystem imports
from movement_driver import movement_driver
from fluidics_system import fluidics_module

# from cv_system import cv_module

SAFE_Z = 100.0
INDEX_TO_LETTER = string.ascii_uppercase  # 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'


class ControlUnit:
    def __init__(self, dev_mode=False):
        """
        Control Unit constructor. Creates movement system, fluidics system and CV objects.
        :return: ControlUnit object
        """

        # Path to fluidics module directory
        base_dir = Path(__file__).resolve().parent
        data_path = base_dir / "control_data.json"

        # Open control data dict
        try:
            with open(data_path, "r") as file:
                self.control_data = json.load(file)
            print("Control data loaded successfully")
        except FileNotFoundError:
            print('No control data file found')
        except Exception as e:
            print("Exception occurred, could not open data.json")

        # Init
        self.dev_mode = dev_mode
        try:
            if not self.dev_mode:
                self.fluidics_module = fluidics_module.FluidicsDriver()
                self.movement_module = movement_driver.MovementDriver()
                # self.cv_module = cv_module()
            pass
        except Exception as e:
            print(f"[CONTROL_UNIT]: One of the subsystem initiations failed!. EXITING!")
            exit(1)

        self.status = ControlStatus.IDLE
        self.scheduled_feeds = []
        self.feed_identifier = 1
        self.lock = threading.Lock()

        self.running = True

        # UI callback "sockets"
        self.on_task_added = None
        self.on_task_executed = None
        self.on_task_deleted = None

        # Run thread that manages scheduled execution
        self.thread = threading.Thread(target=self._run_schedule_loop, daemon=True)
        self.thread.start()

        print(f"[CONTROL_UNIT]: ControlUnit initialized!")

    def add_feed_task(self, python_dt, percentage, manual_amount, snapshot_data):
        """
            Adds feeding to the schedule (and also updates the UI using a signal)
            :param python_dt: python time object for the feeding
            :param percentage: int representing the percentage of volume for feeding
            :param manual_amount: int representing manual amount of the feeding (in micro liters)
            :param snapshot_data: snapshot of the 3 plates (list of plate snapshots)
            :return: The feeding ID
        """
        with self.lock:
            feed_id = self.feed_identifier
            self.feed_identifier += 1

            feeding = {
                'id': feed_id,
                'time': python_dt,
                'percent': percentage,
                'manual_amount': manual_amount,
                'snapshot': snapshot_data
            }
            self.scheduled_feeds.append(feeding)
            self.scheduled_feeds.sort(key=lambda x: x['time'])

        # Check if UI is plugged in and if yes build the relevant text for UI schedule
        if self.on_task_added:
            time_str = python_dt.strftime("%Y-%m-%d %H:%M")
            display_text = f"Feeding_id: {feed_id}\nTime: {time_str} - {percentage}% of the larvae volume"
            self.on_task_added(feed_id, display_text)

        print(f"[CONTROL_UNIT]: added feeding {feed_id}:\n{feeding}")
        return feed_id

    def delete_feed(self, feeding_id):
        """
            Deletes a feeding from the scheduled_feeds (and also triggers a signal for the UI if connected
            :param feeding_id: the id of the feeding to be deleted
            :return: VOID
        """
        with self.lock:
            self.scheduled_feeds = [t for t in self.scheduled_feeds if t['id'] != feeding_id]
        if self.on_task_deleted:  # Check if a UI 'plugged in' a function (meaning it is not None)
            self.on_task_deleted(feeding_id)
        print(f"[CONTROL_UNIT]: Deleted feeding {feeding_id}")

    def _run_schedule_loop(self):
        """
            Runs constantly and checks if a feeding needs to be initiated.
            Initiated when controlUnit is initialized
            Exits when controlUnit is destroyed
            :return: None
        """
        while self.running:
            now = datetime.now()
            tasks_to_run = []

            # Acquire lock and extract feedings that their time has come
            with self.lock:
                for task in self.scheduled_feeds[:]:
                    if now >= task['time']:
                        tasks_to_run.append(task)
                        # Remove from backend queue
                        self.scheduled_feeds.remove(task)

            # Execute tasks outside the lock
            for task in tasks_to_run:
                # Remove from UI queue
                if self.on_task_executed:
                    self.on_task_executed(task['id'])

                # Execute the feeding
                self.execute_feeding(task)

            time.sleep(1)

    def _feeding_startup(self):
        """
            Gets Aris ready for feeding. Moves the arm above container and then fills the tube
            :return: True when finished or else if something fails
        """
        container_loc = self.control_data["EMPTY_CONTAINER_LOC"]
        if not self.movement_module.move(x=container_loc["X"], y=container_loc["Y"], z=container_loc["Z"],
                                         speed=3000): return False
        if not self.fluidics_module.fill_tube(): return False

        return True

    def _feeding_operation(self, feeding):
        """

        :param feeding:
        :return:
        """
        plates_lst = feeding["snapshot_data"]
        manual_amount = feeding["manual_amount"]
        for matrix_index, plate in enumerate(plates_lst):
            plate_success = self._feed_plate(plate, matrix_index, manual_amount)
            if not plate_success:
                print(f"Problem with matrix{matrix_index}, continuing to next plate")

        return True

    def _feed_plate(self, plate, matrix_index, manual_amount):
        """
            Feeds of the specific plate.
        :param plate: plate snapshot - {'plate_id':int,
        'plate_type': PlateType, 'wells': [{well row, col, state} for each well in this plate]}
        :param matrix_index: number of the matrix we are working on (1,2,3)
        :param manual_amount: preset amount to feed in microliters
        :return: False if there was some problem, True if everything worked fine
        """
        wells_lst = plate["wells"]
        matrix = f"MATRIX{matrix_index}"
        plate_type = plate["plate_type"]
        for well in wells_lst:
            # Disabled well
            if well["state"] == WellState.DISABLED:
                continue

            # Manual well
            elif well["state"] == WellState.MANUAL:
                # Move just above larvae
                if not self.movement_module.move_to_well(matrix, plate_type, INDEX_TO_LETTER[well["row"]], well["col"],
                                                         SAFE_Z):
                    return False
                if not self.movement_module.move_to_well(matrix, plate_type, INDEX_TO_LETTER[well["row"]], well["col"],
                                                         57):  # Need to change to user defined height
                    return False

                # Dispense preset amount
                print(f"  -> Dispensing {manual_amount}uL...")
                dispense_success = self.fluidics_module.output(manual_amount)
                if not dispense_success:
                    print(f"  -> WARNING: Dispense failed")
                    return False

                # Move up to safe height before continuing
                self.movement_module.move_to_well(matrix, plate_type, INDEX_TO_LETTER[well["row"]], well["col"],
                                                  SAFE_Z)

            # Calculated well
            if well["state"] == WellState.CALCULATED:
                continue

    def _feeding_end(self):
        """
            Finishes feeding operation of ARIS. Empties tube and then moves arm back to resting place (reset)
            :return: True when finished or else if something fails
        """
        if not self.fluidics_module.clear_tube(): return False
        self.movement_module.reset()
        return True

    def execute_feeding(self, feeding):
        """
        Executes a feeding, by coordinating all the subsystems
        :param feeding: data structure with all the feeding data (name, snapshot etc)
        :return:
        """

        # Update status
        self.status = ControlStatus.FEEDING

        # In dev mode doesn't actually use subsystems, only waits and prints
        if self.dev_mode:
            print(f"\n***DEV_MODE_ON*** ⚡ ROBOT STARTING! Time: {feeding['time']}")
            print(f"⚡ Feed Amount: {feeding['percent']}%")
            print("=" * 40 + "\n")
            time.sleep(20)
            self.status = ControlStatus.IDLE
            print(f"\n***DEV_MODE_ON*** ⚡ ROBOT FINISHED!")
            return

        # Actual feeding process
        else:
            print(f"\n⚡ ROBOT STARTING! Time: {feeding['time']}")
            self._feeding_startup()
            self._feeding_operation(feeding)
            self._feeding_end()
            print(f"\n⚡ ROBOT ENDED FEEDING")
            self.status = ControlStatus.IDLE

    def __del__(self):
        self.running = False
        try:
            if hasattr(self, 'movement_module'): self.movement_module.__del__()
            if hasattr(self, 'fluidics_module'): self.fluidics_module.__del__()
            if hasattr(self, 'cv_module'): self.cv_module.__del__()
        except:
            pass
        print(f"[CONTROL_UNIT]: shutting down...")
