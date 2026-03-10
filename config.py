from dotenv import load_dotenv
import os

load_dotenv()  # load variables from .env file

MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_PORT = int(os.getenv("MQTT_PORT"))
AQICN_TOKEN = os.getenv("AQICN_TOKEN")
UPDATE_INTERVAL = int(os.getenv("UPDATE_INTERVAL"))
