import time
from typing import Optional
import spidev
from gpiozero import DigitalInputDevice, OutputDevice


class ShieldADDA:
    VREF: float = 5.0

    PIN_RESET = 18
    PIN_DRDY = 17
    PIN_CS_ADS = 22
    PIN_CS_DAC = 23

    def __init__(self, bus: int = 0, device: int = 0) -> None:
        self.bus = bus
        self.device = device
        self._spi: Optional[spidev.SpiDev] = None

        self._reset = OutputDevice(self.PIN_RESET, initial_value=True)
        self._cs_ads = OutputDevice(self.PIN_CS_ADS, initial_value=True)
        self._cs_dac = OutputDevice(self.PIN_CS_DAC, initial_value=True)
        self._drdy = DigitalInputDevice(self.PIN_DRDY)

    def connect_spi(self) -> None:
        self._spi = spidev.SpiDev()
        self._spi.open(self.bus, self.device)
        self._spi.max_speed_hz = 1000000
        self._spi.mode = 0B01

        self._reset.off()
        time.sleep(0.1)
        self._reset.on()
        time.sleep(0.1)
        print("Zainicjalizowano magistralę SPI i shield AD/DA.")

    def close_connection(self) -> None:
        if self._spi:
            self._spi.close()
            print("Zamknięto połączenie SPI.")

    def _wait_drdy(self) -> None:
        timeout = time.time() + 0.5
        while self._drdy.value == 1:
            if time.time() > timeout:
                break
            time.sleep(0.0001)

    def set_dac1_voltage(self, voltage: float) -> None:
        if not (0.0 <= voltage <= self.VREF):
            raise ValueError(f"Napięcie {voltage}V poza zakresem (0.0 - {self.VREF}V).")

        raw_val = int((voltage / self.VREF) * 65535)

        cmd = 0x24
        msb = (raw_val >> 8) & 0xFF
        lsb = raw_val & 0xFF

        self._cs_dac.off()
        if self._spi:
            self._spi.xfer2([cmd, msb, lsb])
        self._cs_dac.on()

    def read_ad7_voltage(self) -> float:
        mux_channel = (7 << 4) | 8

        self._cs_ads.off()
        if self._spi:
            self._spi.xfer2([0x51, 0x00, mux_channel])
            time.sleep(0.001)

            self._spi.xfer2([0xFC, 0x00])
            self._wait_drdy()

            self._spi.xfer2([0x01])
            time.sleep(0.0002)

            raw_bytes = self._spi.readbytes(3)
            raw_val = (raw_bytes[0] << 16) | (raw_bytes[1] << 8) | raw_bytes[2]

            self._cs_ads.on()

            if raw_val & 0x800000:
                raw_val -= 0x1000000

            voltage = (raw_val / 8388607.0) * self.VREF
            return max(0.0, min(voltage, self.VREF))

        self._cs_ads.on()
        return 0.0


class MFCController:

    def __init__(self, max_voltage: float = 5.0) -> None:
        self.max_voltage = max_voltage
        self.board = ShieldADDA()

    def __enter__(self) -> "MFCController":
        self.board.connect_spi()
        self.set_flow(0.0)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        print("Zamykanie MFC: wyzerowanie przepływu gazu...")
        self.set_flow(0.0)
        self.board.close_connection()

    def set_flow(self, percent: float) -> None:
        if not (0.0 <= percent <= 100.0):
            raise ValueError(f"Przepływ {percent}% poza zakresem (0 - 100%).")

        target_voltage = (percent / 100.0) * self.max_voltage
        self.board.set_dac1_voltage(target_voltage)
        print(f"Ustawiono przepływ zadany: {percent:.1f}% ({target_voltage:.2f} V na DAC1)")

    def get_actual_flow(self) -> float:
        voltage = self.board.read_ad7_voltage()
        measured_percent = (voltage / self.max_voltage) * 100.0
        return min(100.0, measured_percent)


if __name__ == "__main__":
    try:
        with MFCController() as mfc:
            print("\n--- TEST KONTROLERA PRZEPŁYWU MFC ---")

            mfc.set_flow(25.0)
            time.sleep(2.0)
            print(f"Odczytany rzeczywisty przepływ: {mfc.get_actual_flow():.1f}%")

            mfc.set_flow(50.0)
            time.sleep(2.0)
            print(f"Odczytany rzeczywisty przepływ: {mfc.get_actual_flow():.1f}%")

    except Exception as err:
        print(f"Błąd podczas pracy z kontrolerem MFC: {err}")