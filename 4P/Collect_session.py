from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import time
from pathlib import Path

import pandas as pd
import serial


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SESSION_DIR = DATA_DIR / "session_backups"
RAW_FILE = DATA_DIR / "raw_data.csv"
PRIVATE_LOG = DATA_DIR / "collection_log_private.csv"

BAUD_RATE = 115200
WARMUP_SECONDS = 5 * 60
SESSION_SECONDS = 45 * 60
SILENCE_TIMEOUT_SECONDS = 45

SENSOR_COLUMNS = [
    "elapsed_seconds",
    "indoor_temp_c",
    "indoor_rh",
    "outdoor_temp_c",
    "outdoor_rh",
    "pc_exhaust_temp_c",
    "co2_ppm",
]

RATING_COLUMNS = [
    "comfort_start", "comfort_end", "focus_start", "focus_end",
    "typing_accuracy_start", "typing_accuracy_end",
]
RAW_COLUMNS = [
    "session_id", "elapsed_seconds", "workload", "window_state",
    *SENSOR_COLUMNS[1:], *RATING_COLUMNS, "session_notes",
]


def ask_choice(prompt: str, choices: set[str]) -> str:
    while True:
        value = input(prompt).strip().lower()
        if value in choices:
            return value
        print(f"Enter one of: {', '.join(sorted(choices))}")


def ask_optional_number(prompt: str, minimum: float, maximum: float):
    while True:
        value = input(prompt).strip()
        if value == "":
            return None
        try:
            number = float(value)
        except ValueError:
            print("Enter a number or leave it blank.")
            continue
        if math.isfinite(number) and minimum <= number <= maximum:
            return number
        print(f"Enter a value from {minimum} to {maximum}, or leave it blank.")


def wait_for_header(ser: serial.Serial) -> None:
    deadline = time.monotonic() + 30
    expected = ",".join(SENSOR_COLUMNS)
    while time.monotonic() < deadline:
        line = ser.readline().decode("utf-8", errors="ignore").strip()
        if line:
            print(line)
        if line == expected:
            return
    raise RuntimeError(
        "No recording header received. Upload arduino_capture.ino (not a sensor "
        "test), close Serial Monitor, unplug/reconnect the Arduino, then retry."
    )


def append_private_log(record: dict, path: Path = PRIVATE_LOG) -> None:
    log_df = pd.DataFrame([record])
    if path.exists():
        log_df.to_csv(path, mode="a", header=False, index=False)
    else:
        log_df.to_csv(path, index=False)


def save_metadata(path: Path, metadata: dict) -> None:
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    temporary.replace(path)


def save_frame(path: Path, frame: pd.DataFrame) -> None:
    temporary = path.with_suffix(".csv.tmp")
    frame.to_csv(temporary, index=False)
    temporary.replace(path)


