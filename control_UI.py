import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QGridLayout, QPushButton, QLabel,
                               QListWidget, QListWidgetItem, QDateTimeEdit,
                               QSlider, QProgressBar, QFrame, QScrollArea,
                               QSizePolicy)
from PySide6.QtCore import Qt, QDateTime
from PySide6.QtGui import QColor


# ============================================================================
# 1. LOGIC CONTROLLER (THE BRAIN)
# ============================================================================
class RobotBackend:
    """
    Same backend logic as before.
    """

    def __init__(self):
        self.scheduled_feeds = []

    def handle_well_click(self, plate_id, row, col, current_state):
        print(f"[LOGIC] Cell clicked: Plate {plate_id}, Row {row}, Col {col}")
        if current_state == "empty":
            return "selected"
        elif current_state == "selected":
            return "fed"
        else:
            return "empty"

    def schedule_feed(self, datetime_obj, percentage):
        time_str = datetime_obj.toString("yyyy-MM-dd HH:mm")
        print(f"[LOGIC] Scheduled feed for {time_str} at {percentage}% flow.")
        return f"{time_str} - {percentage}% Intensity"


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
        self.state = "empty"

        # Force styling to ensure visibility regardless of system theme
        self.setStyleSheet("""
            QPushButton {
                background-color: #e0e0e0;
                border-radius: 12px;
                border: 1px solid #bdc3c7;
            }
            QPushButton:hover {
                background-color: #d6eaf8;
            }
        """)
        self.clicked.connect(self.on_click)

    def on_click(self):
        new_state = self.backend.handle_well_click(self.plate_id, self.row, self.col, self.state)
        self.state = new_state
        self.update_color()

    def update_color(self):
        if self.state == "selected":
            color = "#f39c12"  # Orange
        elif self.state == "fed":
            color = "#27ae60"  # Green
        else:
            color = "#e0e0e0"  # Grey

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
        self.rows, self.cols = rows, columns
        self.setFrameShape(QFrame.StyledPanel)
        # Added explicit color for the label text inside the frame
        self.setStyleSheet("""
            QFrame {
                background-color: #ffffff; 
                border-radius: 10px; 
                border: 1px solid #ccc;
            }
            QLabel {
                color: #333333;
                font-weight: bold;
                border: none;
            }
        """)

        layout = QVBoxLayout()

        title = QLabel(f"Matrix #{plate_id}")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        grid_layout = QGridLayout()
        grid_layout.setSpacing(4)

        for r in range(self.rows):
            for c in range(self.cols):
                well = LarvaWell(plate_id, r, c, backend)
                grid_layout.addWidget(well, r, c)

        layout.addLayout(grid_layout)
        self.setLayout(layout)


class ControlPanel(QFrame):
    def __init__(self, backend, list_widget):
        super().__init__()
        self.backend = backend
        self.list_widget = list_widget

        self.setFrameShape(QFrame.StyledPanel)

        # FIX: Explicitly set text color (color: #333333) so it's visible
        # on the light background (#f4f6f7)
        self.setStyleSheet("""
            QFrame {
                background-color: #f4f6f7; 
                border-radius: 10px;
            }
            QLabel {
                color: #333333;
                font-size: 14px;
            }
        """)

        layout = QVBoxLayout()
        layout.setSpacing(20)

        # 1. Slider
        slider_layout = QVBoxLayout()
        self.lbl_percent = QLabel("Feed Intensity: 50%")
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(50)
        self.slider.valueChanged.connect(lambda v: self.lbl_percent.setText(f"Feed Intensity: {v}%"))

        slider_layout.addWidget(self.lbl_percent)
        slider_layout.addWidget(self.slider)

        # 2. Date/Time
        dt_layout = QVBoxLayout()
        lbl_time = QLabel("Schedule Time:")
        self.dt_edit = QDateTimeEdit(QDateTime.currentDateTime())
        self.dt_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.dt_edit.setCalendarPopup(True)
        # Fix text color for the input box specifically
        self.dt_edit.setStyleSheet("color: #333333; background-color: white;")

        dt_layout.addWidget(lbl_time)
        dt_layout.addWidget(self.dt_edit)

        # 3. Button
        self.btn_schedule = QPushButton("Add to Schedule")
        self.btn_schedule.setMinimumHeight(40)
        self.btn_schedule.setStyleSheet("""
            QPushButton { background-color: #3498db; color: white; border-radius: 5px; font-weight: bold; }
            QPushButton:hover { background-color: #2980b9; }
        """)
        self.btn_schedule.clicked.connect(self.add_schedule)

        layout.addLayout(slider_layout)
        layout.addLayout(dt_layout)
        layout.addWidget(self.btn_schedule)
        layout.addStretch()

        self.setLayout(layout)

    def add_schedule(self):
        result_text = self.backend.schedule_feed(self.dt_edit.dateTime(), self.slider.value())
        item = QListWidgetItem(result_text)
        # Ensure list items are also visible
        item.setForeground(QColor("#333333"))
        self.list_widget.addItem(item)


# ============================================================================
# 3. MAIN WINDOW
# ============================================================================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ARIS - Larvae Feeding Control")
        self.resize(1000, 700)  # Slightly taller default size

        self.backend = RobotBackend()

        central_widget = QWidget()
        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # --- LEFT COLUMN (SCROLLABLE) ---
        # 1. Create a Scroll Area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # Only scroll vertically
        scroll_area.setStyleSheet("border: none; background-color: transparent;")

        # 2. Create a container widget to go INSIDE the scroll area
        left_container = QWidget()
        # FIX: Changed to QVBoxLayout (Vertical) instead of HBox
        left_layout = QVBoxLayout()
        left_layout.setSpacing(15)  # Space between matrices

        self.plate1 = LarvaPlate(1, self.backend, 6, 8)
        self.plate2 = LarvaPlate(2, self.backend, 4, 6)
        self.plate3 = LarvaPlate(3, self.backend, 4, 6)

        left_layout.addWidget(self.plate1)
        left_layout.addWidget(self.plate2)
        left_layout.addWidget(self.plate3)
        left_container.setLayout(left_layout)

        # 3. Set the container as the scroll area's widget
        scroll_area.setWidget(left_container)

        # --- RIGHT COLUMN ---
        self.schedule_list = QListWidget()
        self.schedule_list.setStyleSheet("""
            QListWidget { background-color: white; border-radius: 10px; border: 1px solid #ccc; color: #333; }
        """)

        # --- MIDDLE COLUMN ---
        self.controls = ControlPanel(self.backend, self.schedule_list)

        # Add to Main Layout
        # Notice we add 'scroll_area' instead of 'left_container' directly
        main_layout.addWidget(scroll_area, 4)
        main_layout.addWidget(self.controls, 3)
        main_layout.addWidget(self.schedule_list, 3)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet("font-family: 'Segoe UI', sans-serif; font-size: 14px;")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())