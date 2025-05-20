import sys
import time
import can
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout, QMessageBox
)

class MotorControlGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CAN 전진 제어 GUI")
        self.setGeometry(300, 300, 400, 180)

        self.bus = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        # 속도 입력
        speed_layout = QHBoxLayout()
        self.speed_input = QLineEdit("5.0")
        speed_layout.addWidget(QLabel("속도 (km/h):"))
        speed_layout.addWidget(self.speed_input)
        layout.addLayout(speed_layout)

        # 버튼
        self.btn_connect = QPushButton("CAN 연결")
        self.btn_forward = QPushButton("전진")
        layout.addWidget(self.btn_connect)
        layout.addWidget(self.btn_forward)

        self.setLayout(layout)

        self.btn_connect.clicked.connect(self.connect_can)
        self.btn_forward.clicked.connect(self.send_forward)

    def connect_can(self):
        try:
            self.bus = can.interface.Bus(channel='can0', interface='socketcan')
            #self.bus = can.Bus(channel=self.interface_name, interface='socketcan')
            

            QMessageBox.information(self, "성공", "CAN 연결 완료")
        except Exception as e:
            QMessageBox.critical(self, "에러", f"CAN 연결 실패: {e}")

    def send_forward(self):
        if not self.bus:
            QMessageBox.warning(self, "오류", "먼저 CAN을 연결하세요")
            return


        ctrl_msg = can.Message(arbitration_id=0x10a, data=[0x02, 0x01, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00], is_extended_id=False)
        self.bus.send(ctrl_msg)
        time.sleep(0.02)

        ctrl_msg = can.Message(arbitration_id=0x10a, data=[0x02, 0x01, 0x02, 0x00, 0x01, 0x00, 0x00, 0x00], is_extended_id=False)
        self.bus.send(ctrl_msg)
        time.sleep(0.02)

        try:
            #while True:
            speed = float(self.speed_input.text())
            speed_val = int(speed / 0.1)
            linear_v1 = speed_val & 0xFF
            linear_v2 = (speed_val >> 8) & 0xFF

            angular_velocity = int((10 + 30) / 0.1)  # 정면 유지
            angular_v1 = angular_velocity & 0xFF
            angular_v2 = (angular_velocity >> 8) & 0xFF

            # 메시지 구성
            enable_msg = can.Message(arbitration_id=0x501, data=[0xF1, 0, 0, 0, 0, 0, 0, 0], is_extended_id=False)
            steering_msg = can.Message(arbitration_id=0x502, data=[0xF1, 0, 0, 0, angular_v1, angular_v2, 0, 0], is_extended_id=False)
            speed_msg = can.Message(arbitration_id=0x504,
                                    data=[0xF1, 0x00, 0x01, 0x01, 0x00, 0x00, linear_v1, linear_v2],
                                    is_extended_id=False)
            brake_release_msg = can.Message(arbitration_id=0x503, data=[0xF1, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00], is_extended_id=False)
            
            indicator_msg = can.Message(arbitration_id=0x506, data=[0x00, 0, 0, 0, 0, 0, 0, 0], is_extended_id=False)

            #wheel_msg = can.Message(arbitration_id=0x10b, data=[0x80, 0, 0, 0, 0, 0, 0, 0], is_extended_id=False)
            # 전송 순서
            self.bus.send(enable_msg)
            time.sleep(0.05)
            self.bus.send(brake_release_msg)
            time.sleep(0.05)
            self.bus.send(steering_msg)
            self.bus.send(indicator_msg)
            time.sleep(0.05)
            self.bus.send(speed_msg)
            time.sleep(5)
            #self.bus.send(wheel_msg)

            #QMessageBox.information(self, "전송", f"{speed:.1f} km/h 속도로 전진 명령 전송 완료")
        except Exception as e:
            QMessageBox.critical(self, "에러", f"명령 전송 실패: {e}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    gui = MotorControlGUI()
    gui.show()
    sys.exit(app.exec())
