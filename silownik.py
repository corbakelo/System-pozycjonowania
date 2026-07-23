import time
from pathlib import Path
from typing import Optional
import serial


class JrkController:

    DEFAULT_PORT = Path("/dev/ttyACM0")
    MIN_POSITION: int = 0
    MAX_POSITION: int = 4095

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
            print(f"Połączono ze sterownikiem Jrk na porcie {self.port_path}")
        except serial.SerialException as err:
            print(f"Błąd otwarcia portu szeregowego: {err}")
            raise

    def disconnect(self) -> None:
        if self._serial and self._serial.is_open:
            self._serial.close()
            print("Zamknięto połączenie ze sterownikiem.")

    def __enter__(self) -> "JrkController":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.disconnect()

    def set_target(self, position: int) -> None:
        if not (self.MIN_POSITION <= position <= self.MAX_POSITION): #0-4095
            raise ValueError(f"Pozycja {position} poza zakresem ({self.MIN_POSITION}-{self.MAX_POSITION}).")
        if not self._serial or not self._serial.is_open:
            raise RuntimeError("Port szeregowy nie jest otwarty.")

        # Przygotowanie 2 bajtów komendy Pololu Jrk "Set Target"
        low_byte = (position & 0x1F) | 0xC0
        high_byte = (position >> 5) & 0x7F

        cmd = bytearray([low_byte, high_byte])
        self._serial.write(cmd)
        self._serial.flush()

    def get_position(self) -> int:
        if not self._serial or not self._serial.is_open:
            raise RuntimeError("Port szeregowy nie jest otwarty.")

        # Komenda 0xA7 = Get position
        self._serial.write(bytearray([0xA7]))
        self._serial.flush()

        response = self._serial.read(2)
        if len(response) < 2:
            raise TimeoutError("Brak odpowiedzi ze sterownika Jrk (timeout).")

        # Złożenie w wartość 12-bitową
        low_byte, high_byte = response[0], response[1]
        position_val = low_byte | (high_byte << 8)
        return position_val

    def stop_motor(self) -> None:
        if not self._serial or not self._serial.is_open:
            raise RuntimeError("Port szeregowy nie jest otwarty.")

        # Komenda 0xFF = Motor Off
        self._serial.write(bytearray([0xFF]))
        self._serial.flush()
        print("[!] Silnik zatrzymany.")


if __name__ == "__main__":
    device_port = Path("/dev/ttyACM0")

    try:
        with JrkController(port_path=device_port) as jrk:
            current_pos = jrk.get_position()
            print(f"[i] Pozycja startowa siłownika: {current_pos}")

            target = 0
            print(f"[>] Rozpoczynam ruch do pozycji {target}...")
            jrk.set_target(target)

            # Pętla monitorująca ruch na żywo
            for _ in range(10):
                time.sleep(0.5)
                pos = jrk.get_position()
                print(f"    Aktualna pozycja tłoka: {pos}")
                if abs(pos - target) < 20:  # Margines tolerancji
                    print("[+] Osiągnięto cel!")
                    break

            target = 3800
            print(f"[>] Rozpoczynam ruch powrotny do pozycji {target}...")
            jrk.set_target(target)

            time.sleep(3.0)
            final_pos = jrk.get_position()
            print(f"[i] Pozycja końcowa: {final_pos}")

    except Exception as err:
        print(f"[-] Błąd podczas pracy z Jrk: {err}")