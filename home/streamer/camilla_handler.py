import yaml
import subprocess

CONFIG_PATH = "/etc/camilladsp/config.yml"

def update_eq(band, gain):
    """Update EQ gain and reload CamillaDSP"""
    with open(CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f)
    
    # Update gain in filter
    config["filters"][band]["parameters"]["gain"] = gain
    
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(config, f)
    
    # Reload CamillaDSP
    subprocess.run(["pkill", "camilladsp"])
    subprocess.run(["sudo", "camilladsp", CONFIG_PATH])
    
    return {"status": "updated", "band": band, "gain": gain}
