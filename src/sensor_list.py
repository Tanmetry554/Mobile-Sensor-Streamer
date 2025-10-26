import argparse
import json
import socket
import sys
import time

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0", help="Bind address")
    ap.add_argument("--port", type=int, default=5005, help="UDP port to listen on")
    args = ap.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((args.host, args.port))
    sock.settimeout(0.0)  # non-blocking

    # This set will store the unique sensors we've found
    seen_sensors = set()

    print(f"Listening on {args.host}:{args.port}...")
    print("Waiting for data to discover sensors...")

    try:
        while True:
            try:
                data, addr = sock.recvfrom(65535)
            except BlockingIOError:
                time.sleep(0.001)
                continue

            text = data.decode("utf-8", errors="ignore")
            for line in text.splitlines():
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # Get the sensor type and name
                sensor_type = obj.get('type')
                name = obj.get('name', 'Unknown')

                # Skip if data is incomplete
                if sensor_type is None:
                    continue
                
                # We use a tuple (type, name) as a unique identifier
                sensor_id = (sensor_type, name)

                # Check if this is a new sensor
                if sensor_id not in seen_sensors:
                    seen_sensors.add(sensor_id)
                    
                    print(f"\n[+] New sensor found: {name}")
                    print("--- All Active Sensors Seen So Far ---")
                    
                    # Sort the list by sensor type number for a clean display
                    sorted_list = sorted(list(seen_sensors), key=lambda s: s[0])
                    
                    for s_type, s_name in sorted_list:
                        print(f"  Type {s_type:<2} | Name: {s_name}")
                    
                    print("--------------------------------------\n")

    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        sock.close()
        print("Socket closed.")

if __name__ == "__main__":
    main()