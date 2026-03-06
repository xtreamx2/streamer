from flask import Flask, render_template, request, redirect
from mpd import MPDClient
import json
import requests
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR.parent / "config"
CONFIG_RADIO = CONFIG_DIR / "config-radio.json"

app = Flask(__name__)

# ------------------------------
# Helpers
# ------------------------------

def load_stations():
    if not CONFIG_RADIO.exists():
        return {"stations": []}
    return json.loads(CONFIG_RADIO.read_text())

def save_stations(data):
    CONFIG_RADIO.write_text(json.dumps(data, indent=2))

def mpd_client():
    c = MPDClient()
    try:
        c.connect("localhost", 6600)
        return c
    except:
        return None

# ------------------------------
# M3U resolver
# ------------------------------

def resolve_m3u(url):
    if not url.lower().endswith(".m3u"):
        return url
    try:
        r = requests.get(url, timeout=5)
        for line in r.text.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                return line
    except:
        pass
    return url

# ------------------------------
# Routes
# ------------------------------

@app.route("/")
def index():
    data = load_stations()
    client = mpd_client()
    status = {}

    if client:
        try:
            status = client.status()
            song = client.currentsong()
            status["title"] = song.get("title", "")
        except:
            pass

    return render_template("index.html", stations=data["stations"], status=status)

@app.route("/play/<name>")
def play(name):
    data = load_stations()
    client = mpd_client()

    if client:
        for s in data["stations"]:
            if s["name"] == name:
                try:
                    client.clear()
                    client.add(s["url"])
                    client.play()
                except:
                    pass
                break

    return redirect("/")

@app.route("/stop")
def stop():
    client = mpd_client()
    if client:
        try:
            client.stop()
        except:
            pass
    return redirect("/")

@app.route("/edit/<name>", methods=["GET", "POST"])
def edit(name):
    data = load_stations()
    station = next((s for s in data["stations"] if s["name"] == name), None)

    if request.method == "POST":
        station["name"] = request.form["name"]
        station["url"] = resolve_m3u(request.form["url"])
        station["favorite"] = ("favorite" in request.form)
        save_stations(data)
        return redirect("/")

    return render_template("edit.html", station=station)

@app.route("/delete/<name>")
def delete(name):
    data = load_stations()
    data["stations"] = [s for s in data["stations"] if s["name"] != name]
    save_stations(data)
    return redirect("/")

@app.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        data = load_stations()
        data["stations"].append({
            "name": request.form["name"],
            "url": resolve_m3u(request.form["url"]),
            "favorite": ("favorite" in request.form),
            "tags": []
        })
        save_stations(data)
        return redirect("/")
    return render_template("edit.html", station=None)

# ------------------------------
# Run
# ------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
