import time
import json
import psutil
from awscrt import mqtt
from awsiot import mqtt_connection_builder

# -------- CONFIGURATION --------
ENDPOINT = "a24vf5ncyln50t-ats.iot.eu-north-1.amazonaws.com"

SERIAL = "001"
THING_NAME = f"vantilator_{SERIAL}"

CA_PATH = "AmazonRootCA1.pem"
CERT_PATH = f"vantilator_{SERIAL}-cert.pem.crt"
KEY_PATH  = f"vantilator_{SERIAL}-private.pem.key"

TOPIC = f"vantilator/{SERIAL}/data"
INTERVAL = 5  # seconds
# --------------------------------


def get_laptop_data():
    cpu = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    battery = psutil.sensors_battery()

    return {
        "device": "laptop",
        "cpu_usage_percent": cpu,
        "ram_usage_percent": memory.percent,
        "ram_used_mb": round(memory.used / (1024 * 1024), 2),
        "disk_usage_percent": disk.percent,
        "battery_percent": battery.percent if battery else None,
        "power_plugged": battery.power_plugged if battery else None,
        "status": "online",
        "timestamp": int(time.time())
    }


print("Starting laptop → AWS IoT sender...")

mqtt_connection = mqtt_connection_builder.mtls_from_path(
    endpoint=ENDPOINT,
    cert_filepath=CERT_PATH,
    pri_key_filepath=KEY_PATH,
    ca_filepath=CA_PATH,
    client_id=THING_NAME,
    clean_session=False,
    keep_alive_secs=30
)

print("Connecting to AWS IoT...")
mqtt_connection.connect().result()
print("✅ Connected to AWS IoT")

try:
    while True:
        payload = get_laptop_data()

        print("📤 Sending:", payload)

        mqtt_connection.publish(
            topic=TOPIC,
            payload=json.dumps(payload),
            qos=mqtt.QoS.AT_LEAST_ONCE
        )

        time.sleep(INTERVAL)

except KeyboardInterrupt:
    print("Stopping data sender...")

finally:
    mqtt_connection.disconnect().result()
    print("Disconnected from AWS IoT")
