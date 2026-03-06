import logging

def setup_logger():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler("/var/log/streamer.log"),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger("streamer")
