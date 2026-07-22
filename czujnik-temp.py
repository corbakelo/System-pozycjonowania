import time
from pathlib import Path

BASE_DIRECTORY = Path("/sys/bus/w1/devices/")


def find_thermometer_file_path() -> Path | None:
    device_directories = list(BASE_DIRECTORY.glob("28-*"))
    if not device_directories:
        return None

    return device_directories[0] / "w1_slave"


def read_raw_temperature_lines(thermometer_file_path: Path) -> list[str] | None:
    try:
        return thermometer_file_path.read_text().splitlines()
    except (FileNotFoundError, OSError):
        return None


def convert_raw_temperature_to_celsius(thermometer_file_path: Path) -> float | None:
    lines = read_raw_temperature_lines(thermometer_file_path)
    if not lines or len(lines) < 2:
        return None

    if lines[0].startswith("00 00 00 00 00 00 00 00 00"):
        return None
    
    retry_count = 0
    while lines[0].strip()[-3:] != "YES" and retry_count < 5:
        time.sleep(0.2)
        lines = read_raw_temperature_lines(thermometer_file_path)
        if not lines:
            return None
        retry_count += 1

    if lines[0].strip()[-3:] != "YES":
        return None

    equals_position = lines[1].find("t=")
    if equals_position == -1:
        return None

    temperature_string = lines[1][equals_position + 2 :]
    temperature_in_celsius = float(temperature_string) / 1000.0

    return temperature_in_celsius


def print_temperature_measurement(thermometer_file_path: Path) -> None:
    temperature_in_celsius = convert_raw_temperature_to_celsius(
        thermometer_file_path
    )

    if temperature_in_celsius is None:
        print("Błąd odczytu danych! Czujnik odłączony lub uszkodzony.")
        return

    print(f"Temperatura: {temperature_in_celsius:.2f} °C")


def main() -> None:
    thermometer_file_path = find_thermometer_file_path()

    if not thermometer_file_path:
        print("Nie wykryto czujnika na magistrali 1-Wire!")
        return

    thermometer_id = thermometer_file_path.parent.name
    print(f"Wykryto czujnik pod adresem ID: {thermometer_id}")
    print("Rozpoczęto ciągły pomiar temperatury...\n")

    try:
        while True:
            print_temperature_measurement(thermometer_file_path)
            time.sleep(2)

    except KeyboardInterrupt:
        print("\nPrzerwano działanie programu przez użytkownika.")


if __name__ == "__main__":
    main()