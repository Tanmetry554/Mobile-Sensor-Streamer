import argparse
import csv
import json
import socket
import sys
from datetime import datetime
import time
import math
import numpy as np
from collections import deque

import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets, QtCore
from pyqtgraph.opengl import GLViewWidget, GLGridItem, GLAxisItem, GLMeshItem, MeshData

# ======================================================
# Quaternion → Roll, Pitch, Yaw conversion
# ======================================================
def get_rpy_from_quaternion(vals):
    if len(vals) < 4:
        return None, None, None

    try:
        x, y, z, w = float(vals[0]), float(vals[1]), float(vals[2]), float(vals[3])
    except (ValueError, TypeError, IndexError):
        return None, None, None

    # --- Fix Android ENU → OpenGL right-handed frame ---
    q = np.array([x, y, z, w])
    q_fixed = np.array([q[0], -q[1], -q[2], q[3]])  # flip Y,Z
    q_conj = np.array([-q_fixed[0], -q_fixed[1], -q_fixed[2], q_fixed[3]])  # invert
    x, y, z, w = q_conj

    # Roll (x-axis)
    t0 = +2.0 * (w * x + y * z)
    t1 = +1.0 - 2.0 * (x * x + y * y)
    roll_x = math.atan2(t0, t1)

    # Pitch (y-axis)
    t2 = +2.0 * (w * y - z * x)
    t2 = +1.0 if t2 > +1.0 else t2
    t2 = -1.0 if t2 < -1.0 else t2
    pitch_y = math.asin(t2)

    # Yaw (z-axis)
    t3 = +2.0 * (w * z + x * y)
    t4 = +1.0 - 2.0 * (y * y + z * z)
    yaw_z = math.atan2(t3, t4)

    return math.degrees(roll_x), math.degrees(pitch_y), math.degrees(yaw_z), q_conj


# ======================================================
# Utility: Rotation matrix from quaternion
# ======================================================
def rotmat_from_quat(x, y, z, w):
    return np.array([
        [1 - 2*(y*y + z*z), 2*(x*y - z*w), 2*(x*z + y*w)],
        [2*(x*y + z*w), 1 - 2*(x*x + z*z), 2*(y*z - x*w)],
        [2*(x*z - y*w), 2*(y*z + x*w), 1 - 2*(x*x + y*y)]
    ], dtype=float)


# ======================================================
# Create cube mesh (manual for all PyQtGraph versions)
# ======================================================
def make_cube_mesh(size=20):
    verts = np.array([
        [-1, -1, -1],
        [-1, -1,  1],
        [-1,  1, -1],
        [-1,  1,  1],
        [ 1, -1, -1],
        [ 1, -1,  1],
        [ 1,  1, -1],
        [ 1,  1,  1],
    ], dtype=float)

    faces = np.array([
        [0, 1, 3], [0, 3, 2],
        [4, 6, 7], [4, 7, 5],
        [0, 4, 5], [0, 5, 1],
        [2, 3, 7], [2, 7, 6],
        [0, 2, 6], [0, 6, 4],
        [1, 5, 7], [1, 7, 3],
    ], dtype=int)

    mesh = MeshData(vertexes=verts, faces=faces)
    cube = GLMeshItem(
        meshdata=mesh,
        smooth=False,
        color=(0.2, 0.6, 1.0, 0.8),
        shader='shaded',
        drawEdges=True
    )
    cube.scale(size, size, size / 5)  # thinner to look like a phone
    return cube


# ======================================================
# Apply rotation matrix to cube
# ======================================================
def set_item_rotation(item, R, size):
    M = pg.Transform3D(
        R[0,0], R[0,1], R[0,2], 0.0,
        R[1,0], R[1,1], R[1,2], 0.0,
        R[2,0], R[2,1], R[2,2], 0.0,
        0.0,    0.0,    0.0,    1.0
    )
    item.setTransform(M)
    item.scale(size, size, size / 5)


