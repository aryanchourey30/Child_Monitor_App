import json
import socket
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import paho.mqtt.client as mqtt

# =========================
# CONFIG
# =========================
BROKER_HOST = "192.168.1.24"   # change to your broker/laptop IP
BROKER_PORT = 1883
CLIENT_ID = "grainfy-rpi-cam-01"

TOPIC_FRAME = "guardianbaby/frame/jpeg"
TOPIC_META = "guardianbaby/frame/meta"
TOPIC_HEARTBEAT = "guardianbaby/device/heartbeat"

CAPTURE_INTERVAL_SEC = 15   # 4 frames per minute
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720
JPEG_QUALITY = 85

# Your project folder
BASE_DIR = Path("/home/pi/grainfy/vdout")
TEMP_DIR = BASE_DIR / "temp_frames"
TEMP_DIR.mkdir(parents=True, exist_ok=True)


# =========================
# HELPERS
# =========================
def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def hostname() -> str:
    return socket.gethostname()


def build_meta(frame_id: str, image_size: int) -> dict:
    return {
        "device_id": CLIENT_ID,
        "hostname": hostname(),
        "timestamp": utc_now_iso(),
        "frame_id": frame_id,
        "encoding": "jpeg",
        "width": CAMERA_WIDTH,
        "height": CAMERA_HEIGHT,
        "image_size_bytes": image_size,
    }


def capture_frame_to_file(output_file: str) -> None:
    cmd = [
        "rpicam-still",
        "--output", output_file,
        "--width", str(CAMERA_WIDTH),
        "--height", str(CAMERA_HEIGHT),
        "--quality", str(JPEG_QUALITY),
        "--immediate",
        "-n",
    ]
    subprocess.run(cmd, check=True)


# =========================
# MQTT CALLBACKS
# =========================
def on_connect(client, userdata, flags, reason_code, properties=None):
    print(f"[MQTT] Connected with reason_code={reason_code}")


def on_disconnect(client, userdata, disconnect_flags, reason_code, properties=None):
    print(f"[MQTT] Disconnected reason_code={reason_code}")


# =========================
# MAIN
# =========================
def main() -> None:
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=CLIENT_ID,
        protocol=mqtt.MQTTv311,
    )
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

    client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
    client.loop_start()

    print("[INFO] Publisher started")
    print(f"[INFO] Broker: {BROKER_HOST}:{BROKER_PORT}")
    print(f"[INFO] Publishing JPEG frames every {CAPTURE_INTERVAL_SEC} seconds")
    print("[INFO] Temporary frame files will be deleted after publish")

    try:
        while True:
            loop_start = time.time()
            ts = datetime.now(timezone.utc)
            frame_id = ts.strftime("%Y%m%dT%H%M%S.%fZ")
            frame_file = TEMP_DIR / f"{frame_id}.jpg"

            # 1) Capture frame
            try:
                capture_frame_to_file(str(frame_file))
            except subprocess.CalledProcessError as e:
                print(f"[ERROR] rpicam-still failed: {e}")
                time.sleep(CAPTURE_INTERVAL_SEC)
                continue

            # 2) Read frame bytes
            try:
                image_bytes = frame_file.read_bytes()
            except Exception as e:
                print(f"[ERROR] Could not read frame file {frame_file}: {e}")
                try:
                    frame_file.unlink(missing_ok=True)
                except Exception:
                    pass
                time.sleep(CAPTURE_INTERVAL_SEC)
                continue

            # 3) Build metadata
            meta = build_meta(frame_id, len(image_bytes))
            meta_payload = json.dumps(meta)

            # 4) Publish metadata + frame bytes
            try:
                meta_info = client.publish(TOPIC_META, meta_payload, qos=1)
                frame_info = client.publish(TOPIC_FRAME, image_bytes, qos=1)

                meta_info.wait_for_publish()
                frame_info.wait_for_publish()

                print(
                    f"[INFO] Published frame {frame_id} "
                    f"({len(image_bytes)} bytes) at {meta['timestamp']}"
                )
            except Exception as e:
                print(f"[ERROR] MQTT publish failed for frame {frame_id}: {e}")

            # 5) Delete temp frame after publish attempt
            try:
                frame_file.unlink(missing_ok=True)
            except Exception as e:
                print(f"[WARN] Could not delete temp frame {frame_file}: {e}")

            # 6) Publish heartbeat
            try:
                heartbeat = {
                    "device_id": CLIENT_ID,
                    "hostname": hostname(),
                    "timestamp": utc_now_iso(),
                    "status": "online",
                }
                client.publish(TOPIC_HEARTBEAT, json.dumps(heartbeat), qos=0)
            except Exception as e:
                print(f"[WARN] Heartbeat publish failed: {e}")

            # 7) Sleep until next interval
            elapsed = time.time() - loop_start
            sleep_time = max(0.0, CAPTURE_INTERVAL_SEC - elapsed)
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("[INFO] Stopping publisher...")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
