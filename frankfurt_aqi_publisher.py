#!/usr/bin/env python3

import time
import requests
import signal
import sys
import paho.mqtt.client as mqtt
from config import MQTT_BROKER, MQTT_PORT, AQICN_TOKEN, UPDATE_INTERVAL

# ======================================================
# DEFAULT SETTINGS
# ======================================================
DEFAULT_STATION_ID = 10855  # Frankfurt-Ost
selected_station_id = DEFAULT_STATION_ID

# ======================================================
# MQTT SETUP (Callback API v2)
# ======================================================
client = mqtt.Client(
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2
)

def publish(topic, value):
    """Publish value to MQTT topic (retain=True)"""
    client.publish(topic, str(value), retain=True)

# ======================================================
# ALERT LOGIC
# ======================================================
def evaluate_alert(aqi):
    try:
        aqi = int(aqi)
    except (ValueError, TypeError):
        return ("UNKNOWN", "No data available")

    if aqi == 0:
        return ("UNKNOWN", "No data available")
    elif aqi <= 50:
        return ("GOOD", "Air quality is good")
    elif aqi <= 100:
        return ("MODERATE", "Air quality is moderate")
    elif aqi <= 150:
        return ("UNHEALTHY_SENSITIVE", "Unhealthy for sensitive groups")
    elif aqi <= 200:
        return ("UNHEALTHY", "Air quality is unhealthy")
    else:
        return ("VERY_UNHEALTHY", "Air quality is very unhealthy")

# ======================================================
# NO DATA HANDLER (PUBLISH ZERO)
# ======================================================
def publish_no_data():
    print("[INFO] Publishing NO DATA (0)")

    publish("openhab/aqi/frankfurt/current/aqi", 0)
    publish("openhab/aqi/frankfurt/current/pm25", 0)
    publish("openhab/aqi/frankfurt/current/pm10", 0)
    publish("openhab/aqi/frankfurt/current/temp", 0)
    publish("openhab/aqi/frankfurt/current/humidity", 0)
    publish("openhab/aqi/frankfurt/current/wind", 0)

    publish("openhab/aqi/frankfurt/alert/level", "UNKNOWN")
    publish("openhab/aqi/frankfurt/alert/message", "No data available")

# ======================================================
# MQTT CALLBACKS
# ======================================================
def on_connect(client, userdata, flags, reason_code, properties=None):
    print("[INFO] Connected to MQTT broker, rc =", reason_code)
    client.subscribe("openhab/aqi/frankfurt/region_id")
    print("[INFO] Subscribed to openhab/aqi/frankfurt/region_id")

def on_message(client, userdata, msg):
    global selected_station_id
    payload = msg.payload.decode().strip().replace('"', '')

    print(f"[MQTT] Received region_id: {payload}")

    try:
        selected_station_id = int(payload)
        print(f"[INFO] Selected station updated to {selected_station_id}")
        publish_aqi(selected_station_id)
    except ValueError:
        print(f"[WARNING] Invalid station ID received: {payload}")

client.on_connect = on_connect
client.on_message = on_message

client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_start()

# ======================================================
# AQI FETCHING
# ======================================================
def fetch_aqi_data(station_id):
    url = f"https://api.waqi.info/feed/@{station_id}/?token={AQICN_TOKEN}"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("status") != "ok":
            print("[WARNING] API returned non-ok status")
            return None

        iaqi = data["data"].get("iaqi", {})
        return {
            "aqi": data["data"].get("aqi"),
            "pm25": iaqi.get("pm25", {}).get("v"),
            "pm10": iaqi.get("pm10", {}).get("v"),
            "temp": iaqi.get("t", {}).get("v"),
            "humidity": iaqi.get("h", {}).get("v"),
            "wind": iaqi.get("w", {}).get("v")
        }

    except Exception as e:
        print("[ERROR] Failed to fetch AQI:", e)
        return None

# ======================================================
# PUBLISH AQI + ALERTS
# ======================================================
def publish_aqi(station_id):
    data = fetch_aqi_data(station_id)

    # 🚨 NO DATA for ANY station
    if (
        not data or
        data.get("aqi") in (None, "-", "N/A") or
        str(data.get("aqi")).strip() == ""
    ):
        print(f"[WARNING] No AQI data for station {station_id}")
        publish_no_data()
        return

    print(f"[INFO] Publishing AQI for station {station_id}")

    publish("openhab/aqi/frankfurt/current/aqi", data["aqi"])
    publish("openhab/aqi/frankfurt/current/pm25", data["pm25"] or 0)
    publish("openhab/aqi/frankfurt/current/pm10", data["pm10"] or 0)
    publish("openhab/aqi/frankfurt/current/temp", data["temp"] or 0)
    publish("openhab/aqi/frankfurt/current/humidity", data["humidity"] or 0)
    publish("openhab/aqi/frankfurt/current/wind", data["wind"] or 0)

    level, message = evaluate_alert(data["aqi"])
    publish("openhab/aqi/frankfurt/alert/level", level)
    publish("openhab/aqi/frankfurt/alert/message", message)

    print(f"[ALERT] {level} → {message}")

# ======================================================
# SHUTDOWN HANDLER
# ======================================================
def signal_handler(sig, frame):
    print("[INFO] Shutting down AQI service...")
    client.loop_stop()
    client.disconnect()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# ======================================================
# MAIN LOOP
# ======================================================
print(f"[INFO] AQI service started (default station: {DEFAULT_STATION_ID})")

while True:
    publish_aqi(selected_station_id)
    time.sleep(UPDATE_INTERVAL)
