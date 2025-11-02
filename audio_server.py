#!/usr/bin/env python3
import os
import time
import json
import struct
import math
import threading
import requests
import subprocess
import wave
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
RECORD_AFTER_SEC = 18  # post-event recording duration
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "recordings")
os.makedirs(OUTPUT_DIR, exist_ok=True)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "rms_state.json")

# --- Globals ---
buffer = deque(maxlen=WINDOW_SEC * SAMPLE_RATE * CHANNELS)
last_notification_time = 0
lock = threading.Lock()
_monitor_thread = None
_stop_event = threading.Event()
_recording_lock = threading.Lock()

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

def save_wav(filename, samples):
    """Write a WAV file from raw PCM samples"""
    with wave.open(filename, 'w') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(struct.pack("<{}h".format(len(samples)), *samples))

def record_event(pre_buffer, duration_sec):
    """Save pre-buffer + record post-event audio (delete old recordings first)"""
    with _recording_lock:
        # --- Delete old recordings ---
        for f in os.listdir(OUTPUT_DIR):
            if f.endswith(".wav") or f.endswith(".dismissed"):
                try:
                    os.remove(os.path.join(OUTPUT_DIR, f))
                except OSError:
                    pass  # ignore deletion errors

        filename = os.path.join(
            OUTPUT_DIR, f"event_{time.strftime('%Y%m%d_%H%M%S')}.wav"
        )
        print(f"Recording event audio to {filename}...")
        samples = list(pre_buffer)

        # Record post-event audio
        cmd = [
            "arecord",
            "-D", DEVICE,
            "-f", "cd",
            "-t", "raw",
            "-d", str(duration_sec),
            "-q"
        ]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, start_new_session=True)
        raw_post = proc.stdout.read()
        proc.wait()
        if raw_post:
            post_samples = struct.unpack("<{}h".format(len(raw_post)//2), raw_post)
            samples.extend(post_samples)

        save_wav(filename, samples)
        print(f"Event recording saved: {filename}")

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

        # --- Notification & recording check ---
        with lock:
            last_time = last_notification_time
        now = time.time()
        if rms_value > THRESHOLD and now - last_time > COOLDOWN_SEC:
            send_notification(rms_value)
            # Record event: pre-buffer + post-event
            record_event(buffer, RECORD_AFTER_SEC)

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
        _monitor_thread.join(timeout=5)   # wait up to 5 seconds
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
def route_stop():
    msg = stop_monitor()
    return jsonify({"status": msg})

@app.route("/audio/status", methods=["GET"])
def route_status():
    return jsonify(get_status())

# --- Standalone run ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False, threaded=True)