def finite_reading(value: str, co2: bool = False) -> bool:
    try:
        number = float(value)
        return math.isfinite(number) and (not co2 or number > 0)
    except (ValueError, TypeError):
        return False


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--practice", action="store_true",
                        help="Record one minute after a 30-second warm-up; keep separate from study data.")
    args = parser.parse_args(argv)
    data_dir = DATA_DIR / "practice" if args.practice else DATA_DIR
    session_dir = data_dir / "session_backups"
    metadata_dir = data_dir / "session_metadata_private"
    raw_file = data_dir / "raw_data.csv"
    private_log = data_dir / "collection_log_private.csv"
    session_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)
    duration = 60 if args.practice else SESSION_SECONDS
    warmup = 30 if args.practice else WARMUP_SECONDS
    mode = "PRACTICE (not assessment measurements)" if args.practice else "STUDY"
    print(f"{mode}: {duration / 60:g} minutes of recording; {warmup:g} seconds of warm-up.")

    port = input("Arduino COM port, for example COM5: ").strip()
    example_id = "P01" if args.practice else "S01"
    session_id = input(f"New session ID, for example {example_id}: ").strip().upper()
    if not re.fullmatch(r"[A-Z0-9_-]+", session_id):
        raise ValueError("Session ID may contain only letters, numbers, _ and -.")

    workload = ask_choice("PC workload (idle/high): ", {"idle", "high"})
    window_state = ask_choice("Window state (closed/open): ", {"closed", "open"})

    backup_file = session_dir / f"{session_id}_raw.csv"
    metadata_file = metadata_dir / f"{session_id}.json"
    if backup_file.exists() or metadata_file.exists():
        raise ValueError(f"{session_id} already has saved files. Use a new ID; no files were overwritten.")
    if raw_file.exists():
        existing = pd.read_csv(raw_file, usecols=["session_id"])
        if session_id in existing["session_id"].astype(str).values:
            raise ValueError(f"{session_id} already exists. Use a new session ID.")

    print("\nBefore continuing:")
    print("- Put all sensors in their fixed positions.")
    print(f"- Set the window to: {window_state}.")
    print("- Keep the PC idle during sensor warm-up.")
    print("- Unplug/reconnect the Arduino before every new session; close Serial Monitor.")
    input("Press Enter when the physical setup is ready...")

    metadata = {
        "session_id": session_id, "workload": workload, "window_state": window_state,
        "practice": args.practice, "planned_seconds": duration, "status": "preparing",
        "start_elapsed_seconds": None, "end_elapsed_seconds": None,
        "rows": 0, "last_elapsed_seconds": None,
    }
    ratings = {column: None for column in RATING_COLUMNS}
    rows = []
    completed = False
    notes = ""
    failure = ""
    seen = {column: False for column in SENSOR_COLUMNS[1:]}
    save_metadata(metadata_file, metadata)
    try:
        print(f"Opening {port}. Close Arduino Serial Monitor first.")
        with serial.Serial(port, BAUD_RATE, timeout=2) as ser:
            time.sleep(2)
            for remaining in range(warmup, 0, -30):
                print(f"Warm-up remaining: {remaining} seconds", flush=True)
                time.sleep(min(30, remaining))

            print("Optional START ratings: Enter leaves an unmeasured value blank.")
            print("Comfort: 1=very uncomfortable, 7=very comfortable. Focus: 1=very unfocused, 7=very focused.")
            ratings["comfort_start"] = ask_optional_number("Comfort NOW (1-7): ", 1, 7)
            ratings["focus_start"] = ask_optional_number("Focus NOW (1-7): ", 1, 7)
            ratings["typing_accuracy_start"] = ask_optional_number("Starting typing accuracy, if measured (0-100%): ", 0, 100)

            message = "Start the standardised high workload" if workload == "high" else "Leave the PC idle"
            input(f"{message}, then press Enter to begin recording...")
            ser.reset_input_buffer()
            metadata["start_elapsed_seconds"] = 0
            metadata["status"] = "recording"
            metadata.update(ratings)
            save_metadata(metadata_file, metadata)
            ser.write(b"START\n")
            wait_for_header(ser)

            print(f"Recording {duration / 60:g} minutes. Each row is saved immediately.", flush=True)
            print(f"Session CSV: {backup_file}")
            with backup_file.open("x", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=RAW_COLUMNS)
                writer.writeheader()
                stream.flush()
                last_received = time.monotonic()
                recording_deadline = last_received + duration + 90
                previous_elapsed = -1.0
                while True:
                    if time.monotonic() - last_received > SILENCE_TIMEOUT_SECONDS:
                        raise RuntimeError("No valid data row for 45 seconds. Check USB and the Arduino.")
                    if time.monotonic() > recording_deadline:
                        raise RuntimeError("Recording exceeded its expected duration. Check the Arduino output.")
                    line = ser.readline().decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    values = next(csv.reader([line]))
                    if len(values) != len(SENSOR_COLUMNS):
                        print(f"Skipped message: {line}", flush=True)
                        continue
                    record = dict(zip(SENSOR_COLUMNS, values))
                    if not finite_reading(record["elapsed_seconds"]):
                        continue
                    elapsed = float(record["elapsed_seconds"])
                    if elapsed < 0 or (not rows and elapsed > 15):
                        raise RuntimeError("Unexpected starting timer. Unplug/reconnect the board before a new session.")
                    if elapsed < previous_elapsed:
                        raise RuntimeError("Arduino timer restarted during recording. Session marked incomplete.")
                    previous_elapsed = elapsed
                    last_received = time.monotonic()
                    record.update(session_id=session_id, workload=workload,
                                  window_state=window_state, session_notes="", **ratings)
                    writer.writerow(record)
                    stream.flush()
                    os.fsync(stream.fileno())
                    rows.append(record)
                    for column in seen:
                        valid = finite_reading(record[column], co2=(column == "co2_ppm"))
                        if column == "pc_exhaust_temp_c" and valid:
                            valid = float(record[column]) != -127.0
                        seen[column] |= valid
                    print(f"{elapsed / 60:5.1f} min | {line}", flush=True)
                    # Stop early if a required sensor never produces data.
                    if len(rows) >= 3 and not all(seen.values()):
                        absent = ", ".join(column for column, valid in seen.items() if not valid)
                        raise RuntimeError(f"Required measurements missing: {absent}. Fix the sensor before a full run.")
                    if elapsed >= duration:
                        completed = True
                        break

        if completed:
            print("Recording finished. Enter END ratings now; leave unmeasured values blank.")
            ratings["comfort_end"] = ask_optional_number("Comfort NOW (1-7): ", 1, 7)
            ratings["focus_end"] = ask_optional_number("Focus NOW (1-7): ", 1, 7)
            ratings["typing_accuracy_end"] = ask_optional_number("Ending typing accuracy, if measured (0-100%): ", 0, 100)
            notes = input("Interruptions or deviations, or Enter for none: ").strip()
    except KeyboardInterrupt:
        failure = "Interrupted by user."
        print("\nStopped. Already received readings remain saved.")
    except (serial.SerialException, RuntimeError, OSError) as error:
        failure = str(error)
        print(f"\nRecording issue: {failure}")
    finally:
        metadata["end_elapsed_seconds"] = float(rows[-1]["elapsed_seconds"]) if rows else None
        metadata.update(ratings)
        metadata.update(status="completed" if completed else "incomplete", rows=len(rows),
                        last_elapsed_seconds=previous_elapsed if rows else None, error=failure)
        notes = "; ".join(text for text in [notes, failure] if text)
        metadata["notes"] = notes
        save_metadata(metadata_file, metadata)
        append_private_log({
            "session_id": session_id, "workload": workload, "window_state": window_state,
            "start_elapsed_seconds": metadata["start_elapsed_seconds"],
            "end_elapsed_seconds": metadata["end_elapsed_seconds"],
            "duration_minutes": round(float(rows[-1]["elapsed_seconds"]) / 60, 2) if rows else 0,
            "notes": notes if completed else f"INCOMPLETE: {notes}",
        }, private_log)

    if rows:
        session_df = pd.DataFrame(rows, columns=RAW_COLUMNS)
        for column, value in ratings.items():
            session_df[column] = value
        session_df["session_notes"] = notes
        save_frame(backup_file, session_df)
        print(f"Saved {len(rows)} readings: {backup_file}")
        if completed:
            if raw_file.exists():
                old = pd.read_csv(raw_file, dtype={"session_id": str})
                if session_id in old["session_id"].values:
                    raise ValueError("Session ID was added by another process. Backup kept; combined CSV unchanged.")
                session_df = pd.concat([old, session_df], ignore_index=True)
            save_frame(raw_file, session_df)
            print(f"Updated {'practice' if args.practice else 'study'} raw data: {raw_file}")
        else:
            print("Incomplete session kept in its backup; not added to the study's combined data.")
    print(f"Status: {metadata['status']}. Private metadata: {metadata_file}")


if __name__ == "__main__":
    main()
