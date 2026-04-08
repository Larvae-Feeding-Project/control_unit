import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QGridLayout, QPushButton, QLabel,
                               QListWidget, QListWidgetItem, QDateTimeEdit,
                               QSlider, QFrame, QScrollArea, QMenu)
from PySide6.QtCore import Qt, QDateTime, QObject, Signal
from PySide6.QtGui import QColor, QIcon, QAction
from enum import Enum

from control_module import ControlUnit

class ControlBridge(QObject):
    task_added = Signal(int, str)
    task_executed = Signal(int)
    task_deleted = Signal(int)

    def __init__(self, control_unit):
        super().__init__()
        self.cu = control_unit
        self.cu.on_task_added = self.task_added.emit
        self.cu.on_task_executed = self.task_executed.emit
        self.cu.on_task_deleted = self.task_deleted.emit

class WellState(Enum):
    DISABLED = 0
    MANUAL = 1
    CALCULATED = 2
    def next(self):
        return WellState((self.value + 1) % len(WellState))

class LarvaWell(QPushButton):
    def __init__(self, plate_id, row, col, control_unit):
        super().__init__()
        self.setFixedSize(25, 25)
        self.plate_id, self.row, self.col = plate_id, row, col
        self.control_unit = control_unit
        self.state = WellState.CALCULATED
        self.clicked.connect(self.on_click)
        self.update_color()

    def on_click(self): self.set_state(self.state.next())
    def set_state(self, new_state):
        self.state = new_state
        self.update_color()

    def update_color(self):
        if self.state == WellState.MANUAL: color = "#f39c12"
        elif self.state == WellState.CALCULATED: color = "#3498db"
        else: color = "#bdc3c7"
        self.setStyleSheet(f"QPushButton {{ background-color: {color}; border-radius: 12px; border: 1px solid #7f8c8d; }}")

class LarvaPlate(QFrame):
    def __init__(self, plate_id, control_unit, rows, columns):
        super().__init__()
        self.plate_id, self.rows, self.cols = plate_id, rows, columns
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("QFrame { background-color: #ffffff; border-radius: 10px; border: 1px solid #ccc; }")

        layout = QVBoxLayout()
        header_layout = QHBoxLayout()
        title = QLabel(f"Matrix #{plate_id}")
        title.setStyleSheet("color: #333333; font-weight: bold; border: none; font-size: 14px;")

        # --- REVERTED TO ORIGINAL EXPLICIT BUTTONS ---
        btn_box = QHBoxLayout()
        btn_box.setSpacing(5)

        btn_calc = QPushButton("Calc")
        btn_calc.setFixedSize(50, 25)
        btn_calc.setStyleSheet("background-color: #3498db; color: white; border-radius: 4px; border: none; font-weight: bold; font-size: 11px;")
        btn_calc.clicked.connect(lambda: self.set_plate_state(WellState.CALCULATED))

        btn_man = QPushButton("Man")
        btn_man.setFixedSize(50, 25)
        btn_man.setStyleSheet("background-color: #f39c12; color: white; border-radius: 4px; border: none; font-weight: bold; font-size: 11px;")
        btn_man.clicked.connect(lambda: self.set_plate_state(WellState.MANUAL))

        btn_dis = QPushButton("Dis")
        btn_dis.setFixedSize(50, 25)
        btn_dis.setStyleSheet("background-color: #bdc3c7; color: black; border-radius: 4px; border: none; font-weight: bold; font-size: 11px;")
        btn_dis.clicked.connect(lambda: self.set_plate_state(WellState.DISABLED))

        btn_box.addWidget(btn_calc)
        btn_box.addWidget(btn_man)
        btn_box.addWidget(btn_dis)

        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addLayout(btn_box)
        layout.addLayout(header_layout)

        grid_layout = QGridLayout()
        grid_layout.setSpacing(4)
        for r in range(self.rows):
            for c in range(self.cols):
                grid_layout.addWidget(LarvaWell(plate_id, r, c, control_unit), r, c)

        layout.addLayout(grid_layout)
        self.setLayout(layout)

    def set_plate_state(self, new_state):
        for well in self.findChildren(LarvaWell): well.set_state(new_state)

    def get_snapshot_data(self):
        return {'plate_id': self.plate_id, 'wells': [{'row': w.row, 'col': w.col, 'state': w.state} for w in self.findChildren(LarvaWell)]}

