import sys
import uuid  # For creating unique IDs for every feed
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QGridLayout, QPushButton, QLabel,
                               QListWidget, QListWidgetItem, QDateTimeEdit,
                               QSlider, QFrame, QScrollArea, QMenu)
from PySide6.QtCore import Qt, QDateTime, QTimer, QObject, Signal
from PySide6.QtGui import QColor, QIcon, QAction
from enum import Enum

# ============================================================================
# 1. LOGIC CONTROLLER
# ============================================================================
class RobotBackend(QObject):  # Inherit from QObject to use Signals & Timers
    # Signal to tell the UI to remove an item visually when it executes
    feed_triggered = Signal(str)

    def __init__(self):
        super().__init__()
        self.scheduled_feeds = []  # Will store: {'id': uuid, 'time': dt, 'percent': 50, 'snapshot': [...]}

        # --- TIMING MECHANISM ---
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_schedule)
        self.timer.start(1000)  # Check every 1 second


    def schedule_feed(self, datetime_obj, percentage, snapshot_data):
        """
        Receives the time, percentage, AND the full snapshot of the plates.
        Saves them together as one distinct task.
        """
        # Create a unique ID for this specific task
        task_id = str(uuid.uuid4())

        feed_task = {
            'id': task_id,
            'time': datetime_obj,
            'percent': percentage,
            'snapshot': snapshot_data  # The frozen state of the grid
        }

        self.scheduled_feeds.append(feed_task)

        # Sort by time so the earliest feed is first
        self.scheduled_feeds.sort(key=lambda x: x['time'])

        time_str = datetime_obj.toString("yyyy-MM-dd HH:mm")
        print(f"[LOGIC] Scheduled Feed {task_id[:8]}... for {time_str}")

        # Return the ID so the UI can attach it to the list item
        display_text = f"{time_str} - {percentage}% of the larvae volume"
        return task_id, display_text

    def delete_feed(self, task_id):
        """Removes a feed from the internal memory based on ID."""
        initial_count = len(self.scheduled_feeds)
        # Keep only feeds that DO NOT match the ID
        self.scheduled_feeds = [f for f in self.scheduled_feeds if f['id'] != task_id]

        if len(self.scheduled_feeds) < initial_count:
            print(f"[LOGIC] Deleted feed {task_id[:8]}... from memory.")

    def check_schedule(self):
        """Called every second to see if it's time to feed."""
        now = QDateTime.currentDateTime()

        # Iterate over a copy so we can remove items safely
        for task in self.scheduled_feeds[:]:
            if now >= task['time']:
                self.execute_robot(task)

                # Remove from memory
                self.scheduled_feeds.remove(task)

                # Tell UI to remove it from the list
                self.feed_triggered.emit(task['id'])

    def execute_robot(self, task):
        """Actual Robot Trigger Logic"""
        print("\n" + "=" * 40)
        print(f"⚡ ROBOT STARTING! Time: {task['time'].toString()}")
        print(f"⚡ Feed Amount: {task['percent']}%")
        print(f"⚡ Snapshot Data Loaded: {len(task['snapshot'])} matrices found.")
        # Here you would loop through task['snapshot'] to send commands to drivers
        # for plate in task['snapshot']:
        #    ... send serial commands ...
        print("=" * 40 + "\n")


# ============================================================================
# 2. UI COMPONENTS
# ============================================================================


class WellState(Enum):
    """
    This enum represents the 3 states a well can be in: Disabled, Manual or Calculated
    """
    DISABLED = 0
    MANUAL = 1
    CALCULATED = 2

    def next(self):
        return WellState((self.value + 1) % len(WellState))

