import argparse
import csv
import json
import socket
import sys
from datetime import datetime
import time
import math

def get_rpy_from_quaternion(vals):
    """
    Converts Android rotation vector quaternion (x, y, z, w) to RPY angles.
    """
    if len(vals) < 4:
        return None, None, None

    try:
        # Attempt to cast all required values to float
        # This handles values that are numbers OR strings of numbers
        x, y, z, w = float(vals[0]), float(vals[1]), float(vals[2]), float(vals[3])
    except (ValueError, TypeError, IndexError):
        # If any value is not a number or list is short, abort
        return None, None, None

    # Roll (x-axis rotation)
    t0 = +2.0 * (w * x + y * z)
    t1 = +1.0 - 2.0 * (x * x + y * y)
    roll_x = math.atan2(t0, t1)

    # Pitch (y-axis rotation)
    t2 = +2.0 * (w * y - z * x)
    t2 = +1.0 if t2 > +1.0 else t2
    t2 = -1.0 if t2 < -1.0 else t2
    pitch_y = math.asin(t2)

    # Yaw (z-axis rotation)
    t3 = +2.0 * (w * z + x * y)
    t4 = +1.0 - 2.0 * (y * y + z * z)
    yaw_z = math.atan2(t3, t4)

    # Return angles in degrees
    return math.degrees(roll_x), math.degrees(pitch_y), math.degrees(yaw_z)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0", help="Bind address")
    ap.add_argument("--port", type=int, default=5005, help="UDP port to listen on")
    ap.add_argument("--csv", default=None, help="Optional CSV output file")
    args = ap.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((args.host, args.port))
    sock.settimeout(0.0)  # non-blocking

    writer = None
    csvfile = None
    if args.csv:
        csvfile = open(args.csv, "w", newline="", encoding="utf-8")
        writer = csv.writer(csvfile)
        writer.writerow(["host_ts", "ts_ns", "type", "name", "vendor", "version", "acc", "values", "roll_deg", "pitch_deg", "yaw_deg"])

    print(f"Listening UDP on {args.host}:{args.port}")
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

                host_ts = datetime.utcnow().isoformat()
                
                vals_raw = obj.get("values", []) # Get the raw 'values' field
                sensor_type = obj.get("type")
                name = obj.get("name", "Unknown")
                acc_val = obj.get("acc", "?")

                # <--- MODIFIED: Fix for string-encoded 'values' field
                vals = []
                if isinstance(vals_raw, str):
                    try:
                        # Try to parse the string as a JSON list
                        vals = json.loads(vals_raw)
                    except json.JSONDecodeError:
                        # Not a JSON string, just keep it as a single-item list
                        vals = [vals_raw]
                elif isinstance(vals_raw, list):
                    # It's already a list, use it as-is
                    vals = vals_raw
                # --- END MODIFICATION ---


                roll, pitch, yaw = None, None, None
                
                # Types 11 (Rotation Vector) and 15 (Game Rotation Vector)
                if sensor_type in [11, 15]:
                    roll, pitch, yaw = get_rpy_from_quaternion(vals)
                    
                    # <--- MODIFIED: Only print RPY values, and only if successful
                    if roll is not None:
                        print(f"Roll: {roll: >7.2f}, Pitch: {pitch: >7.2f}, Yaw: {yaw: >7.2f}")
                
                # <--- MODIFIED: The old, comprehensive print statement has been removed
                
                if writer:
                    # CSV writing is unchanged
                    writer.writerow([
                        host_ts,
                        obj.get("ts_ns"),
                        sensor_type,
                        name,
                        obj.get("vendor"),
                        obj.get("version"),
                        acc_val,
                        ";".join(str(v) for v in vals),
                        roll if roll is not None else "",
                        pitch if pitch is not None else "",
                        yaw if yaw is not None else ""
                    ])
                    csvfile.flush()
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        if csvfile:
            csvfile.close()
        sock.close()

if __name__ == "__main__":
    main()