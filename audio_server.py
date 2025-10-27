#!/usr/bin/env python3
import os
import time
import json
import struct
import math
import threading
import requests
import subprocess
from collections import deque
from flask import Flask, jsonify
from dotenv import load_dotenv

# --- Load environment variables ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_IDS = [int(x) for x in os.getenv("CHAT_IDS", "").split(",") if x]

# --- Configuration ---
THRESHOLD = 0.02
COOLDOWN_SEC = 300
WINDOW_SEC = 2
STEP_SEC = 1
SAMPLE_RATE = 44100
CHANNELS = 2
DEVICE = "plughw:1,0"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "rms_state.json")

# --- Globals ---
buffer = deque(maxlen=WINDOW_SEC * SAMPLE_RATE * CHANNELS)
last_notification_time = 0
lock = threading.Lock()
_monitor_thread = None
_stop_event = threading.Event()

# --- Flask app ---
app = Flask(__name__)

# --- Audio / RMS functions ---
def write_state(rms_value, timestamp):
    """Atomically write RMS state to JSON file"""
    data = {"rms": round(rms_value, 5), "timestamp": timestamp}
    tmp_file = STATE_FILE + ".tmp"
    with open(tmp_file, "w") as f:
        json.dump(data, f)
    os.replace(tmp_file, STATE_FILE)

def read_state():
    if not os.path.exists(STATE_FILE):
        return {"rms": 0.0, "timestamp": "Never"}
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"rms": 0.0, "timestamp": "Invalid"}

def send_notification(rms_value):
    global last_notification_time
    text = (
        f"Otto's crib noise ({rms_value * 1000:.1f} normalized units) exceeded "
        f"{THRESHOLD * 1000:.1f} @ {time.strftime('%H:%M:%S')}"
    )
    for chat_id in CHAT_IDS:
        try:
            requests.get(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                params={"chat_id": chat_id, "text": text},
                timeout=5,
            )
        except requests.RequestException as e:
            print("Telegram send failed:", e)
    with lock:
        last_notification_time = time.time()
    print("Notification sent:", text)

def monitor_loop():
    """Background monitor: reads audio, calculates RMS, writes state, sends notifications"""
    print("Audio monitor thread started.")
    while not _stop_event.is_set():
        # --- Capture audio chunk ---
        cmd = [
            "arecord",
            "-D", DEVICE,
            "-d", str(STEP_SEC),
            "-f", "cd",
            "-t", "raw",
            "-q"
        ]
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        raw_data = proc.stdout.read()
        proc.wait()

        if raw_data:
            samples = struct.unpack("<{}h".format(len(raw_data)//2), raw_data)
            buffer.extend(samples)
            sum_squares = sum(sample**2 for sample in buffer) if buffer else 0
            rms_value = math.sqrt(sum_squares / len(buffer)) / 32768 if buffer else 0.0
        else:
            rms_value = 0.0

        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        write_state(rms_value, timestamp)

        # --- Notification check ---
        with lock:
            last_time = last_notification_time
        now = time.time()
        if rms_value > THRESHOLD and now - last_time > COOLDOWN_SEC:
            send_notification(rms_value)

        time.sleep(0.1)  # slight pause to prevent tight loop if arecord fails

def start_monitor():
    global _monitor_thread, _stop_event, DEVICE
    if _monitor_thread is not None and _monitor_thread.is_alive():
        return "Monitor already running."

    # --- Try possible devices ---
    for dev in ["plughw:0,0", "plughw:1,0"]:
        try:
            result = subprocess.run(
                ["arecord", "-D", dev, "-d", "1", "-f", "cd", "-t", "raw"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True
            )
            if result.stdout:
                DEVICE = dev
                break
        except subprocess.CalledProcessError:
            continue
    else:
        # --- No working device found ---
        return "No working audio device found (tried 0,0 and 1,0)."

    # --- Start monitor thread ---
    _stop_event.clear()
    _monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
    _monitor_thread.start()
    return f"Audio monitor started on {DEVICE}."

def stop_monitor():
    global _monitor_thread
    _stop_event.set()
    if _monitor_thread is not None:
        _monitor_thread.join(timeout=5)  # wait up to 5 seconds
        if _monitor_thread.is_alive():
            return "Monitor did not stop in time."
    return "Audio monitor successfully stopped."

def get_status():
    state = read_state()
    with lock:
        last_time = last_notification_time
    last_time_str = (
        time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_time))
        if last_time else "Never"
    )
    return {
        "current_rms": state.get("rms", 0.0),
        "threshold": THRESHOLD,
        "last_notification": last_time_str,
        "last_update": state.get("timestamp", "Never")
    }

# --- Flask routes ---
@app.route("/audio/start", methods=["POST"])
def route_start():
    msg = start_monitor()
    return jsonify({"status": msg})

@app.route("/audio/stop", methods=["GET"])
def audio_stop():
    msg = audio_server.stop_monitor()
    return jsonify({"status": msg})

@app.route("/audio/status", methods=["GET"])
def route_status():
    return jsonify(get_status())

# --- Standalone run ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False, threaded=True)
