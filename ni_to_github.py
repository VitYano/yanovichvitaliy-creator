from datetime import datetime, timezone
import csv
import json
import os
import time
import traceback

import matplotlib.pyplot as plt
import nidaqmx


DEVICE_NAME = "cDAQ9181-1C9B71DMod1"
CHANNELS = ("ai0", "ai1", "ai2")

MIN_VOLTAGE = -10.0
MAX_VOLTAGE = 10.0

POLL_SECONDS = 0.02
COLLECT_SECONDS = 60

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.path.join(BASE_DIR, "docs")
DATA_DIR = os.path.join(DOCS_DIR, "data")
IMAGES_DIR = os.path.join(DOCS_DIR, "images")

CSV_FILE = os.path.join(DATA_DIR, "latest.csv")
JSON_FILE = os.path.join(DATA_DIR, "latest.json")
PNG_FILE = os.path.join(IMAGES_DIR, "latest.png")


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(IMAGES_DIR, exist_ok=True)


def normalize_values(values):
    if not isinstance(values, (list, tuple)):
        raise TypeError(f"Expected list/tuple from task.read(), got {type(values).__name__}")

    normalized = []

    for item in values:
        if isinstance(item, (list, tuple)):
            if len(item) == 0:
                raise ValueError("Empty value list returned from NI DAQ")
            normalized.append(float(item[0]))
        else:
            normalized.append(float(item))

    if len(normalized) != len(CHANNELS):
        raise ValueError(f"Expected {len(CHANNELS)} values, got {len(normalized)}")

    return normalized


def collect_one_minute():
    points = []
    started_at = utc_now_iso()
    t0 = time.time()

    print(f"Collecting data for {COLLECT_SECONDS} seconds...")

    with nidaqmx.Task() as task:
        for channel in CHANNELS:
            task.ai_channels.add_ai_voltage_chan(
                f"{DEVICE_NAME}/{channel}",
                min_val=MIN_VOLTAGE,
                max_val=MAX_VOLTAGE,
            )

        print("NI task opened successfully")

        while True:
            elapsed = time.time() - t0
            if elapsed >= COLLECT_SECONDS:
                break

            values = task.read(number_of_samples_per_channel=1, timeout=2.0)
            vals = normalize_values(values)

            point = {
                "time": utc_now_iso(),
                "elapsed_s": round(elapsed, 3),
                "ai0": vals[0],
                "ai1": vals[1],
                "ai2": vals[2],
            }
            points.append(point)

            time.sleep(POLL_SECONDS)

    ended_at = utc_now_iso()

    print(f"Collected {len(points)} points")

    return {
        "device": DEVICE_NAME,
        "channels": list(CHANNELS),
        "poll_seconds": POLL_SECONDS,
        "collect_seconds": COLLECT_SECONDS,
        "started_at": started_at,
        "ended_at": ended_at,
        "points_count": len(points),
        "points": points,
    }


def save_csv(payload):
    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["time", "elapsed_s", "ai0", "ai1", "ai2"])

        for p in payload["points"]:
            writer.writerow([
                p["time"],
                p["elapsed_s"],
                p["ai0"],
                p["ai1"],
                p["ai2"],
            ])

    print(f"Saved CSV: {CSV_FILE}")


def save_json(payload):
    latest = payload["points"][-1] if payload["points"] else None

    out = {
        "device": payload["device"],
        "channels": payload["channels"],
        "poll_seconds": payload["poll_seconds"],
        "collect_seconds": payload["collect_seconds"],
        "started_at": payload["started_at"],
        "ended_at": payload["ended_at"],
        "points_count": payload["points_count"],
        "latest": latest,
        "history": payload["points"],
    }

    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"Saved JSON: {JSON_FILE}")


def save_plot(payload):
    points = payload["points"]
    if not points:
        raise ValueError("No points collected, cannot build plot")

    x = [p["elapsed_s"] for p in points]
    y0 = [p["ai0"] for p in points]
    y1 = [p["ai1"] for p in points]
    y2 = [p["ai2"] for p in points]

    plt.figure(figsize=(14, 6))
    plt.plot(x, y0, label="AI0")
    plt.plot(x, y1, label="AI1")
    plt.plot(x, y2, label="AI2")

    plt.title("NI 9215 - Last 60 Seconds")
    plt.xlabel("Time (s)")
    plt.ylabel("Voltage (V)")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(PNG_FILE, dpi=140)
    plt.close()

    print(f"Saved plot: {PNG_FILE}")


def main():
    ensure_dirs()

    try:
        payload = collect_one_minute()
        save_csv(payload)
        save_json(payload)
        save_plot(payload)
        print("Done")
    except Exception:
        print("ERROR:")
        traceback.print_exc()


if __name__ == "__main__":
    main()
