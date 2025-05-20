import sys
import time
import can
import json
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QLabel, QHBoxLayout, QPushButton, QFileDialog, QMessageBox, QLineEdit
)
from PyQt6.QtCore import QTimer

CONFIG_FILE = "can_config.json"

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Withus CAN Monitor")
        self.resize(1200, 800)
        self.interface_name = self.load_config()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        self.interface_label = QLabel(f"Interface: {self.interface_name}")
        layout.addWidget(self.interface_label)

        btn_layout = QHBoxLayout()
        self.btn_connect = QPushButton("Connect CAN")
        self.btn_connect.clicked.connect(self.connect_can_interface)
        self.btn_disconnect = QPushButton("Disconnect CAN")
        self.btn_disconnect.clicked.connect(self.disconnect_can_interface)
        self.btn_clear = QPushButton("Clear Tables")
        self.btn_clear.clicked.connect(self.clear_tables)
        for btn in [self.btn_connect, self.btn_disconnect, self.btn_clear]:
            btn_layout.addWidget(btn)
        layout.addLayout(btn_layout)

        table_layout = QHBoxLayout()
        self.raw_table = QTableWidget(0, 3)
        self.raw_table.setHorizontalHeaderLabels(["CAN ID", "DLC", "Data"])
        table_layout.addWidget(self.raw_table)
        layout.addLayout(table_layout)

        control_layout = QHBoxLayout()
        self.speed_input = QLineEdit()
        self.speed_input.setPlaceholderText("Enter Speed (km/h)")
        self.btn_send_drive = QPushButton("Send Drive Command")
        self.btn_send_drive.clicked.connect(self.send_drive_command)
        self.btn_stop = QPushButton("Stop Vehicle")
        self.btn_stop.clicked.connect(self.stop_vehicle)
        control_layout.addWidget(self.speed_input)
        control_layout.addWidget(self.btn_send_drive)
        control_layout.addWidget(self.btn_stop)
        layout.addLayout(control_layout)

        form_layout = QHBoxLayout()
        self.input_id = QLineEdit()
        self.input_id.setPlaceholderText("CAN ID (hex)")
        self.input_data = []
        form_layout.addWidget(self.input_id)
        for i in range(8):
            field = QLineEdit()
            field.setMaxLength(2)
            field.setPlaceholderText(f"{i}")
            self.input_data.append(field)
            form_layout.addWidget(field)
        self.btn_write = QPushButton("Write CAN")
        self.btn_write.clicked.connect(self.send_can_frame)
        form_layout.addWidget(self.btn_write)
        layout.addLayout(form_layout)

        self.bus = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.read_can_messages)

        self.drive_timer = QTimer()
        self.drive_timer.timeout.connect(self.send_repeated_drive_command)
        self.current_speed = 0.0

    def load_config(self):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f).get("interface", "can0")
        except:
            return "can0"

    def connect_can_interface(self):
        if self.bus:
            QMessageBox.warning(self, "Warning", "Already connected.")
            return
        try:
            self.bus = can.Bus(channel=self.interface_name, interface='socketcan')
            self.timer.start(50)
            QMessageBox.information(self, "Info", "CAN connected.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Connection failed:\n{e}")

    def disconnect_can_interface(self):
        if self.bus:
            self.timer.stop()
            self.drive_timer.stop()
            self.bus.shutdown()
            self.bus = None
            QMessageBox.information(self, "Info", "CAN disconnected.")

    def read_can_messages(self):
        try:
            for _ in range(100):
                msg = self.bus.recv(timeout=0.0)
                if msg is None:
                    break
                self.update_raw_table(msg)
        except Exception as e:
            print(f"Read error: {e}")

    def send_can_frame(self):
        try:
            if self.bus is None:
                raise Exception("Not connected.")
            can_id = int(self.input_id.text(), 16)
            data = [int(f.text(), 16) for f in self.input_data if f.text()]
            if len(data) != 8:
                raise ValueError("DLC must be 8.")
            msg = can.Message(arbitration_id=can_id, data=data, is_extended_id=False)
            self.bus.send(msg)
        except Exception as e:
            QMessageBox.critical(self, "Send Error", str(e))

    def send_drive_command(self):
        try:
            if self.bus is None:
                raise Exception("CAN not connected.")
            speed = float(self.speed_input.text())
            self.current_speed = speed
            self.send_drive_frame(speed)
            self.drive_timer.start(500)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def send_drive_frame(self, speed):
        speed_val = int(speed / 0.1)
        linear_v1 = speed_val & 0xFF
        linear_v2 = (speed_val >> 8) & 0xFF
        angular_velocity = int((10 + 30) / 0.1)
        angular_v1 = angular_velocity & 0xFF
        angular_v2 = (angular_velocity >> 8) & 0xFF

        msgs = [
            can.Message(arbitration_id=0x501, data=[0xF1, 0, 0, 0, 0, 0, 0, 0], is_extended_id=False),
            can.Message(arbitration_id=0x503, data=[0xF1, 0, 0, 0, 0, 0, 0, 0], is_extended_id=False),
            can.Message(arbitration_id=0x502, data=[0xF1, 0, 0, 0, angular_v1, angular_v2, 0, 0], is_extended_id=False),
            can.Message(arbitration_id=0x506, data=[0x00, 0, 0, 0, 0, 0, 0, 0], is_extended_id=False),
            can.Message(arbitration_id=0x504, data=[0xF1, 0x00, 0x01, 0x01, 0, 0, linear_v1, linear_v2], is_extended_id=False)
        ]
        for m in msgs:
            self.bus.send(m)
            time.sleep(0.01)

    def send_repeated_drive_command(self):
        self.send_drive_frame(self.current_speed)

    def stop_vehicle(self):
        if self.bus:
            self.drive_timer.stop()
            self.send_drive_frame(0.0)
            QMessageBox.information(self, "정지", "차량 정지 명령 전송됨.")

    def update_raw_table(self, message):
        can_id = hex(message.arbitration_id)
        row_count = self.raw_table.rowCount()
        for row in range(row_count):
            if self.raw_table.item(row, 0).text() == can_id:
                self.raw_table.setItem(row, 1, QTableWidgetItem(str(message.dlc)))
                self.raw_table.setItem(row, 2, QTableWidgetItem(message.data.hex()))
                return
        self.raw_table.insertRow(row_count)
        self.raw_table.setItem(row_count, 0, QTableWidgetItem(can_id))
        self.raw_table.setItem(row_count, 1, QTableWidgetItem(str(message.dlc)))
        self.raw_table.setItem(row_count, 2, QTableWidgetItem(message.data.hex()))

    def clear_tables(self):
        self.raw_table.setRowCount(0)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
