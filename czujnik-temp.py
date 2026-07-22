import glob
import os
import time

# Ścieżka bazowa, gdzie Linux montuje urządzenia 1-Wire
BASE_DIR = "/sys/bus/w1/devices/"


def find_sensor_file():
    """Szuka folderu czujnika zaczynającego się od '28-'"""
    device_folders = glob.glob(BASE_DIR + "28-*")
    if not device_folders:
        return None
    # Zwraca ścieżkę do pliku w1_slave pierwszego znalezionego czujnika
    return os.path.join(device_folders[0], "w1_slave")


def read_temp_raw(sensor_file):
    """Odczytuje surowe linie tekstu z pliku czujnika"""
    with open(sensor_file, "r") as f:
        return f.readlines()


def read_temperature(sensor_file):
    """Przetwarza surowe dane i zwraca temperaturę w stopniach Celsjusza"""
    lines = read_temp_raw(sensor_file)

    retry_count = 0
    while lines[0].strip()[-3:] != "YES" and retry_count < 5:
        time.sleep(0.2)
        lines = read_temp_raw(sensor_file)
        retry_count += 1

    if lines[0].strip()[-3:] != "YES":
        return None 

    # Szukanie wartości 't=' w drugiej linii pliku
    equals_pos = lines[1].find("t=")
    if equals_pos != -1:
        temp_string = lines[1][equals_pos + 2 :]
        temp_c = float(temp_string) / 1000.0  # Wartość jest w milistopniach
        return temp_c

    return None


def main():
    sensor_file = find_sensor_file()

    if not sensor_file:
        print("NIE ZNALEZIONO CZUJNIKA!")
        return

    print(f"Wykryto czujnik pod adresem: {sensor_file.split('/')[4]}")
    print("Start pomiaru temperatury...\n")

    try:
        while True:
            temp = read_temperature(sensor_file)

            if temp is not None:
                print(f"Temperatura: {temp:.2f} °C")
            else:
                print("Błąd odczytu danych z czujnika...")

            time.sleep(2)  # Pomiar co 2 sekundy

    except KeyboardInterrupt:
        print("\nZakończono działanie skryptu.")


if __name__ == "__main__":
    main()