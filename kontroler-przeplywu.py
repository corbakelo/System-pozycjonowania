import time
from typing import Optional
import spidev
from gpiozero import DigitalInputDevice, OutputDevice


class WaveshareADDA:
    """
    Niskopoziomowa obsługa nakładki Waveshare High-Precision AD/DA Board.
    - DAC8552 (16-bit DAC) na wyjściu DAC1
    - ADS1256 (24-bit ADC) na wejściu AD7
    """

    VREF: float = 5.0

    PIN_RST = 18
    PIN_DRDY = 17
    PIN_CS_ADC = 22
    PIN_CS_DAC = 23

    def __init__(self, bus: int = 0, device: int = 0) -> None:
        self.bus = bus
        self.device = device
        self._spi: Optional[spidev.SpiDev] = None

        self._rst = OutputDevice(self.PIN_RST, initial_value=True)
        self._cs_adc = OutputDevice(self.PIN_CS_ADC, initial_value=True)
        self._cs_dac = OutputDevice(self.PIN_CS_DAC, initial_value=True)
        self._drdy = DigitalInputDevice(self.PIN_DRDY)

    def connect(self) -> None:
        """Otwiera magistralę SPI i resetuje układy."""
        self._spi = spidev.SpiDev()
        self._spi.open(self.bus, self.device)
        self._spi.max_speed_hz = 1000000  # 1 MHz dla stabilności
        self._spi.mode = 0B01             # Mode 1 dla ADS1256/DAC8552

        # Hard-reset nakładki
        self._rst.off()
        time.sleep(0.1)
        self._rst.on()
        time.sleep(0.1)
        print("[+] Zainicjalizowano magistralę SPI i shield AD/DA.")

    def close(self) -> None:
        """Zamyka połączenie SPI."""
        if self._spi:
            self._spi.close()
            print("[+] Zamknięto połączenie SPI.")

    def set_dac1_voltage(self, voltage: float) -> None:
        """
        Ustawia napięcie wyjściowe na kanale DAC1 (0.0 V - VREF).
        """
        if not (0.0 <= voltage <= self.VREF):
            raise ValueError(f"Napięcie {voltage}V poza zakresem (0.0 - {self.VREF}V).")

        # Przeliczenie napięcia na wartość 16-bitową (0 - 65535)
        raw_val = int((voltage / self.VREF) * 65535)

        # DAC8552: Kanal B (DAC1) command byte = 0x24 (Load DAC B)
        cmd = 0x24
        msb = (raw_val >> 8) & 0xFF
        lsb = raw_val & 0xFF

        self._cs_dac.off()
        if self._spi:
            self._spi.xfer2([cmd, msb, lsb])
        self._cs_dac.on()

    def read_ad7_voltage(self) -> float:
        """
        Odczytuje napięcie analogowe z wejścia AD7 (0.0 V - VREF).
        """
        # Ustawienie MUX w ADS1256 na kanał AD7 (AIN7 vs AINCOM)
        mux_channel = (7 << 4) | 8

        self._cs_adc.off()
        if self._spi:
            # Zapisz MUX register (0x50 | 0x01), podaj kanał 0x78
            self._spi.xfer2([0x50 | 0x01, 0x00, mux_channel])
            # Odbierz komendę synchronizacji i odczytu danych (RDATA = 0x01)
            time.sleep(0.001)
            self._spi.xfer2([0x01])
            time.sleep(0.001)

            # Odczyt 3 bajtów danych z ADS1256 (24 bity)
            raw_bytes = self._spi.readbytes(3)
            raw_val = (raw_bytes[0] << 16) | (raw_bytes[1] << 8) | raw_bytes[2]
            
            # Przeliczenie wartości 24-bitowej na napięcie
            voltage = (raw_val / 8388607.0) * self.VREF
            self._cs_adc.on()
            return max(0.0, min(voltage, self.VREF))

        self._cs_adc.on()
        return 0.0


class MFCController:
    """
    Wysokopoziomowy kontroler przepływu gazu (M+W Instruments / Bronkhorst).
    Operuje na zakresie procentowym 0 - 100%.
    """

    def __init__(self, max_voltage: float = 5.0) -> None:
        self.max_voltage = max_voltage
        self.board = WaveshareADDA()

    def __enter__(self) -> "MFCController":
        self.board.connect()
        # Bezpieczeństwo: wyzerowanie przepływu na starcie
        self.set_flow(0.0)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        # Bezpieczeństwo: wyzerowanie przepływu przed wyłączeniem
        print("[!] Zamykanie MFC: wyzerowanie przepływu gazu...")
        self.set_flow(0.0)
        self.board.close()

    def set_flow(self, percent: float) -> None:
        """
        Ustawia żądany przepływ gazu w procentach (0.0% - 100.0%).
        """
        if not (0.0 <= percent <= 100.0):
            raise ValueError(f"Przepływ {percent}% poza zakresem (0 - 100%).")

        target_voltage = (percent / 100.0) * self.max_voltage
        self.board.set_dac1_voltage(target_voltage)
        print(f"[>] Ustawiono przepływ zadany: {percent:.1f}% ({target_voltage:.2f} V na DAC1)")

    def get_actual_flow(self) -> float:
        """
        Odczytuje rzeczywisty pomiar przepływu gazu z czujnika (0.0% - 100.0%).
        """
        voltage = self.board.read_ad7_voltage()
        measured_percent = (voltage / self.max_voltage) * 100.0
        return min(100.0, measured_percent)


if __name__ == "__main__":
    try:
        with MFCController() as mfc:
            print("\n--- TEST KONTROLERA PRZEPŁYWU MFC ---")

            # 1. Otwarcie zaworu na 25%
            mfc.set_flow(25.0)
            time.sleep(2.0)

            # Odczyt rzeczywiście zmierzonego przepływu z pinu AD7
            actual_flow = mfc.get_actual_flow()
            print(f"[i] Odczytany rzeczywisty przepływ: {actual_flow:.1f}%")

            # 2. Otwarcie zaworu na 50%
            mfc.set_flow(50.0)
            time.sleep(2.0)

            actual_flow = mfc.get_actual_flow()
            print(f"[i] Odczytany rzeczywisty przepływ: {actual_flow:.1f}%")

            # 3. Wyzerowanie przepływu
            mfc.set_flow(0.0)
            time.sleep(1.0)

    except Exception as err:
        print(f"[-] Błąd podczas pracy z kontrolerem MFC: {err}")