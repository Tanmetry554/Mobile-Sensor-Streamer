## Phone Sensor Streamer & Dashboard

This project allows you to stream real-time sensor data (accelerometer, gyroscope, magnetometer, GPS, battery, etc.) from an Android phone to a Python dashboard on your PC via UDP/IP.

It includes individual scripts for testing specific sensors and one unified Sensor Dashboard for full visualization.

---

### Features

* Stream all available sensors wirelessly over Wi-Fi
* Real-time 3D orientation cube visualization (using quaternion → RPY conversion)
* Live GPS tracking with OpenStreetMap
* Battery, power, and step counter monitoring
* Simple modular Python scripts for different use cases
* Easy setup — no servers, just Wi-Fi

---

## 1. Setup (Python side)

### Step 1: Clone the repository

```bash
git clone https://github.com/<your-username>/phone-sensor-dashboard.git
cd phone-sensor-dashboard
```

### Step 2: Create a virtual environment

Windows:

```bash
python -m venv venv
venv\Scripts\activate
```

Linux/macOS:

```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install dependencies

```bash
pip install -r requirements.txt
```


---

## 2. Setup (Android side)

You do not need Android Studio. The prebuilt APK is already included in the project folder.

### Steps:

1. Copy the **PhoneSensorsStreamer.apk** file from the repository to your Android phone.
2. Install it manually (you may need to enable “Install from unknown sources” in settings).
3. Open the app on your phone.
4. Enter your laptop’s IP address (same Wi-Fi network).
5. Tap **Start Streaming** to begin sending sensor data.

The app will automatically broadcast all sensor data via UDP.

---

## 3. Python Scripts Overview

| File                      | Description                                                                                         |
| ------------------------- | --------------------------------------------------------------------------------------------------- |
| **`Sensor_Dashboard.py`** | Main dashboard — displays all available data: 3D orientation cube, GPS map, and live sensor values. |
| **`Orientation_Fast.py`** | Fast 3D visualization of phone orientation (roll, pitch, yaw) using PyQtGraph.                      |
| **`rpy_output_text.py`**  | Terminal-only version that prints roll, pitch, yaw angles in real-time.                             |
| **`GPS.py`**              | Minimal script that listens for GPS data and prints latitude, longitude, altitude, and speed.       |
| **`sensor_list.py`**      | Lists all sensors currently being streamed from the Android device.                                 |

---

## 4. Running the Project

### Option A — Run the full dashboard

This shows everything in one unified interface:

```bash
python Sensor_Dashboard.py
```

### Option B — Individual tools

```bash
python Orientation_Fast.py       # 3D orientation cube
python rpy_output_text.py        # RPY values only (no GUI)
python GPS.py                    # GPS data only
python sensor_list.py            # View available sensors
```

---

## 5. Network Setup

* Ensure both your phone and laptop are connected to the same Wi-Fi network.
* In the Android app:

  * Enter your laptop’s local IP address (shown via `ipconfig` on Windows or `ifconfig` on Linux).
  * Keep the UDP port 5005 (default) unless you change it in the Python code.

---

## 6. Requirements

Python 3.10+ recommended.

Example `requirements.txt`:

```
PyQt5
PyQtWebEngine
pyqtgraph
numpy
```

If you only want text-based tools:

```
numpy
```

---

## 7. Folder Structure

```
phone-sensor-dashboard/
├── PhoneSensorsStreamer.apk     # Prebuilt Android app
├── Sensor_Dashboard.py          # Full GUI dashboard (3D + map + data)
├── Orientation_Fast.py          # Fast orientation cube visualization
├── GPS.py                       # GPS-only listener
├── sensor_list.py               # Lists all available phone sensors
├── rpy_output_text.py           # Terminal RPY printout
├── requirements.txt             # Python dependencies
├── .gitignore
└── README.md
```

---

## 8. Troubleshooting

| Problem                      | Fix                                                                                                        |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------- |
| No data received             | Check that both devices are on the same Wi-Fi, and the correct IP is entered.                              |
| Permission denied (GPS)      | Allow location permission in the Android app.                                                              |
| Dashboard opens but is empty | Start the Android app first; the dashboard updates when UDP packets arrive.                                |
| 3D cube not moving           | Ensure the phone supports rotation vector sensors (`TYPE_ROTATION_VECTOR` or `TYPE_GAME_ROTATION_VECTOR`). |
| Qt WebEngine crash           | Reinstall PyQtWebEngine (`pip install PyQtWebEngine==5.15.7`).                                             |

---

## 9. Contributing

Feel free to fork this repo, add new visualizations (like IMU plots, step counters, or compass), and create pull requests.
Ideas:

* Add CSV recording
* Implement Kalman-filtered orientation
* Integrate BLE fallback for offline streaming

---

## 10. Credits

Created by **Tanay Shetty**
(Mechatronics Engineering | Robotics & Sensor Systems Enthusiast)
