import socket
import json

UDP_IP = "0.0.0.0"
UDP_PORT = 5005

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))

print(f"Listening for GPS data on {UDP_IP}:{UDP_PORT} ...")

while True:
    data, addr = sock.recvfrom(65535)
    try:
        text = data.decode("utf-8")
        for line in text.splitlines():
            obj = json.loads(line)

            name = obj.get("name", "")
            if "gps" in name.lower():
                vals = obj.get("values", [])
                if len(vals) >= 5:
                    lat, lon, alt, speed, acc = vals[:5]
                    print(f"📍 GPS: lat={lat:.6f}, lon={lon:.6f}, alt={alt:.2f} m, "
                          f"speed={speed:.2f} m/s, acc={acc:.2f} m")
                elif len(vals) >= 4:
                    lat, lon, alt, acc = vals[:4]
                    print(f"📍 GPS: lat={lat:.6f}, lon={lon:.6f}, alt={alt:.2f} m, acc={acc:.2f} m")

    except json.JSONDecodeError:
        continue
