import threading
import time
from datetime import datetime

# Subsystem imports
from movement_driver import movement_driver
from fluidics_system import fluidics_module


# from cv_system import cv_module

class ControlUnit:
    def __init__(self, dev_mode=False):
        """
        Control Unit constructor. Creates movement system, fluidics system and CV objects.
        :return: ControlUnit object
        """
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
            executed_ids = []

            with self.lock:
                for task in self.scheduled_feeds[:]:
                    if now >= task['time']:
                        self.execute_feeding(task)
                        self.scheduled_feeds.remove(task)
                        executed_ids.append(task['id'])

            if self.on_task_executed:
                for tid in executed_ids:
                    self.on_task_executed(tid)

            time.sleep(1)

    def execute_feeding(self, task):
        """
        Executes a feeding, by coordinating all the subsystems
        :param task: data structure with all the feeding data (name, snapshot etc)
        :return:
        """
        # In dev mode doesnt actgually use subsystems, only prints
        if self.dev_mode: # todo: implement feeding flow
            print(f"\n⚡ ROBOT STARTING! Time: {task['time']}")
            print(f"⚡ Feed Amount: {task['percent']}%")
            print("=" * 40 + "\n")
            return



    def __del__(self):
        self.running = False
        try:
            if hasattr(self, 'movement_module'): self.movement_module.__del__()
            if hasattr(self, 'fluidics_module'): self.fluidics_module.__del__()
            if hasattr(self, 'cv_module'): self.cv_module.__del__()
        except:
            pass
        print(f"[CONTROL_UNIT]: shutting down...")
