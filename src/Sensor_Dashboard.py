

HOST = "0.0.0.0"
PORT = 5005
CSV_PATH = None
UPDATE_MS = 33
GPS_HISTORY = 5000

# --- Qt attributes must be set BEFORE QApplication creation ---
from PyQt5.QtCore import QCoreApplication, Qt
QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)

# --- Now safe to import everything ---
import sys
import socket
import json
import csv
import math
import os
from collections import deque
from datetime import datetime
import numpy as np

# Import all GUI and OpenGL modules AFTER setting the attribute
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWebEngineWidgets import QWebEngineView
import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets, QtCore
from pyqtgraph.opengl import GLViewWidget, GLGridItem, GLAxisItem, GLMeshItem, MeshData
import folium

# --- Initialize QApplication now ---
qt_app = QApplication(sys.argv)





# ======================
# Quaternion → RPY
# ======================
def get_rpy_from_quaternion(vals):
    if len(vals) < 4:
        return None, None, None, None
    try:
        x, y, z, w = map(float, vals[:4])
    except (ValueError, TypeError):
        return None, None, None, None

    # Android ENU → OpenGL RHS fix + invert
    q = np.array([x, y, z, w], dtype=float)
    q_fixed = np.array([q[0], -q[1], -q[2], q[3]], dtype=float)
    q_conj = np.array([-q_fixed[0], -q_fixed[1], -q_fixed[2], q_fixed[3]], dtype=float)
    x, y, z, w = q_conj

    # Roll, Pitch, Yaw
    t0 = 2.0 * (w * x + y * z)
    t1 = 1.0 - 2.0 * (x * x + y * y)
    roll = math.degrees(math.atan2(t0, t1))
    t2 = 2.0 * (w * y - z * x)
    t2 = max(-1.0, min(1.0, t2))
    pitch = math.degrees(math.asin(t2))
    t3 = 2.0 * (w * z + x * y)
    t4 = 1.0 - 2.0 * (y * y + z * z)
    yaw = math.degrees(math.atan2(t3, t4))
    return roll, pitch, yaw, q_conj


def rotmat_from_quat(x, y, z, w):
    return np.array([
        [1 - 2*(y*y + z*z), 2*(x*y - z*w),     2*(x*z + y*w)],
        [2*(x*y + z*w),     1 - 2*(x*x + z*z), 2*(y*z - x*w)],
        [2*(x*z - y*w),     2*(y*z + x*w),     1 - 2*(x*x + y*y)]
    ], dtype=float)


# ======================
# 3D Cube Mesh
# ======================
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
    cube = GLMeshItem(meshdata=mesh, smooth=False,
                      color=(0.2, 0.6, 1.0, 0.85),
                      shader='shaded', drawEdges=True)
    cube.scale(size, size, size / 5)
    return cube


def set_item_rotation(item, R, size):
    M = pg.Transform3D(
        R[0, 0], R[0, 1], R[0, 2], 0.0,
        R[1, 0], R[1, 1], R[1, 2], 0.0,
        R[2, 0], R[2, 1], R[2, 2], 0.0,
        0.0, 0.0, 0.0, 1.0
    )
    item.setTransform(M)
    item.scale(size, size, size / 5)


