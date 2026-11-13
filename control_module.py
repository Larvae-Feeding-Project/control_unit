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
from vision_system import vision_system_module
from feeding_logger import FeedingLogger

# from cv_system import cv_module

SAFE_Z = 100.0
INDEX_TO_LETTER = string.ascii_uppercase  # 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
TEMP_FEED_Z = 54.3  # for on bed feeding 47.4
WORK_Z = 150


class ControlUnit:
    def __init__(self, dev_mode=False):
        """
        Control Unit constructor. Creates movement system, fluidics system and CV objects.
        :return: ControlUnit object
        """

        # Path to fluidics module directory
        base_dir = Path(__file__).resolve().parent
        data_path = base_dir / "control_data.json"

        # Dedicated path for tracking the feed ID between launches
        self.id_tracker_path = base_dir / "feed_id_tracker.json"

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
                self.movement_module = movement_driver.MovementDriver()
                self.fluidics_module = fluidics_module.FluidicsDriver()
                self.vision_system = vision_system_module.VisionDriver()
            pass
        except Exception as e:
            print(f"[CONTROL_UNIT]: One of the subsystem initiations failed!. EXITING!")
            exit(1)

        self.status = ControlStatus.IDLE
        self.scheduled_feeds = []

        # Load the saved feed identifier (defaults to 1 if it's the first time)
        self.feed_identifier = self._load_feed_id()
        self.lock = threading.Lock()

        # Stop event
        self.stop_event = threading.Event()

        self.running = True
        self.arm_is_up = False

        # UI callback "sockets"
        self.on_task_added = None
        self.on_task_executed = None
        self.on_task_deleted = None
        self.on_status_changed = None

        # Run thread that manages scheduled execution
        self.thread = threading.Thread(target=self._run_schedule_loop, daemon=True)
        self.thread.start()

        print(f"[CONTROL_UNIT]: ControlUnit initialized!")

    def _load_feed_id(self):
        """Loads the last used feed identifier from the tracker file."""
        if self.id_tracker_path.exists():
            try:
                with open(self.id_tracker_path, "r") as file:
                    tracker_data = json.load(file)
                    return tracker_data.get("feed_identifier", 1)
            except Exception as e:
                print(f"[CONTROL_UNIT]: Error loading feed ID tracker: {e}")
        return 1

    def _save_feed_id(self):
        """Saves the current feed identifier to persist between launches."""
        try:
            with open(self.id_tracker_path, "w") as file:
                json.dump({"feed_identifier": self.feed_identifier}, file, indent=4)
        except Exception as e:
            print(f"[CONTROL_UNIT]: Error saving feed ID tracker: {e}")

    def add_feed_task(self, python_dt, percentage, manual_amount, snapshot_data, experiment_name=""):
        """
            Adds feeding to the schedule (and also updates the UI using a signal)
            :param python_dt: python time object for the feeding
            :param percentage: int representing the percentage of volume for feeding
            :param manual_amount: int representing manual amount of the feeding (in micro liters)
            :param snapshot_data: snapshot of the 3 plates (list of plate snapshots)
            :param experiment_name: str representing the name of the experiment
            :return: The feeding ID
        """
        with self.lock:
            feed_id = self.feed_identifier
            self.feed_identifier += 1

            # Save the newly incremented ID immediately to json
            self._save_feed_id()

            feeding = {
                'id': feed_id,
                'experiment_name': experiment_name,
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
            display_name = experiment_name if experiment_name else "Unnamed"
            display_text = f"Experiment Name: {display_name}\nFeeding ID: {feed_id}\nScheduled Time: {time_str}\n{percentage}%"
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

    def _set_status(self, new_status):
        """
            Safely updates the machine status and notifies the UI immediately.
        :param new_status: The ControlStatus enum to change to.
        """
        self.status = new_status
        if self.on_status_changed:
            self.on_status_changed(new_status)

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
            Turns the camera system on
            Future update will also heat up the arm
            :return: True when finished or else if something fails
        """
        container_loc = self.control_data["EMPTY_CONTAINER_LOC"]
        self.movement_module.move(z=100)
        if not self.movement_module.move(x=container_loc["X"], y=container_loc["Y"], z=container_loc["Z"],
                                         speed=3000): return False

        # Fill the tube
        if not self.fluidics_module.fill_tube(): return False

        # Start the vision system (start the camera)
        if not self.vision_system.vision_system_startup(): return False

        time.sleep(4)

        return True

    def _feeding_operation(self, feeding, exp_path):
        """
            Runs the feeding process itself. Works plate by plate
        :param feeding: The feeding data
        :param exp_path: Pathlib object to the current experiment's data folder
        :return: True when finished (errors in plates may have occurred)
        """

        print(feeding)
        plates_lst = feeding["snapshot"]
        manual_amount = feeding["manual_amount"]
        for matrix_index, plate in enumerate(plates_lst):
            plate_success = self._feed_plate(plate, matrix_index + 1, manual_amount, exp_path)

            # Stop if stop event is on
            if self.stop_event.is_set(): return False

            if not plate_success:
                print(f"Problem with matrix{matrix_index + 1}, continuing to next plate")

        return True

    def _feed_plate(self, plate, matrix_index, manual_amount, exp_path):
        """
            Feeds of the specific plate.
        :param plate: plate snapshot - {'plate_id':int,
        'plate_type': PlateType, 'wells': [{well row, col, state} for each well in this plate]}
        :param matrix_index: number of the matrix we are working on (1,2,3)
        :param manual_amount: preset amount to feed in microliters
        :param exp_path: Pathlib object to the experiment's folder
        :return: False if there was some problem, True if everything worked fine
        """

        wells_lst = plate["wells"]
        matrix = f"MATRIX{matrix_index}"
        plate_type = plate["plate_type"]
        for well in wells_lst:
            print(f"row: {well['row']}, column: {well['col']}")
            # Catch abort request
            if self.stop_event.is_set():
                print(f"  -> Aborting matrix {matrix_index} loop due to STOP request.")
                return False

            # Disabled well
            if well["state"] == WellState.DISABLED:
                continue

            # Manual well
            elif well["state"] == WellState.MANUAL:
                # Move just above larvae
                if not self.movement_module.move_to_well(matrix, plate_type, INDEX_TO_LETTER[well["row"]], well["col"],
                                                         SAFE_Z):
                    return False

                if self.stop_event.is_set():
                    print(f"  -> Aborting matrix {matrix_index} loop due to STOP request.")
                    return False

                if not self.movement_module.move_to_well(matrix, plate_type, INDEX_TO_LETTER[well["row"]], well["col"],
                                                         TEMP_FEED_Z):  # Need to change to user defined height
                    return False

                # Dispense preset amount
                print(f"  -> Dispensing {manual_amount}uL...")
                dispense_success = self.fluidics_module.output(manual_amount)
                if not dispense_success:
                    print(f"  -> WARNING: Dispense failed")
                    return False

                # Log this manual feeding (the amount is known, no photo is taken for manual wells)
                self._log_well(matrix, INDEX_TO_LETTER[well["row"]], int(well["col"]) + 1,
                               WellState.MANUAL, manual_amount)

                # Move up to safe height before continuing
                self.movement_module.move_to_well(matrix, plate_type, INDEX_TO_LETTER[well["row"]], well["col"],
                                                  SAFE_Z, speed=6000)

            # Calculated well
            if well["state"] == WellState.CALCULATED:
                # Move camera above larvae
                if not self.movement_module.move_to_well_photo_position(matrix, plate_type,
                                                                        INDEX_TO_LETTER[well["row"]], well["col"]):
                    return False

                if self.stop_event.is_set():
                    print(f"  -> Aborting matrix {matrix_index} loop due to STOP request.")
                    return False

                # Build the filename for the photo (e.g., MATRIX1_A1.jpg)
                well_id = f"{matrix}_{INDEX_TO_LETTER[well['row']]}{str(int(well['col']) + 1)}"
                photo_path = exp_path / f"{well_id}.jpg"

                time.sleep(1)

                # Take photo and remember whether it succeeded
                photo_ok = self.vision_system.take_photo(str(photo_path))
                if not photo_ok:
                    print(f"  -> WARNING: Vision system failure! Photo skipped for {well_id}.")

                # Log this larva; no amount yet (calculated feeding isn't implemented),
                # and the photo name is saved only if the photo succeeded
                self._log_well(matrix, INDEX_TO_LETTER[well["row"]], int(well["col"]) + 1,
                               WellState.CALCULATED, "", photo_path if photo_ok else None)

                # Successful execution
        return True

    def _log_well(self, matrix, letter, col_number, state, amount, photo_path=None, dx="", dy=""):
        """
        Adds one row to the experiment's feeding_log_DO_NOT_OPEN.csv for a single larva.
        :param matrix: matrix name (e.g. "MATRIX1")
        :param letter: row letter of the well (e.g. "A")
        :param col_number: column number of the well, starting from 1
        :param state: WellState of the well (MANUAL or CALCULATED)
        :param amount: amount of food in microliters ("" if nothing was dispensed)
        :param photo_path: Path of the saved photo, or None if there is no photo
        :param dx: x offset of the larva from the center of the well (in mm), can be negative or positive, "" if not calculated
        :param dy: y offset of the larva from the center of the well (in mm), can be negative or positive, "" if not calculated
        :return: None
        """
        f = self.current_feeding
        self.feeding_logger.log_well(
            feed_id=f['id'],
            # Planned time of the feeding (same for all larvae in this feeding)
            scheduled_time=f['time'].strftime("%Y-%m-%d %H:%M"),
            # Actual time this row was written
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            matrix=matrix,
            well=f"{letter}{col_number}",
            # Stable id that follows the same larva across all feedings
            larva_id=f"{matrix}_{letter}{col_number}",
            well_state=state.name,
            dx=dx,
            dy=dy,
            amount_ul=amount,
            # Full path of the photo taken before feeding ("" if no photo)
            photo_path=str(photo_path) if photo_path else "")

    def _feeding_end(self):
        """
            Finishes feeding operation of ARIS. Empties tube and then moves arm back to resting place (reset).
            Also turns off the camera
            :return: True when finished or else if something fails
        """
        if not self.fluidics_module.clear_tube(): return False
        self.movement_module.reset()
        self.vision_system.vision_system_turn_off()
        return True

    def execute_feeding(self, feeding):
        """
            Executes a feeding, by coordinating all the subsystems
        :param feeding: data structure with all the feeding data (name, snapshot etc)
        :return:
        """

        # Update status
        self._set_status(ControlStatus.FEEDING)
        self.stop_event.clear()

        # In dev mode doesn't actually use subsystems, only waits and prints
        if self.dev_mode:
            print(f"\n***DEV_MODE_ON*** ⚡ ROBOT STARTING! Time: {feeding['time']}")
            print(f"⚡ Feed Amount: {feeding['percent']}%")
            print("=" * 40 + "\n")
            time.sleep(20)
            self._set_status(ControlStatus.IDLE)
            print(f"\n***DEV_MODE_ON*** ⚡ ROBOT FINISHED!")
            return

        # Actual feeding process
        else:
            print(f"\n⚡ ROBOT STARTING! Scheduled Time: {feeding['time']}")

            # Experiment Directory creation
            exp_name = feeding.get('experiment_name') or 'Unnamed_Experiment'
            base_dir_str = self.control_data.get("BASE_DATA_DIRECTORY", "")
            feed_id = feeding.get('id', 'unknown_id')
            exp_path = Path(base_dir_str) / exp_name / f"feed_{feed_id}"
            try:
                # Creates the folder, and any parent folders if they don't exist
                exp_path.mkdir(parents=True, exist_ok=True)
                print(f"[CONTROL_UNIT]: Experiment directory ready at {exp_path}")
            except Exception as e:
                print(f"[CONTROL_UNIT]: ERROR creating directory {exp_path}: {e}")
                self._set_status(ControlStatus.IDLE)
                return

            # Create the CSV logger for this experiment (one feeding_log_DO_NOT_OPEN.csv per experiment folder)
            self.feeding_logger = FeedingLogger(exp_path.parent / "feeding_log_DO_NOT_OPEN.csv", exp_name)
            # Keep the current feeding data so _log_well can read the id and time.
            self.current_feeding = feeding

            # Startup
            startup_success = False
            if self.stop_event.is_set():
                print("Aborted before startup...")
            else:
                startup_success = self._feeding_startup()

            # Feeding operation
            if startup_success and not self.stop_event.is_set():
                self._feeding_operation(feeding, exp_path)

            # Evaluate finish process
            if self.stop_event.is_set():
                print("\n⚠️ FEEDING ABORTED DUE TO EMERGENCY STOP!")

                # Give the restarted systems a minute to reset properly
                time.sleep(60)

            else:
                self._feeding_end()
                print(f"\n⚡ ROBOT ENDED FEEDING")
                # Feeding completed normally: refresh the copy the user can open
                self.feeding_logger.update_view_copy()

            self.stop_event.clear()
            self._set_status(ControlStatus.IDLE)

    def request_stop(self):
        """
            Triggered by the UI STOP button. Halts hardware and flags the python thread to abort.
        """
        if self.status is not ControlStatus.FEEDING:
            return

        print("\n[CONTROL_UNIT]: 🛑 EMERGENCY STOP REQUESTED!")

        # Flag feeding functions to stop
        self.stop_event.set()
        # Hardware kills immediately
        if not self.dev_mode:
            if hasattr(self, 'movement_module'):
                self.movement_module.emergency_stop()
            if hasattr(self, 'fluidics_module'):
                self.fluidics_module.emergency_stop()
            if hasattr(self, 'vision_system'):
                self.vision_system.emergency_stop()

        # Update UI and backend status
        self._set_status(ControlStatus.STOPPING)

    def __del__(self):
        self.running = False
        try:
            if hasattr(self, 'movement_module'): self.movement_module.__del__()
            if hasattr(self, 'fluidics_module'): self.fluidics_module.__del__()
            if hasattr(self, 'vision_system'): self.vision_system.__del__()
        except:
            pass
        print(f"[CONTROL_UNIT]: shutting down...")

    def request_arm_toggle(self):
        """
        Triggered by the UI. Starts a thread to toggle arm position up/down.
        Only allowed if system is IDLE.
        """
        if self.status != ControlStatus.IDLE:
            print("[CONTROL_UNIT]: Cannot move arm, system is busy.")
            return

        # Open in a thread to prevent UI freezing
        threading.Thread(target=self._toggle_arm_thread, daemon=True).start()

    def _toggle_arm_thread(self):
        """
        Thread function that actually moves the arm and updates the status.
        """

        if self.dev_mode:
            direction = "DOWN" if self.arm_is_up else "UP"
            print(f"\n***DEV_MODE_ON*** ⚡ Moving arm {direction}...")
            time.sleep(2)  # Simulate movement duration
            self.arm_is_up = not self.arm_is_up
        else:
            # Set your desired Z values here (assuming 0.0 is bed height)
            self._set_status(ControlStatus.MOVING)
            target_z = 0.0 if self.arm_is_up else WORK_Z
            print(f"[CONTROL_UNIT]: Moving arm to Z={target_z}...")

            try:
                success = self.movement_module.move(z=target_z)
                if success:
                    self.arm_is_up = not self.arm_is_up
                    print("[CONTROL_UNIT]: Arm movement complete.")
                else:
                    print("[CONTROL_UNIT]: WARNING: Arm movement failed.")
                self._set_status(ControlStatus.IDLE)
            except Exception as e:
                print(f"[CONTROL_UNIT]: Error moving arm: {e}")
                self._set_status(ControlStatus.IDLE)