# ======================================================
# Main app class
# ======================================================
class SensorVisualizer:
    def __init__(self, host="0.0.0.0", port=5005, csv_path=None):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((host, port))
        self.sock.settimeout(0.0)

        self.csvfile = open(csv_path, "w", newline="", encoding="utf-8") if csv_path else None
        self.writer = None
        if self.csvfile:
            self.writer = csv.writer(self.csvfile)
            self.writer.writerow(["host_ts", "ts_ns", "type", "name", "roll_deg", "pitch_deg", "yaw_deg", "values"])

        self.q_latest = np.array([0, 0, 0, 1], dtype=float)
        self.have_quat = False

        self.app = QtWidgets.QApplication(sys.argv)
        self.main = QtWidgets.QWidget()
        self.main.setWindowTitle("📱 Real-time 3D Orientation Visualizer")
        layout = QtWidgets.QVBoxLayout(self.main)

        # --- 3D View
        self.view3d = GLViewWidget()
        self.view3d.opts['distance'] = 120
        self.view3d.setMinimumSize(800, 600)
        layout.addWidget(self.view3d)

        grid = GLGridItem()
        grid.scale(10, 10, 1)
        self.view3d.addItem(grid)

        axis = GLAxisItem()
        axis.setSize(50, 50, 50)
        self.view3d.addItem(axis)

        # --- Cube
        self.cube = make_cube_mesh(size=20)
        self.view3d.addItem(self.cube)

        # --- Angle Label
        self.angle_label = QtWidgets.QLabel("Roll: 0°  Pitch: 0°  Yaw: 0°")
        self.angle_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.angle_label.setStyleSheet(
            "font-size: 18px; color: white; background-color: #222; padding: 10px; border-radius: 6px;"
        )
        layout.addWidget(self.angle_label)

        # --- Timer
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(16)

        print(f"Listening UDP on {host}:{port} ...")

    # ------------------------------------------
    def update(self):
        while True:
            try:
                data, addr = self.sock.recvfrom(65535)
            except BlockingIOError:
                break

            try:
                text = data.decode("utf-8", errors="ignore")
            except UnicodeDecodeError:
                continue

            for line in text.splitlines():
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                vals_raw = obj.get("values", [])
                if isinstance(vals_raw, str):
                    try:
                        vals = json.loads(vals_raw)
                    except json.JSONDecodeError:
                        vals = [vals_raw]
                elif isinstance(vals_raw, list):
                    vals = vals_raw
                else:
                    vals = []

                sensor_type = obj.get("type")
                name = obj.get("name", "Unknown")

                if sensor_type in [11, 15]:
                    roll, pitch, yaw, q = get_rpy_from_quaternion(vals)
                    if roll is not None:
                        self.q_latest = q
                        self.have_quat = True
                        self.angle_label.setText(
                            f"Roll: {roll:7.2f}°   Pitch: {pitch:7.2f}°   Yaw: {yaw:7.2f}°"
                        )
                        if self.writer:
                            host_ts = datetime.utcnow().isoformat()
                            self.writer.writerow([
                                host_ts,
                                obj.get("ts_ns"),
                                sensor_type,
                                name,
                                f"{roll:.2f}",
                                f"{pitch:.2f}",
                                f"{yaw:.2f}",
                                ";".join(str(v) for v in vals),
                            ])
                            self.csvfile.flush()

        # Update 3D orientation
        if self.have_quat:
            x, y, z, w = self.q_latest
            R = rotmat_from_quat(x, y, z, w)
            set_item_rotation(self.cube, R, 20)

    # ------------------------------------------
    def run(self):
        self.main.show()
        sys.exit(self.app.exec())


# ======================================================
# Entry Point
# ======================================================
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=5005)
    ap.add_argument("--csv", default=None)
    args = ap.parse_args()

    vis = SensorVisualizer(args.host, args.port, args.csv)
    vis.run()