# ======================
# Main Dashboard
# ======================
class SensorDashboard:
    def __init__(self, host, port, csv_path=None):
        # --- Qt must be created first ---
        self.app = QtWidgets.QApplication(sys.argv)

        # UDP setup
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((host, port))
        self.sock.settimeout(0.0)
        print(f"Listening on {host}:{port} ...")

        # CSV logging
        self.csvfile = None
        self.writer = None
        if csv_path:
            self.csvfile = open(csv_path, "w", newline="", encoding="utf-8")
            self.writer = csv.writer(self.csvfile)
            self.writer.writerow([
                "host_ts", "type", "name", "roll", "pitch", "yaw",
                "lat", "lon", "alt", "speed", "acc",
                "batt_V", "batt_A", "batt_W", "charging"
            ])

        # --- GUI setup ---
        self.main = QtWidgets.QMainWindow()
        self.main.setWindowTitle("🌍 Real-time Sensor Dashboard (3D + Map)")
        self.central = QtWidgets.QWidget()
        self.main.setCentralWidget(self.central)
        layout = QtWidgets.QHBoxLayout(self.central)

        # 3D Orientation View
        self.view3d = GLViewWidget()
        self.view3d.opts['distance'] = 120
        self.view3d.setMinimumSize(600, 600)
        grid = GLGridItem()
        grid.scale(10, 10, 1)
        axis = GLAxisItem()
        axis.setSize(50, 50, 50)
        self.cube = make_cube_mesh(20)
        self.view3d.addItem(grid)
        self.view3d.addItem(axis)
        self.view3d.addItem(self.cube)

        # 2D OpenStreetMap View
        self.map_view = QWebEngineView()
        self.map_html = os.path.join(os.getcwd(), "realtime_map.html")
        self._create_map_html(0, 0)
        self.map_view.load(QtCore.QUrl.fromLocalFile(self.map_html))

        layout.addWidget(self.view3d)
        layout.addWidget(self.map_view)

        # Status panel
        self.status = QtWidgets.QLabel("Waiting for data...")
        self.status.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.status.setStyleSheet("font-size:14px;background:#222;color:white;padding:5px;")
        layout.addWidget(self.status)

        # State
        self.q_latest = np.array([0, 0, 0, 1], dtype=float)
        self.have_quat = False
        self.roll = self.pitch = self.yaw = 0.0
        self.lat = self.lon = 0
        self.batt_v = self.batt_a = self.batt_w = 0
        self.batt_chg = 0

        # GPS trail
        self.gps_points = deque(maxlen=GPS_HISTORY)

        # Timer
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self._update)
        self.timer.start(UPDATE_MS)


    def _create_map_html(self, lat, lon):
        m = folium.Map(location=[lat or 0, lon or 0], zoom_start=3, tiles="OpenStreetMap")
        m.save(self.map_html)

    def _update_map_marker(self, lat, lon):
        m = folium.Map(location=[lat, lon], zoom_start=17, tiles="OpenStreetMap")
        folium.Marker(location=[lat, lon], popup="📍 Phone").add_to(m)
        folium.PolyLine(list(self.gps_points), color="blue", weight=3).add_to(m)
        m.save(self.map_html)
        self.map_view.reload()

    def _update(self):
        while True:
            try:
                data, addr = self.sock.recvfrom(65535)
            except BlockingIOError:
                break

            text = data.decode("utf-8", errors="ignore")
            for line in text.splitlines():
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                name = obj.get("name", "")
                stype = obj.get("type")
                vals = obj.get("values", [])
                if isinstance(vals, str):
                    try:
                        vals = json.loads(vals)
                    except json.JSONDecodeError:
                        vals = [vals]

                # Orientation
                if stype in [11, 15, 20] or "rotation" in name.lower():
                    roll, pitch, yaw, q = get_rpy_from_quaternion(vals)
                    if roll is not None:
                        self.roll, self.pitch, self.yaw = roll, pitch, yaw
                        self.q_latest = q
                        self.have_quat = True

                # GPS
                elif "gps" in name.lower():
                    if len(vals) >= 2:
                        self.lat, self.lon = vals[0], vals[1]
                        self.gps_points.append((self.lat, self.lon))
                        self._update_map_marker(self.lat, self.lon)

                # Battery
                elif "battery" in name.lower():
                    if len(vals) >= 3:
                        self.batt_v, self.batt_a, self.batt_w = vals[:3]
                        if len(vals) >= 4:
                            self.batt_chg = int(vals[3])

        # Update 3D Cube
        if self.have_quat:
            x, y, z, w = self.q_latest
            R = rotmat_from_quat(x, y, z, w)
            set_item_rotation(self.cube, R, 20)

        self.status.setText(
            f"📡 Roll={self.roll:6.1f}° Pitch={self.pitch:6.1f}° Yaw={self.yaw:6.1f}°  "
            f"📍 Lat={self.lat:.5f}, Lon={self.lon:.5f}  🔋 {self.batt_v:.2f}V  {'⚡' if self.batt_chg else ''}"
        )

    def run(self):
        self.main.show()
        sys.exit(self.app.exec())


# ======================
# Entry Point
# ======================
if __name__ == "__main__":
    dashboard = SensorDashboard(HOST, PORT, CSV_PATH)
    dashboard.main.show()
    sys.exit(qt_app.exec())

