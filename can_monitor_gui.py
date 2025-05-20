
#  sudo ip link set can0 up type can bitrate 500000 
import sys
import subprocess
import can
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QTableWidget, QTableWidgetItem, QLabel, QHBoxLayout, QPushButton,
    QFileDialog, QMessageBox, QHeaderView, QDialog, QLineEdit, QFormLayout,
    QSlider
)
from PyQt6.QtCore import Qt, QTimer
import json

CONFIG_FILE = "can_config.json"

class CANParser:
    def __init__(self):
        pass

    def parse(self, can_id, data):
        parsed = {}
        # parsing logic here (omitted for brevity)
        return parsed

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Withus CAN Monitor")
        self.resize(1200, 1000)
        self.interface_name = self.load_config()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        self.interface_label = QLabel(f"Interface: {self.interface_name}")
        main_layout.addWidget(self.interface_label)

        # Control buttons
        btn_layout = QHBoxLayout()
        main_layout.addLayout(btn_layout)

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

        table_layout = QHBoxLayout()
        main_layout.addLayout(table_layout)

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

        # Write input area - one line layout
        form_layout = QHBoxLayout()
        self.input_id = QLineEdit()
        self.input_id.setPlaceholderText("CAN ID (hex)")
        form_layout.addWidget(self.input_id)
        self.input_data = []
        for i in range(8):
            field = QLineEdit()
            field.setMaxLength(2)
            field.setPlaceholderText(f"{i}")
            self.input_data.append(field)
            form_layout.addWidget(field)
        self.btn_write = QPushButton("Write CAN")
        self.btn_write.clicked.connect(self.send_can_frame)
        form_layout.addWidget(self.btn_write)
        main_layout.addLayout(form_layout)

        # Sliders for command
        self.vel_label = QLabel('Cmd Vel: 0')
        self.steering_label = QLabel('Steering Angle: 0')

        self.vel_slider = QSlider(Qt.Orientation.Horizontal)
        self.vel_slider.setRange(-70, 70)
        self.vel_slider.setValue(0)
        self.vel_slider.valueChanged.connect(self.update_vel_label)

        self.steering_slider = QSlider(Qt.Orientation.Horizontal)
        self.steering_slider.setRange(-30, 30)
        self.steering_slider.setValue(0)
        self.steering_slider.valueChanged.connect(self.update_steering_label)

        self.brake_button = QPushButton('Brake')
        self.brake_button.clicked.connect(self.toggle_brake)
        self.close_button = QPushButton('Close')
        self.close_button.clicked.connect(self.close_app)

        main_layout.addWidget(self.vel_label)
        main_layout.addWidget(self.vel_slider)
        main_layout.addWidget(self.steering_label)
        main_layout.addWidget(self.steering_slider)
        main_layout.addWidget(self.brake_button)
        main_layout.addWidget(self.close_button)

        self.bus = None
        self.parser = CANParser()
        self.timer = QTimer()
        self.timer.timeout.connect(self.read_can_messages)

