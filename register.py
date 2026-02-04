import sys, json, threading
from awscrt import mqtt
from awsiot import mqtt_connection_builder

# ---------------- CONFIG ----------------
ENDPOINT = "a24vf5ncyln50t-ats.iot.eu-north-1.amazonaws.com"
TEMPLATE_NAME = "Vantilator"   # must EXACTLY match IoT provisioning template name

CERT_PATH = "bec06ffafa7f7fc47f0a596f0344899f96dd9c65bdad0f16fde981a3969d01dc-certificate.pem.crt"
KEY_PATH  = "bec06ffafa7f7fc47f0a596f0344899f96dd9c65bdad0f16fde981a3969d01dc-private.pem.key"
CA_PATH   = "AmazonRootCA1.pem"
# ---------------------------------------

response_event = threading.Event()
ownership_token = None
new_cert = None
new_key = None


def on_message_received(topic, payload, **kwargs):
    global ownership_token, new_cert, new_key
    data = json.loads(payload.decode())

    if "certificateOwnershipToken" in data:
        ownership_token = data["certificateOwnershipToken"]
        new_cert = data["certificatePem"]
        new_key = data["privateKey"]
        print("[STEP 1] Ownership token + new credentials received")

    elif "errorMessage" in data:
        print("[ERROR]", data["errorMessage"])

    response_event.set()


# -------- SERIAL NUMBER ARGUMENT --------
if len(sys.argv) < 2:
    print("Usage: python register.py <SERIAL_NUMBER>")
    sys.exit(1)

serial = sys.argv[1]
client_id = f"bootstrap-{serial}"


# -------- MQTT CONNECTION --------
mqtt_connection = mqtt_connection_builder.mtls_from_path(
    endpoint=ENDPOINT,
    cert_filepath=CERT_PATH,
    pri_key_filepath=KEY_PATH,
    ca_filepath=CA_PATH,
    client_id=client_id,
    clean_session=True
)

print("Connecting to AWS IoT...")
mqtt_connection.connect().result()
print("Connected")


# -------- STEP 1: CREATE CERT --------
create_cert_topic = "$aws/certificates/create/json"
create_accepted   = "$aws/certificates/create/json/accepted"

mqtt_connection.subscribe(
    topic=create_accepted,
    qos=mqtt.QoS.AT_LEAST_ONCE,
    callback=on_message_received
)

print("Requesting new certificate...")
mqtt_connection.publish(
    topic=create_cert_topic,
    payload="{}",
    qos=mqtt.QoS.AT_LEAST_ONCE
)

response_event.wait(5)
response_event.clear()

if not ownership_token:
    print("❌ Failed to receive ownership token")
    sys.exit(1)


# -------- STEP 2: PROVISION THING --------
register_topic = f"$aws/provisioning-templates/{TEMPLATE_NAME}/provision/json"
register_accepted = f"{register_topic}/accepted"

mqtt_connection.subscribe(
    topic=register_accepted,
    qos=mqtt.QoS.AT_LEAST_ONCE,
    callback=on_message_received
)

payload = {
    "certificateOwnershipToken": ownership_token,
    "Parameters": {
        "SerialNumber": serial
    }
}

print(f"Registering Thing: vantilator_{serial}")
mqtt_connection.publish(
    topic=register_topic,
    payload=json.dumps(payload),
    qos=mqtt.QoS.AT_LEAST_ONCE
)

response_event.wait(5)


# -------- STEP 3: SAVE NEW FILES --------
print("Saving new device credentials...")

with open(f"vantilator_{serial}-cert.pem.crt", "w") as f:
    f.write(new_cert)

with open(f"vantilator_{serial}-private.pem.key", "w") as f:
    f.write(new_key)

print("✅ SUCCESS!")
print(f"Created files:")
print(f"  vantilator_{serial}-cert.pem.crt")
print(f"  vantilator_{serial}-private.pem.key")

mqtt_connection.disconnect().result()
print("Disconnected from AWS IoT")