class ControlPanel(QFrame):
    def __init__(self, control_unit, list_widget, plates):
        super().__init__()
        self.control_unit, self.list_widget, self.plates = control_unit, list_widget, plates
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("QFrame { background-color: #f4f6f7; border-radius: 10px; } QLabel { color: #333333; font-size: 14px; }")

        layout = QVBoxLayout()
        layout.setSpacing(20)

        slider_layout = QVBoxLayout()
        self.lbl_percent = QLabel("Feed percentage: 50%")
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(50)
        self.slider.valueChanged.connect(lambda v: self.lbl_percent.setText(f"Feed percentage: {v}%"))
        slider_layout.addWidget(self.lbl_percent)
        slider_layout.addWidget(self.slider)

        dt_layout = QVBoxLayout()
        self.dt_edit = QDateTimeEdit(QDateTime.currentDateTime())
        self.dt_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.dt_edit.setCalendarPopup(True)
        dt_layout.addWidget(QLabel("Schedule Time:"))
        dt_layout.addWidget(self.dt_edit)

        self.btn_schedule = QPushButton("Add to Schedule")
        self.btn_schedule.setMinimumHeight(40)
        self.btn_schedule.setStyleSheet("QPushButton { background-color: #34495e; color: white; border-radius: 5px; font-weight: bold; }")
        self.btn_schedule.clicked.connect(self.add_schedule)

        # --- REVERTED TO ORIGINAL EXPLICIT BUTTONS ---
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
        layout.addLayout(slider_layout)
        layout.addWidget(self.btn_schedule)
        layout.addLayout(button_layout)
        layout.addStretch()
        self.setLayout(layout)

    def change_all(self, new_state):
        for plate in self.plates: plate.set_plate_state(new_state)

    def add_schedule(self):
        full_snapshot = [plate.get_snapshot_data() for plate in self.plates]
        self.control_unit.add_feed_task(self.dt_edit.dateTime().toPython(), self.slider.value(), full_snapshot)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ARIS - Larvae Feeding Control")
        self.resize(1100, 700)

        self.control_unit = ControlUnit()
        self.bridge = ControlBridge(self.control_unit)

        self.bridge.task_added.connect(self.ui_add_item)
        self.bridge.task_executed.connect(self.ui_remove_item)
        self.bridge.task_deleted.connect(self.ui_remove_item)

        central_widget = QWidget()
        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("border: none; background-color: transparent;")

        left_container = QWidget()
        left_layout = QVBoxLayout()
        self.plate1 = LarvaPlate(1, self.control_unit, 6, 8)
        self.plate2 = LarvaPlate(2, self.control_unit, 4, 6)
        self.plate3 = LarvaPlate(3, self.control_unit, 4, 6)
        left_layout.addWidget(self.plate1); left_layout.addWidget(self.plate2); left_layout.addWidget(self.plate3)
        left_container.setLayout(left_layout)
        scroll_area.setWidget(left_container)

        self.schedule_list = QListWidget()
        self.schedule_list.setStyleSheet("background-color: white; border-radius: 10px; border: 1px solid #ccc; color: #333;")
        self.schedule_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.schedule_list.customContextMenuRequested.connect(self.show_context_menu)

        self.controls = ControlPanel(self.control_unit, self.schedule_list, [self.plate1, self.plate2, self.plate3])

        main_layout.addWidget(scroll_area, 4); main_layout.addWidget(self.controls, 3); main_layout.addWidget(self.schedule_list, 3)

    def ui_add_item(self, task_id, text):
        item = QListWidgetItem(text)
        item.setData(Qt.UserRole, task_id)
        self.schedule_list.addItem(item)

    def ui_remove_item(self, task_id):
        for i in range(self.schedule_list.count()):
            if self.schedule_list.item(i).data(Qt.UserRole) == task_id:
                self.schedule_list.takeItem(i)
                break

    def show_context_menu(self, pos):
        item = self.schedule_list.itemAt(pos)
        if not item: return
        menu = QMenu()
        delete_action = QAction("Delete Feeding", self)
        delete_action.triggered.connect(lambda: self.control_unit.delete_feed(item.data(Qt.UserRole)))
        menu.addAction(delete_action)
        menu.exec(self.schedule_list.mapToGlobal(pos))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet("font-family: 'Segoe UI', sans-serif; font-size: 14px;")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())