#    def update_vel_label(self, value):
#        self.vel_label.setText(f'Cmd Vel: {value}')
#
#    def update_steering_label(self, value):
#        self.steering_label.setText(f'Steering Angle: {value}')
#
#    def toggle_brake(self):
#        QMessageBox.information(self, "Brake", "Brake signal toggled")
#
#    def close_app(self):
#        self.close()

    def show_custom_message(self, title, message, width=300, height=100):
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
            self.show_custom_message("Warning", "CAN is already connected.")
            return
        try:
            #subprocess.run(["sudo", "ip", "link", "set", self.interface_name, "up", "type", "can", "bitrate", "500000"], check=True)
            self.bus = can.Bus(channel=self.interface_name, interface='socketcan')
            self.timer.start(50)
            self.show_custom_message("Info", "CAN connected successfully.")
        except Exception as e:
            self.show_custom_message("Error", f"Failed to open CAN interface:\n{e}")
            self.bus = None

    def disconnect_can_interface(self):
        if self.bus is not None:
            self.timer.stop()
            self.bus.shutdown()
            self.bus = None
            self.show_custom_message("Info", "CAN disconnected.")
        else:
            self.show_custom_message("Warning", "CAN is not connected.")

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

    def send_can_frame(self):
        if self.bus is None:
            self.show_custom_message("Error", "CAN is not connected.")
            return
        try:
            can_id = int(self.input_id.text(), 16)
            data = []
            for field in self.input_data:
                val = field.text()
                if not val:
                    raise ValueError("Empty data field.")
                data.append(int(val, 16))
            if len(data) != 8:
                raise ValueError("DLC must be 8.")
            msg = can.Message(arbitration_id=can_id, data=data, is_extended_id=False)
            self.bus.send(msg)
        except Exception as e:
            self.show_custom_message("Error", f"Failed to send CAN message:\n{e}")

    def update_raw_table(self, message):
        can_id = message.arbitration_id
        can_id_hex = hex(can_id)

        if not hasattr(self, 'can_id_row_map'):
            self.can_id_row_map = {}
            self.received_can_ids = []
            self.min_can_id = None

        if can_id not in self.can_id_row_map:
            self.received_can_ids.append(can_id)
            if self.min_can_id is None or can_id < self.min_can_id:
                self.min_can_id = can_id
            insert_position = 0 if can_id == self.min_can_id else self.raw_table.rowCount()
            if can_id == self.min_can_id:
                for cid in self.can_id_row_map:
                    self.can_id_row_map[cid] += 1
            self.raw_table.insertRow(insert_position)
            self.raw_table.setItem(insert_position, 0, QTableWidgetItem(can_id_hex))
            self.raw_table.setItem(insert_position, 1, QTableWidgetItem(str(message.dlc)))
            self.raw_table.setItem(insert_position, 2, QTableWidgetItem(message.data.hex()))
            self.can_id_row_map[can_id] = insert_position
        else:
            row = self.can_id_row_map[can_id]
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
            self.show_custom_message("Info", "Restart the program to apply the new interface.")

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


    def update_vel_label(self):
        vel_value = float(self.vel_slider.value())
        self.vel_label.setText(f'Cmd Vel: {vel_value} km/hr')

    def update_steering_label(self):
        steering_value = float(self.steering_slider.value())
        self.steering_label.setText(f'Steering Angle: {steering_value} degrees')

    def toggle_brake(self):
        # Toggle the brake state and set the parameter value
        self.brake_active = not self.brake_active
        if self.brake_active == True:
            self.break_stop = subprocess.Popen(
                ['gnome-terminal', '--disable-factory', '-x', 'ros2', 'param', 'set', 'can_subscriber', 'break', '1'],
                preexec_fn=os.setpgrp
)
        else:
           self.break_stop = subprocess.Popen(
                ['gnome-terminal', '--disable-factory', '-x', 'ros2', 'param', 'set', 'can_subscriber', 'break', '0'],
                preexec_fn=os.setpgrp
)

        # Change the color of the UI based on the brake state
        color = "white" if self.brake_active else "red"
        self.brake_button.setStyleSheet(f"background-color: {color}; color: white;")


    def close_app(self):
        # Set brake parameter to 1 and close the application
   
        self.break_stop = subprocess.Popen(
            ['gnome-terminal', '--disable-factory', '-x', 'ros2', 'param', 'set', 'can_subscriber', 'break', '1'],
            preexec_fn=os.setpgrp)
        self.close()

    def send_continuous_velocities(self):
        # This method is called by the timer to continuously send velocities
        vel_value = float(self.vel_slider.value())
        steering_value = float(self.steering_slider.value())

        # Publish the speed and steering values
        twist_msg = Twist()
        twist_msg.linear.x = vel_value
        twist_msg.angular.z = steering_value
        self.cmd_vel_pub.publish(twist_msg)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