class LarvaWell(QPushButton):
    def __init__(self, plate_id, row, col, backend):
        super().__init__()
        self.setFixedSize(25, 25)
        self.plate_id = plate_id
        self.row = row
        self.col = col
        self.backend = backend
        self.state = WellState.CALCULATED

        self.clicked.connect(self.on_click)
        self.update_color()

    def on_click(self):
        """
        Changes the state of the well in cyclic order using WellState ENUM
        :return: VOID
        """
        self.set_state(self.state.next())

    def set_state(self, new_state):
        """
        Sets the state of the well Manually
        :param new_state: new state to insert
        :return: VOID
        """
        self.state = new_state
        self.update_color()

    def update_color(self):
        """
        Sets the color of the well based on the given state
        Activated whenever there is a state change
        :return: VOID
        """
        if self.state == WellState.MANUAL:
            color = "#f39c12"  # Orange
        elif self.state == WellState.CALCULATED:
            color = "#3498db"  # Blue
        else:
            color = "#bdc3c7"  # Grey (Disabled)

        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                border-radius: 12px;
                border: 1px solid #7f8c8d;
            }}
        """)


class LarvaPlate(QFrame):
    def __init__(self, plate_id, backend, rows, columns):
        super().__init__()
        self.plate_id = plate_id
        self.rows = rows
        self.cols = columns
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("""
            QFrame {
                background-color: #ffffff; 
                border-radius: 10px; 
                border: 1px solid #ccc;
            }
        """)

        layout = QVBoxLayout()

        # --- HEADER ---
        header_layout = QHBoxLayout()
        title = QLabel(f"Matrix #{plate_id}")
        title.setStyleSheet("color: #333333; font-weight: bold; border: none; font-size: 14px;")

        btn_box = QHBoxLayout()
        btn_box.setSpacing(5)

        btn_calc = QPushButton("Calc")
        btn_calc.setFixedSize(50, 25)
        btn_calc.setStyleSheet(
            "background-color: #3498db; color: white; border-radius: 4px; border: none; font-weight: bold; font-size: 11px;")
        btn_calc.clicked.connect(lambda: self.set_plate_state(WellState.CALCULATED))

        btn_man = QPushButton("Man")
        btn_man.setFixedSize(50, 25)
        btn_man.setStyleSheet(
            "background-color: #f39c12; color: white; border-radius: 4px; border: none; font-weight: bold; font-size: 11px;")
        btn_man.clicked.connect(lambda: self.set_plate_state(WellState.MANUAL))

        btn_dis = QPushButton("Dis")
        btn_dis.setFixedSize(50, 25)
        btn_dis.setStyleSheet(
            "background-color: #bdc3c7; color: black; border-radius: 4px; border: none; font-weight: bold; font-size: 11px;")
        btn_dis.clicked.connect(lambda: self.set_plate_state(WellState.DISABLED))

        btn_box.addWidget(btn_calc)
        btn_box.addWidget(btn_man)
        btn_box.addWidget(btn_dis)

        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addLayout(btn_box)
        layout.addLayout(header_layout)

        # --- GRID ---
        grid_layout = QGridLayout()
        grid_layout.setSpacing(4)

        for r in range(self.rows):
            for c in range(self.cols):
                well = LarvaWell(plate_id, r, c, backend)
                grid_layout.addWidget(well, r, c)

        layout.addLayout(grid_layout)
        self.setLayout(layout)

    def set_plate_state(self, new_state):
        """
        Sets the status of all the wells in the plate to the given new_state
        :param new_state: State to change all the wells to.
        :return: VOID
        """
        print(f"[UI] Matrix PLATE Override: Setting all to {new_state}")
        for well in self.findChildren(LarvaWell):
            well.set_state(new_state)

    def get_snapshot_data(self):
        """
        Captures the exact state of every well in this plate.
        Returns a dictionary.
        """
        wells_data = []
        # findChildren finds all buttons. Note: Order is usually creation order.
        # For strict ordering, we could sort by row/col, but this is usually sufficient.
        for well in self.findChildren(LarvaWell):
            wells_data.append({
                'row': well.row,
                'col': well.col,
                'state': well.state
            })

        return {
            'plate_id': self.plate_id,
            'wells': wells_data
        }


class ControlPanel(QFrame):
    def __init__(self, backend, list_widget, plates):
        super().__init__()
        self.backend = backend
        self.list_widget = list_widget
        self.plates = plates

        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("""
            QFrame { background-color: #f4f6f7; border-radius: 10px; }
            QLabel { color: #333333; font-size: 14px; }
        """)

        layout = QVBoxLayout()
        layout.setSpacing(20)

        # Formula slider
        slider_layout = QVBoxLayout()
        self.lbl_percent = QLabel("Feed percentage: 50%")
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(50)
        self.slider.valueChanged.connect(lambda v: self.lbl_percent.setText(f"Feed percentage: {v}%"))
        slider_layout.addWidget(self.lbl_percent)
        slider_layout.addWidget(self.slider)

        # Date&Time box
        dt_layout = QVBoxLayout()
        lbl_time = QLabel("Schedule Time:")
        self.dt_edit = QDateTimeEdit(QDateTime.currentDateTime())
        self.dt_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.dt_edit.setCalendarPopup(True)
        self.dt_edit.setStyleSheet("color: #333333; background-color: white;")
        dt_layout.addWidget(lbl_time)
        dt_layout.addWidget(self.dt_edit)

        # Add to Schedule Button
        self.btn_schedule = QPushButton("Add to Schedule")
        self.btn_schedule.setMinimumHeight(40)
        self.btn_schedule.setStyleSheet("""
            QPushButton { background-color: #34495e; color: white; border-radius: 5px; font-weight: bold; }
            QPushButton:hover { background-color: #2c3e50; }
        """)
        self.btn_schedule.clicked.connect(self.add_schedule)

        # Global Control Buttons
        button_layout = QHBoxLayout()

        self.btn_calc = QPushButton("All Calc")
        self.btn_calc.setStyleSheet("background-color: #3498db; color: white; padding: 5px; border-radius: 4px;")
        self.btn_calc.clicked.connect(lambda: self.change_all(WellState.CALCULATED))

        self.btn_man = QPushButton("All Manual")
        self.btn_man.setStyleSheet("background-color: #f39c12; color: white; padding: 5px; border-radius: 4px;")
        self.btn_man.clicked.connect(lambda: self.change_all(WellState.MANUAL))

        self.btn_dis = QPushButton("All Disable")
        self.btn_dis.setStyleSheet("background-color: #bdc3c7; color: black; padding: 5px; border-radius: 4px;")
        self.btn_dis.clicked.connect(lambda: self.change_all(WellState.DISABLED))

        button_layout.addWidget(self.btn_calc)
        button_layout.addWidget(self.btn_man)
        button_layout.addWidget(self.btn_dis)

        layout.addLayout(dt_layout)
        layout.addWidget(self.btn_schedule)
        layout.addLayout(slider_layout)
        layout.addLayout(button_layout)
        layout.addStretch()

        self.setLayout(layout)

    def add_schedule(self):
        # 1. Gather Snapshot of current visual state
        full_snapshot = []
        for plate in self.plates:
            full_snapshot.append(plate.get_snapshot_data())

        # 2. Send to Backend
        task_id, display_text = self.backend.schedule_feed(
            self.dt_edit.dateTime(),
            self.slider.value(),
            full_snapshot
        )

        # 3. Add to UI List with Hidden ID
        item = QListWidgetItem(display_text)
        item.setForeground(QColor("#333333"))

        # STORE DATA: We save the task_id inside the item itself
        item.setData(Qt.UserRole, task_id)

        self.list_widget.addItem(item)

    def change_all(self, new_state):
        for plate in self.plates:
            plate.set_plate_state(new_state)


# ============================================================================
# MAIN WINDOW
# ============================================================================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ARIS - Larvae Feeding Control")
        # Ensure this file exists in your directory
        self.setWindowIcon(QIcon("no_backround_icon.png"))
        self.resize(1100, 700)

        self.backend = RobotBackend()
        # Listen for when a feed is done so we can remove it from list
        self.backend.feed_triggered.connect(self.remove_feed_by_id)

        central_widget = QWidget()
        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # --- LEFT COLUMN (SCROLLABLE) ---
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("border: none; background-color: transparent;")

        left_container = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setSpacing(15)

        # Create Plates
        self.plate1 = LarvaPlate(1, self.backend, 6, 8)
        self.plate2 = LarvaPlate(2, self.backend, 4, 6)
        self.plate3 = LarvaPlate(3, self.backend, 4, 6)

        left_layout.addWidget(self.plate1)
        left_layout.addWidget(self.plate2)
        left_layout.addWidget(self.plate3)
        left_container.setLayout(left_layout)
        scroll_area.setWidget(left_container)

        # --- Schedule (right column) ---
        self.schedule_list = QListWidget()
        self.schedule_list.setStyleSheet(
            "background-color: white; border-radius: 10px; border: 1px solid #ccc; color: #333;")

        # ENABLE RIGHT CLICK CONTEXT MENU
        self.schedule_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.schedule_list.customContextMenuRequested.connect(self.show_context_menu)

        # --- Control panel (middle column) ---
        self.controls = ControlPanel(self.backend, self.schedule_list, [self.plate1, self.plate2, self.plate3])

        # Add to Main Layout
        main_layout.addWidget(scroll_area, 4)
        main_layout.addWidget(self.controls, 3)
        main_layout.addWidget(self.schedule_list, 3)

    def show_context_menu(self, position):
        """Creates the Right-Click Menu"""
        item = self.schedule_list.itemAt(position)
        if not item:
            return  # User clicked on whitespace

        menu = QMenu()
        delete_action = QAction("Delete Feeding", self)
        delete_action.triggered.connect(lambda: self.delete_item(item))
        menu.addAction(delete_action)

        # Show menu at mouse position
        menu.exec(self.schedule_list.mapToGlobal(position))

    def delete_item(self, item):
        """Removes from UI and Backend"""
        # 1. Get the Hidden ID
        task_id = item.data(Qt.UserRole)

        # 2. Tell Backend to delete data
        self.backend.delete_feed(task_id)

        # 3. Remove from UI
        row = self.schedule_list.row(item)
        self.schedule_list.takeItem(row)

    def remove_feed_by_id(self, task_id):
        """Auto-remove from list when timer executes"""
        for i in range(self.schedule_list.count()):
            item = self.schedule_list.item(i)
            if item.data(Qt.UserRole) == task_id:
                self.schedule_list.takeItem(i)
                break


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet("font-family: 'Segoe UI', sans-serif; font-size: 14px;")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())