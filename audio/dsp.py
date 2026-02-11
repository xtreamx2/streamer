# streamer/audio/dsp.py

import json
import time
import subprocess
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
EQ_CONFIG = BASE / "config" / "config-eq.json"
CAMILLA_CONFIG = Path("/etc/camilladsp/streamer.yml")


def load_cfg():
    return json.loads(EQ_CONFIG.read_text())


def write_camilla_yaml(text):
    CAMILLA_CONFIG.write_text(text)


def reload_camilla():
    subprocess.run(["systemctl", "reload", "camilladsp"], check=False)


def render_yaml(cfg):
    mode = cfg["mode"]
    presets = cfg["presets"]
    c2 = cfg["custom2_profiles"]
    c5 = cfg["custom5_profiles"]
    loud = cfg["loudness"]

    if mode == "preset":
        gains = presets[cfg["selected_preset"]]

    elif mode.startswith("custom2"):
        key = mode[-1]
        gains = {
            "60": c2[key]["bass"],
            "230": c2[key]["bass"],
            "910": 0,
            "3600": c2[key]["treble"],
            "14000": c2[key]["treble"]
        }

    elif mode.startswith("custom5"):
        key = mode[-1]
        gains = c5[key]

    else:
        gains = presets["FLAT"]

    # YAML – uproszczony, pipeline dopasujesz później
    out = ["filters:"]
    for f, g in gains.items():
        out.append(f"  peq_{f}:")
        out.append("    type: Peq")
        out.append(f"    freq: {float(f)}")
        out.append("    q: 1.0")
        out.append(f"    gain: {g}")

    if loud["enabled"]:
        out.append("  loud_low:")
        out.append("    type: Lowshelf")
        out.append("    freq: 80")
        out.append("    q: 0.7")
        out.append(f"    gain: {loud['strength'] / 10}")

        out.append("  loud_high:")
        out.append("    type: Highshelf")
        out.append("    freq: 8000")
        out.append("    q: 0.7")
        out.append(f"    gain: {loud['strength'] / 15}")

    return "\n".join(out) + "\n"


def main():
    last = None
    while True:
        cfg = load_cfg()
        if cfg != last:
            yaml = render_yaml(cfg)
            write_camilla_yaml(yaml)
            reload_camilla()
            last = cfg
        time.sleep(1)


if __name__ == "__main__":
    main()
