import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QGridLayout, QPushButton, QLabel,
                               QListWidget, QListWidgetItem, QDateTimeEdit,
                               QSlider, QFrame, QScrollArea)
from PySide6.QtCore import Qt, QDateTime
from PySide6.QtGui import QColor


# ============================================================================
# 1. LOGIC CONTROLLER
# ============================================================================
class RobotBackend:
    def __init__(self):
        self.scheduled_feeds = []

    def handle_well_click(self, plate_id, row, col, current_state):
        print(f"[LOGIC] Cell clicked: Plate {plate_id}, Row {row}, Col {col}")
        # Cycle through states: Disabled -> Manual -> Calculated -> Disabled
        if current_state == "disabled":
            return "manual"
        elif current_state == "manual":
            return "calculated"
        else:
            return "disabled"

    def schedule_feed(self, datetime_obj, percentage):
        time_str = datetime_obj.toString("yyyy-MM-dd HH:mm")
        print(f"[LOGIC] Scheduled feed for {time_str} at {percentage}% flow.")
        return f"{time_str} - {percentage}% of the larvae volume"


# ============================================================================
# 2. UI COMPONENTS
# ============================================================================

class LarvaWell(QPushButton):
    def __init__(self, plate_id, row, col, backend):
        super().__init__()
        self.setFixedSize(25, 25)
        self.plate_id = plate_id
        self.row = row
        self.col = col
        self.backend = backend
        self.state = "disabled"

        self.clicked.connect(self.on_click)
        self.update_color()

    def on_click(self):
        new_state = self.backend.handle_well_click(self.plate_id, self.row, self.col, self.state)
        self.set_state(new_state)

    def set_state(self, new_state):
        self.state = new_state
        self.update_color()

    def update_color(self):
        if self.state == "manual":
            color = "#f39c12"  # Orange
        elif self.state == "calculated":
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

        # Main Vertical Layout for the Plate
        layout = QVBoxLayout()

        # --- HEADER (Title + 3 Local Control Buttons) ---
        header_layout = QHBoxLayout()

        # Title
        title = QLabel(f"Matrix #{plate_id}")
        title.setStyleSheet("color: #333333; font-weight: bold; border: none; font-size: 14px;")

        # Button Container (to keep them grouped tightly on the right)
        btn_box = QHBoxLayout()
        btn_box.setSpacing(5)

        # 1. Local Calculated Button
        btn_calc = QPushButton("Calc")
        btn_calc.setFixedSize(50, 25)
        btn_calc.setCursor(Qt.PointingHandCursor)
        btn_calc.setStyleSheet("""
            QPushButton { background-color: #3498db; color: white; border-radius: 4px; border: none; font-weight: bold; font-size: 11px;}
            QPushButton:hover { background-color: #2980b9; }
        """)
        btn_calc.clicked.connect(lambda: self.set_plate_state("calculated"))

        # 2. Local Manual Button
        btn_man = QPushButton("Man")
        btn_man.setFixedSize(50, 25)
        btn_man.setCursor(Qt.PointingHandCursor)
        btn_man.setStyleSheet("""
            QPushButton { background-color: #f39c12; color: white; border-radius: 4px; border: none; font-weight: bold; font-size: 11px;}
            QPushButton:hover { background-color: #e67e22; }
        """)
        btn_man.clicked.connect(lambda: self.set_plate_state("manual"))

        # 3. Local Disable Button
        btn_dis = QPushButton("Dis")
        btn_dis.setFixedSize(50, 25)
        btn_dis.setCursor(Qt.PointingHandCursor)
        btn_dis.setStyleSheet("""
            QPushButton { background-color: #bdc3c7; color: black; border-radius: 4px; border: none; font-weight: bold; font-size: 11px;}
            QPushButton:hover { background-color: #95a5a6; }
        """)
        btn_dis.clicked.connect(lambda: self.set_plate_state("disabled"))

        # Add buttons to the box
        btn_box.addWidget(btn_calc)
        btn_box.addWidget(btn_man)
        btn_box.addWidget(btn_dis)

        # Assemble Header
        header_layout.addWidget(title)
        header_layout.addStretch()  # Pushes buttons to the right
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
        """Sets the state for ALL wells in THIS plate only."""
        print(f"[UI] Matrix Local Override: Setting all to {new_state}")
        for well in self.findChildren(LarvaWell):
            well.set_state(new_state)


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

        # 1. Slider
        slider_layout = QVBoxLayout()
        self.lbl_percent = QLabel("Feed percentage: 50%")
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(50)
        self.slider.valueChanged.connect(lambda v: self.lbl_percent.setText(f"Feed percentage: {v}%"))
        slider_layout.addWidget(self.lbl_percent)
        slider_layout.addWidget(self.slider)

        # 2. Date/Time
        dt_layout = QVBoxLayout()
        lbl_time = QLabel("Schedule Time:")
        self.dt_edit = QDateTimeEdit(QDateTime.currentDateTime())
        self.dt_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.dt_edit.setCalendarPopup(True)
        self.dt_edit.setStyleSheet("color: #333333; background-color: white;")
        dt_layout.addWidget(lbl_time)
        dt_layout.addWidget(self.dt_edit)

        # 3. Add to Schedule Button
        self.btn_schedule = QPushButton("Add to Schedule")
        self.btn_schedule.setMinimumHeight(40)
        self.btn_schedule.setStyleSheet("""
            QPushButton { background-color: #34495e; color: white; border-radius: 5px; font-weight: bold; }
            QPushButton:hover { background-color: #2c3e50; }
        """)
        self.btn_schedule.clicked.connect(self.add_schedule)


        button_layout = QHBoxLayout()

        self.btn_calc = QPushButton("All Calc")
        self.btn_calc.setStyleSheet("background-color: #3498db; color: white; padding: 5px; border-radius: 4px;")
        self.btn_calc.clicked.connect(lambda: self.change_all("calculated"))

        self.btn_man = QPushButton("All Manual")
        self.btn_man.setStyleSheet("background-color: #f39c12; color: white; padding: 5px; border-radius: 4px;")
        self.btn_man.clicked.connect(lambda: self.change_all("manual"))

        self.btn_dis = QPushButton("All Disable")
        self.btn_dis.setStyleSheet("background-color: #bdc3c7; color: black; padding: 5px; border-radius: 4px;")
        self.btn_dis.clicked.connect(lambda: self.change_all("disabled"))

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
        result_text = self.backend.schedule_feed(self.dt_edit.dateTime(), self.slider.value())
        item = QListWidgetItem(result_text)
        item.setForeground(QColor("#333333"))
        self.list_widget.addItem(item)

    def change_all(self, new_state):
        for plate in self.plates:
            # Re-use the method we just wrote in LarvaPlate
            plate.set_plate_state(new_state)


# ============================================================================
# 3. MAIN WINDOW
# ============================================================================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ARIS - Larvae Feeding Control")
        self.resize(1100, 800)

        self.backend = RobotBackend()

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

        # --- RIGHT COLUMN ---
        self.schedule_list = QListWidget()
        self.schedule_list.setStyleSheet(
            "background-color: white; border-radius: 10px; border: 1px solid #ccc; color: #333;")

        # --- MIDDLE COLUMN ---
        self.controls = ControlPanel(self.backend, self.schedule_list, [self.plate1, self.plate2, self.plate3])

        # Add to Main Layout
        main_layout.addWidget(scroll_area, 4)
        main_layout.addWidget(self.controls, 3)
        main_layout.addWidget(self.schedule_list, 3)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet("font-family: 'Segoe UI', sans-serif; font-size: 14px;")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())