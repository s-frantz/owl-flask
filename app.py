#!/usr/bin/env python3
from flask import Flask, jsonify, render_template
import subprocess
import threading
import audio_server
import time
import os

app = Flask(__name__)

# --- Video globals ---
_video_thread = None
_video_processes = {}
_video_lock = threading.Lock()
VIDEO_DEVICE = "/dev/video0"
AUDIO_DEVICE_OPTIONS = ["hw:0,0", "hw:1,0"]
MEDIAMTX_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "mediamtx"))
FFMPEG_WARMUP_SEC = 2  # seconds to wait for ffmpeg to initialize

def is_process_running(process_name):
    try:
        subprocess.check_output(['pgrep', '-f', process_name])
        return True
    except subprocess.CalledProcessError:
        return False

def get_pi_status():
    streaming_on = is_process_running("mediamtx") and is_process_running("ffmpeg")
    listening_on = audio_server._monitor_thread is not None and audio_server._monitor_thread.is_alive()

    if streaming_on:
        state = "Streaming Video"
    elif listening_on:
        state = "Listening"
    else:
        state = "Idle"

    return state

# --- Video control functions ---
def start_video():
    global _video_thread, _video_processes

    with _video_lock:
        if _video_thread is not None and _video_thread.is_alive():
            return "Video already running."

        # --- Try possible audio devices ---
        selected_audio = None
        for dev in AUDIO_DEVICE_OPTIONS:
            try:
                result = subprocess.run(
                    ["arecord", "-D", dev, "-d", "1", "-f", "cd", "-t", "raw"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True
                )
                if result.stdout:
                    selected_audio = dev
                    break
            except subprocess.CalledProcessError:
                continue
        else:
            return "No working audio device found (tried 0,0 and 1,0)."

        try:
            # Start mediamtx independently in its root folder
            mediamtx_proc = subprocess.Popen(
                [MEDIAMTX_PATH],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=os.path.dirname(MEDIAMTX_PATH),  # run from mediamtx root
                start_new_session=True
            )

            # Start ffmpeg independently
            ffmpeg_cmd = [
                "ffmpeg", "-loglevel", "quiet",
                "-f", "v4l2", "-framerate", "30", "-video_size", "480x360", "-i", VIDEO_DEVICE,
                "-f", "alsa", "-i", selected_audio,
                "-c:v", "libx264", "-preset", "veryfast", "-tune", "zerolatency",
                "-c:a", "libopus", "-b:a", "64k",
                "-f", "rtsp", "rtsp://localhost:8554/stream"
            ]
            ffmpeg_proc = subprocess.Popen(
                ffmpeg_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )

        except OSError as e:
            return f"Failed to start video processes: {e}"

        # Add to processes dict
        _video_processes["mediamtx"] = mediamtx_proc
        _video_processes["ffmpeg"] = ffmpeg_proc

        # --- Warmup check ---
        time.sleep(FFMPEG_WARMUP_SEC)
        if ffmpeg_proc.poll() is not None:
            # ffmpeg exited early → likely bad audio device
            _video_processes.clear()
            return f"Failed to start ffmpeg (audio device {selected_audio})"

        # Thread to monitor processes (optional, mainly for cleanup/status)
        def monitor_video():
            try:
                while any(proc.poll() is None for proc in _video_processes.values()):
                    time.sleep(1)
            finally:
                with _video_lock:
                    _video_processes.clear()

        _video_thread = threading.Thread(target=monitor_video, daemon=True)
        _video_thread.start()

        return f"Video stream started using audio device {selected_audio}."

def stop_video():
    global _video_thread, _video_processes
    with _video_lock:
        if not _video_processes:
            return "Video not running."

        # iterate over a copy to avoid RuntimeError
        for name, proc in list(_video_processes.items()):
            proc.terminate()
        for name, proc in list(_video_processes.items()):
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        _video_processes.clear()
        return "Video stream stopped."

def video_status():
    with _video_lock:
        if not _video_processes:
            return {"status": "Video not running."}
        running = all(proc.poll() is None for proc in _video_processes.values())
        return {"status": "Streaming Video" if running else "Video stopped unexpectedly."}

# --- Routes ---
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/status", methods=["GET"])
def status():
    return jsonify({"status": get_pi_status()})

@app.route("/audio/start", methods=["GET"])
def audio_start():
    msg = audio_server.start_monitor()
    return jsonify({"status": msg})

@app.route("/audio/stop", methods=["GET"])
def audio_stop():
    msg = audio_server.stop_monitor()
    return jsonify({"status": msg})

@app.route("/audio/status", methods=["GET"])
def audio_status():
    return jsonify(audio_server.get_status())

@app.route("/video/start", methods=["GET"])
def route_video_start():
    msg = start_video()
    return jsonify({"status": msg})

@app.route("/video/stop", methods=["GET"])
def route_video_stop():
    msg = stop_video()
    return jsonify({"status": msg})

@app.route("/video/status", methods=["GET"])
def route_video_status():
    return jsonify(video_status())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
