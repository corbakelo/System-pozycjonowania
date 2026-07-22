import time
from pathlib import Path
from typing import Optional
import serial


class MaestroController:

    DEFAULT_PORT = Path("/dev/ttyACM0")
    NEUTRAL_POSITION_US: int = 1500 
    SAFE_SPEED: int = 10             # (1-140)
    SAFE_ACCELERATION: int = 5        # (1-255)

    def __init__(self, port_path: Path = DEFAULT_PORT, baudrate: int = 9600, timeout: float = 1.0) -> None:
        self.port_path: Path = port_path
        self.baudrate: int = baudrate
        self.timeout: float = timeout
        self._serial: Optional[serial.Serial] = None

    def connect(self) -> None:
        if not self.port_path.exists():
            raise FileNotFoundError(f"Port szeregowy {self.port_path} nie istnieje.")

        try:
            self._serial = serial.Serial(
                port=str(self.port_path),
                baudrate=self.baudrate,
                timeout=self.timeout
            )
            print(f"Połączono ze sterownikiem na porcie {self.port_path}")
        except serial.SerialException as err:
            print(f"Błąd otwarcia portu szeregowego: {err}")
            raise

    def disconnect(self) -> None:
        if self._serial and self._serial.is_open:
            self._serial.close()
            print("Zamknięto połączenie szeregowe.")

    def __enter__(self) -> "MaestroController":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.disconnect()

    def set_target(self, channel: int, target_us: int) -> None:
        if not (0 <= channel <= 5):
            raise ValueError(f"Niepoprawny kanał: {channel}. Dozwolony zakres: 0-5.")
        if not self._serial or not self._serial.is_open:
            raise RuntimeError("Port szeregowy nie jest otwarty.")

        target_quarter_us = int(target_us * 4)
        cmd = bytearray([
            0x84,
            channel,
            target_quarter_us & 0x7F,
            (target_quarter_us >> 7) & 0x7F
        ])
        self._serial.write(cmd)

    def set_speed(self, channel: int, speed: int) -> None:
        if not (0 <= channel <= 5):
            raise ValueError(f"Niepoprawny kanał: {channel}.")
        if not self._serial or not self._serial.is_open:
            raise RuntimeError("Port szeregowy nie jest otwarty.")

        cmd = bytearray([
            0x87,
            channel,
            speed & 0x7F,
            (speed >> 7) & 0x7F
        ])
        self._serial.write(cmd)

    def set_acceleration(self, channel: int, accel: int) -> None:
        if not (0 <= channel <= 5):
            raise ValueError(f"Niepoprawny kanał: {channel}.")
        if not self._serial or not self._serial.is_open:
            raise RuntimeError("Port szeregowy nie jest otwarty.")

        cmd = bytearray([
            0x89,
            channel,
            accel & 0x7F,
            (accel >> 7) & 0x7F
        ])
        self._serial.write(cmd)

    def home_channel(self, channel: int, target_us: int = NEUTRAL_POSITION_US) -> None:
        print(f"Bazowanie kanału {channel} do {target_us} µs...")
        self.set_speed(channel, self.SAFE_SPEED)
        self.set_acceleration(channel, self.SAFE_ACCELERATION)
        self.set_target(channel, target_us)
        time.sleep(1.5)
        print(f"Kanał {channel} w pozycji bazowej.")


if __name__ == "__main__":
    device_port = Path("/dev/ttyACM0")

    try:
        with MaestroController(port_path=device_port) as controller:
            controller.home_channel(channel=0, target_us=1500)

            print("Ruch na 1200 µs...")
            controller.set_target(channel=0, target_us=1200)
            time.sleep(2.0)

            # print("Ruch na 1800 µs...")
            # controller.set_target(channel=0, target_us=1800)
            # time.sleep(2.0)

            controller.home_channel(channel=0, target_us=1500)

    except Exception as err:
        print(f"[-] Błąd wykonaniaaaa skryptu: {err}")