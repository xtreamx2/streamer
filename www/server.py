#!/usr/bin/env python3
from flask import Flask

app = Flask(__name__)

@app.get("/")
def index():
    return "Streamer Web UI działa!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
