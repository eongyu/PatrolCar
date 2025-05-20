import sys
import can
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QTableWidget, QTableWidgetItem, QLabel, QHBoxLayout, QPushButton,
    QFileDialog, QMessageBox, QHeaderView, QDialog, QLineEdit
)
from PyQt6.QtCore import QTimer
import json

CONFIG_FILE = "can_config.json"

class CANParser:
    def __init__(self):
        pass

    def parse(self, can_id, data):
        parsed = {}
        if can_id == 0x303:
            vehicle_Gear = data[0] & 0x03
            parsed['Vehicle Gear'] = ["P Gear", "D Gear", "N Gear", "R Gear"][vehicle_Gear]

            Drive_State_Mode = data[1] & 0x03
            parsed['Drive_State_Mode'] = ["Remote Control Mode", "Represents the AD Mode",
                                          "Indicates parallel Mode", "Indocates semi-autonomous"][Drive_State_Mode]

            VCU_Speed_Req = int.from_bytes(data[2:4], byteorder='little') * 0.1 - 80
            parsed['Vehicle Speed Request (km/h)'] = f"{VCU_Speed_Req:.1f}"

        elif can_id == 0x314:
            directionalAngle = int.from_bytes(data[1:3], byteorder='little')
            parsed['Direction Angle (deg)'] = f"{directionalAngle}"
            parsed['eps Control'] = "Works" if data[0] & 0x01 else "Stops"

        elif can_id == 0x304:
            speed = int.from_bytes(data[0:2], byteorder='little') * 0.1 - 80
            parsed['Vehicle Speed (km/h)'] = f"{speed:.1f}"
            parsed['Vehicle Wheel End Angle (deg)'] = f"{int.from_bytes(data[4:6], 'little') * 0.1 - 35:.1f}"
            parsed['Vehicle Break Pressure (Mps)'] = f"{int.from_bytes(data[2:4], 'little') * 0.01:.2f}"

        elif can_id == 0x301:
            parsed['Brake Light'] = "ON" if data[5] & 0x01 else "OFF"
            parsed['Head Light'] = "ON" if data[1] & 0x80 else "OFF"
            parsed['Emergency Button'] = "Pressed" if data[0] & 0x01 else "Not Pressed"
            parsed['Back Touch Switch State'] = "trigger" if data[1] & 0x20 else "Not trigger"
            parsed['Front Touch Switch State'] = "trigger" if data[1] & 0x10 else "Not trigger"

        elif can_id == 0x18F:
            parsed['EPS_Current_Angle (deg)'] = str(int.from_bytes(data[1:3], 'little', signed=True))
            parsed['EPS_ECU_Temperature (℃)'] = str(int.from_bytes(data[6:7], 'little', signed=True))

        elif can_id == 0x060:
            parsed['BUS Voltage (V)'] = f"{int.from_bytes(data[0:2], 'little') * 0.1:.2f}"
            parsed['BUS Current (A)'] = f"{int.from_bytes(data[2:4], 'little') * 0.1 - 1000:.2f}"

        elif can_id == 0x160:
            mode = (data[0] & 0x06) >> 1
            parsed['Drive Mode'] = ["Torque", "Speed", "Torque ring", "Speed loop"][mode]
            parsed['MCU_Brake_Request'] = "Hold brake" if data[0] & 0x08 else "Release"
            parsed['MCU Speed Request (RPM)'] = str(int.from_bytes(data[3:6], 'little') - 7000)
            parsed['MCU Torque Request (Nm)'] = f"{int.from_bytes(data[1:3], 'little') * 0.1 - 1000:.1f}"

        elif can_id == 0x0A0:
            parsed['BMS Battery SOH (%)'] = str(data[7])
            parsed['BMS Battery SOC (%)'] = f"{data[4] * 0.4:.2f}"
            parsed['BMS Battery Voltage (V)'] = f"{int.from_bytes(data[2:4], 'little') * 0.1:.2f}"

        return parsed

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Withus CAN Monitor")
        self.resize(1000, 600)
        self.interface_name = self.load_config()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        self.interface_label = QLabel(f"Interface: {self.interface_name}")
        layout.addWidget(self.interface_label)

        table_layout = QHBoxLayout()
        layout.addLayout(table_layout)

        self.raw_table = QTableWidget(0, 3)
        self.raw_table.setHorizontalHeaderLabels(["CAN ID", "DLC", "Data"])
        self.raw_table.setColumnWidth(0, 80)
        self.raw_table.setColumnWidth(1, 80)
        self.raw_table.setColumnWidth(2, 200)

        self.parsed_table = QTableWidget(0, 2)
        self.parsed_table.setHorizontalHeaderLabels(["Name", "Value"])
        self.parsed_table.setColumnWidth(0, 250)
        self.parsed_table.setColumnWidth(1, 250)

        table_layout.addWidget(self.raw_table)
        table_layout.addWidget(self.parsed_table)

        btn_layout = QHBoxLayout()
        layout.addLayout(btn_layout)

        self.btn_connect = QPushButton("Connect CAN")
        self.btn_connect.clicked.connect(self.connect_can_interface)
        btn_layout.addWidget(self.btn_connect)

        self.btn_disconnect = QPushButton("Disconnect CAN")
        self.btn_disconnect.clicked.connect(self.disconnect_can_interface)
        btn_layout.addWidget(self.btn_disconnect)

        self.btn_change_interface = QPushButton("Change Interface")
        self.btn_change_interface.clicked.connect(self.change_interface)
        btn_layout.addWidget(self.btn_change_interface)

        self.btn_clear = QPushButton("Clear Tables")
        self.btn_clear.clicked.connect(self.clear_tables)
        btn_layout.addWidget(self.btn_clear)

        write_layout = QHBoxLayout()
        layout.addLayout(write_layout)

        self.can_id_input = QLineEdit()
        self.can_id_input.setPlaceholderText("CAN ID (e.g., 0x123)")
        self.can_id_input.setFixedWidth(120)
        write_layout.addWidget(self.can_id_input)

        self.data_inputs = []
        for _ in range(8):
            byte_input = QLineEdit()
            byte_input.setPlaceholderText("00")
            byte_input.setFixedWidth(30)
            self.data_inputs.append(byte_input)
            write_layout.addWidget(byte_input)

        self.btn_write = QPushButton("Write CAN")
        self.btn_write.clicked.connect(self.write_can_message)
        write_layout.addWidget(self.btn_write)

        self.bus = None
        self.parser = CANParser()
        self.timer = QTimer()
        self.timer.timeout.connect(self.read_can_messages)

    def show_custom_message(self, title, message, width=400, height=200):
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setFixedSize(width, height)

        layout = QVBoxLayout(dialog)
        label = QLabel(message)
        label.setWordWrap(True)
        layout.addWidget(label)

        button = QPushButton("OK")
        button.clicked.connect(dialog.accept)
        layout.addWidget(button)

        dialog.exec()

    def connect_can_interface(self):
        if self.bus is not None:
            self.show_custom_message("Warning", "CAN is already connected.", 400, 200)
            return
        try:
            self.bus = can.Bus(channel=self.interface_name, bustype='socketcan')
            self.timer.start(50)
            self.show_custom_message("Info", "CAN connected successfully.", 400, 200)
        except Exception as e:
            self.show_custom_message("Error", f"Failed to open CAN interface:\n{e}", 500, 300)
            self.bus = None

    def disconnect_can_interface(self):
        if self.bus is not None:
            self.timer.stop()
            self.bus.shutdown()
            self.bus = None
            self.show_custom_message("Info", "CAN disconnected.", 400, 200)
        else:
            self.show_custom_message("Warning", "CAN is not connected.", 400, 200)

    def write_can_message(self):
        if self.bus is None:
            self.show_custom_message("Error", "CAN interface is not connected.", 400, 200)
            return

        try:
            can_id_text = self.can_id_input.text().strip()
            if can_id_text.startswith("0x") or can_id_text.startswith("0X"):
                can_id = int(can_id_text, 16)
            else:
                can_id = int(can_id_text)

            data = bytearray()
            for i, byte_input in enumerate(self.data_inputs):
                byte_str = byte_input.text().strip()
                if len(byte_str) == 0:
                    raise ValueError(f"Byte {i+1} is empty.")
                value = int(byte_str, 16)
                if not (0 <= value <= 255):
                    raise ValueError(f"Byte {i+1} out of range (00-FF).")
                data.append(value)

            if len(data) != 8:
                raise ValueError("You must enter exactly 8 bytes.")

            msg = can.Message(arbitration_id=can_id, data=data, is_extended_id=False)
            self.bus.send(msg)

            self.show_custom_message("Success", f"Sent CAN ID {hex(can_id)} with data: {data.hex()}", 400, 200)

        except Exception as e:
            self.show_custom_message("Error", f"Failed to send CAN message:\n{e}", 500, 300)

    def read_can_messages(self):
        try:
            for _ in range(100):
                message = self.bus.recv(timeout=0.0)
                if message is None:
                    break
                self.update_raw_table(message)
                self.update_parsed_table(message)
        except Exception as e:
            print(f"CAN receive error: {e}")

    def update_raw_table(self, message):
        can_id_hex = hex(message.arbitration_id)
        row = self.raw_table.rowCount()
        self.raw_table.insertRow(row)
        self.raw_table.setItem(row, 0, QTableWidgetItem(can_id_hex))
        self.raw_table.setItem(row, 1, QTableWidgetItem(str(message.dlc)))
        self.raw_table.setItem(row, 2, QTableWidgetItem(message.data.hex()))

    def update_parsed_table(self, message):
        parsed = self.parser.parse(message.arbitration_id, message.data)
        for name, value in parsed.items():
            updated = False
            for row in range(self.parsed_table.rowCount()):
                item = self.parsed_table.item(row, 0)
                if item and item.text() == name:
                    self.parsed_table.setItem(row, 1, QTableWidgetItem(value))
                    updated = True
                    break
            if not updated:
                row = self.parsed_table.rowCount()
                self.parsed_table.insertRow(row)
                self.parsed_table.setItem(row, 0, QTableWidgetItem(name))
                self.parsed_table.setItem(row, 1, QTableWidgetItem(value))

    def change_interface(self):
        new_interface, ok = QFileDialog.getOpenFileName(self, "Select CAN Interface", "/", "All Files (*)")
        if ok and new_interface:
            self.interface_name = new_interface
            self.save_config()
            self.show_custom_message("Info", "Restart the program to apply the new interface.", 450, 200)

    def clear_tables(self):
        self.raw_table.setRowCount(0)
        self.parsed_table.setRowCount(0)

    def load_config(self):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                return config.get("interface", "can0")
        except:
            return "can0"

    def save_config(self):
        with open(CONFIG_FILE, 'w') as f:
            json.dump({"interface": self.interface_name}, f)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
