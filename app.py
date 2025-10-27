#!/usr/bin/env python3
from flask import Flask, jsonify, render_template
import subprocess
import audio_server


app = Flask(__name__)


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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
