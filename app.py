#!/usr/bin/env python3
from flask import Flask, jsonify, render_template, Response, send_file
import subprocess

app = Flask(__name__)

# -----------------------
# Helper Functions
# -----------------------
def is_process_running(process_name):
    try:
        subprocess.check_output(['pgrep', '-f', process_name])
        return True
    except subprocess.CalledProcessError:
        return False

def get_pi_status():
    streaming_on = is_process_running("mediamtx") and is_process_running("ffmpeg")
    listening_on = is_process_running("rms_monitor.py")

    if streaming_on:
        state = "Streaming Video"
    elif listening_on:
        state = "Listening"
    else:
        state = "Idle"

    return state

# -----------------------
# Routes
# -----------------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/status", methods=["GET"])
def status():
    return jsonify({"status": get_pi_status()})

# -----------------------
# Minimal toggle route
# -----------------------
@app.route("/toggle_video", methods=["POST"])
def toggle_video():
    """Return current Pi status. JS handles actual video display."""
    return jsonify({"status": get_pi_status()})

# -----------------------
# MJPEG HTML Page
# -----------------------
@app.route("/jpeg")
def mjpeg():
    return render_template("jpeg.html")

@app.route("/mp4")
def mp4():
    return render_template("mp4.html")

# -----------------------
# Main
# -----------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
