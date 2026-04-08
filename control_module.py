import threading
import time
from datetime import datetime

# Driver imports
from movement_driver import movement_driver
from fluidics_system import fluidics_module
# from cv_system import cv_module

class ControlUnit:
    def __init__(self):
        """
        Control Unit constructor. Creates movement system, fluidics system and CV objects.
        :return: ControlUnit object
        """
        try:
            # self.fluidics_module = fluidics_module.FluidicsDriver()
            # self.movement_module = movement_driver.MovementDriver()
            # self.cv_module = cv_module()
            pass
        except Exception as e:
            print("One of the subsystem initiations failed!")
            exit(1)

        self.scheduled_feeds = []
        self.feed_identifier = 1
        self.lock = threading.Lock()

        self.running = True

        # UI CALLBACKS
        self.on_task_added = None
        self.on_task_executed = None  # Matches Bridge
        self.on_task_deleted = None

        self.thread = threading.Thread(target=self._run_schedule_loop, daemon=True)
        self.thread.start()

    def add_feed_task(self, python_dt, percentage, snapshot_data):
        with self.lock:
            task_id = self.feed_identifier
            self.feed_identifier += 1

            task = {
                'id': task_id,
                'time': python_dt,
                'percent': percentage,
                'snapshot': snapshot_data
            }
            self.scheduled_feeds.append(task)
            self.scheduled_feeds.sort(key=lambda x: x['time'])

        if self.on_task_added:
            time_str = python_dt.strftime("%Y-%m-%d %H:%M")
            display_text = f"{time_str} - {percentage}% of the larvae volume"
            self.on_task_added(task_id, display_text)

        return task_id

    def delete_feed(self, task_id):
        with self.lock:
            self.scheduled_feeds = [t for t in self.scheduled_feeds if t['id'] != task_id]
        if self.on_task_deleted:
            self.on_task_deleted(task_id)

    def _run_schedule_loop(self):
        while self.running:
            now = datetime.now()
            executed_ids = []

            with self.lock:
                for task in self.scheduled_feeds[:]:
                    if now >= task['time']:
                        self.execute_robot(task)
                        self.scheduled_feeds.remove(task)
                        executed_ids.append(task['id'])

            if self.on_task_executed:
                for tid in executed_ids:
                    self.on_task_executed(tid)

            time.sleep(1)

    def execute_robot(self, task):
        print(f"\n⚡ ROBOT STARTING! Time: {task['time']}")
        print(f"⚡ Feed Amount: {task['percent']}%")
        print("=" * 40 + "\n")

    def __del__(self):
        self.running = False
        try:
            if hasattr(self, 'movement_module'): self.movement_module.__del__()
            if hasattr(self, 'fluidics_module'): self.fluidics_module.__del__()
        except:
            pass