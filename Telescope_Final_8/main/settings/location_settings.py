import json
import os
import sys
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QMessageBox, QSizePolicy
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

# --------------------------
# Predefined City Coordinates (Accurate Values)
# --------------------------
CITY_COORDS = {
    "Beijing": {"lon": 116.4074, "lat": 39.9042},
    "Nanjing": {"lon": 118.7878, "lat": 32.0415},
    "Kathmandu": {"lon": 85.3240, "lat": 27.7172}
}

class LocationSettingsDialog(QDialog):
    """
    Longitude/Latitude Settings Dialog
    - Quick-access buttons for Beijing/Nanjing/Kathmandu (single row)
    - Saves values to main/settings.json (preserves existing settings)
    - Input validation (only numeric values allowed)
    - Glassy design matching main app
    - Default values: New York (lon: -74.0060, lat: 40.7128)
    Path: main/settings/location_settings.py
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Set Observation Location (Long/Lat)")
        self.setModal(True)
        self.setFixedSize(400, 250)  # Adjusted height for city buttons
        self.setWindowOpacity(0.85)  # Match main app's glassy transparency
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)  # Match main app style

        # --------------------------
        # Path Configuration (Critical for correct file access)
        # --------------------------
        # Current file path: main/settings/location_settings.py
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        # Settings.json path: main/settings.json (one level up from settings folder)
        self.settings_path = os.path.join(os.path.dirname(self.current_dir), "settings.json")

        # Default values (New York) - fallback if no saved values
        self.default_lon = -74.0060
        self.default_lat = 40.7128

        # --------------------------
        # Load Existing Settings
        # --------------------------
        self.existing_settings = self.load_existing_settings()
        self.saved_lon = self.existing_settings.get("longitude", self.default_lon)
        self.saved_lat = self.existing_settings.get("latitude", self.default_lat)

        # --------------------------
        # UI Setup
        # --------------------------
        self.setup_ui()

        # Drag functionality (match main app's borderless drag)
        self.drag_position = None

    # --------------------------
    # Drag Functionality (Borderless Window)
    # --------------------------
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.drag_position:
            self.move(event.globalPos() - self.drag_position)
            event.accept()

    # --------------------------
    # Load Existing Settings (Preserve all existing data)
    # --------------------------
    def load_existing_settings(self):
        """Load settings.json (create if missing, preserve all fields)"""
        try:
            if os.path.exists(self.settings_path):
                with open(self.settings_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            else:
                # Create default settings.json if it doesn't exist
                default_settings = {
                    "window_size": {"width": 830, "height": 570},
                    "window_ratio": "83:57",
                    "tabs": {"count": 5, "row_count": 1, "column_count": 5},
                    "longitude": self.default_lon,
                    "latitude": self.default_lat
                }
                with open(self.settings_path, "w", encoding="utf-8") as f:
                    json.dump(default_settings, f, indent=4)
                return default_settings
        except json.JSONDecodeError:
            QMessageBox.critical(self, "Error", "settings.json is corrupted! Using default values.")
            return {"longitude": self.default_lon, "latitude": self.default_lat}
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load settings: {str(e)}")
            return {"longitude": self.default_lon, "latitude": self.default_lat}

    # --------------------------
    # UI Setup (Including City Buttons in Single Row)
    # --------------------------
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(12)

        # --------------------------
        # Longitude Input
        # --------------------------
        lon_layout = QHBoxLayout()
        lon_label = QLabel("Longitude:")
        lon_label.setFont(QFont("Arial", 11, QFont.Bold))
        self.lon_input = QLineEdit(str(self.saved_lon))
        self.lon_input.setPlaceholderText("e.g., -74.0060 (New York)")
        self.lon_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lon_layout.addWidget(lon_label)
        lon_layout.addWidget(self.lon_input)
        main_layout.addLayout(lon_layout)

        # --------------------------
        # Latitude Input
        # --------------------------
        lat_layout = QHBoxLayout()
        lat_label = QLabel("Latitude:")
        lat_label.setFont(QFont("Arial", 11, QFont.Bold))
        self.lat_input = QLineEdit(str(self.saved_lat))
        self.lat_input.setPlaceholderText("e.g., 40.7128 (New York)")
        self.lat_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lat_layout.addWidget(lat_label)
        lat_layout.addWidget(self.lat_input)
        main_layout.addLayout(lat_layout)

        # --------------------------
        # NEW: City Quick-Access Buttons (Single Row)
        # --------------------------
        city_btn_layout = QHBoxLayout()
        city_btn_layout.setSpacing(8)  # Even spacing between buttons
        city_btn_layout.setAlignment(Qt.AlignCenter)  # Center the row

        # Beijing Button
        beijing_btn = QPushButton("Beijing")
        beijing_btn.setFixedSize(100, 30)
        beijing_btn.clicked.connect(lambda: self.load_city_coords("Beijing"))
        city_btn_layout.addWidget(beijing_btn)

        # Nanjing Button
        nanjing_btn = QPushButton("Nanjing")
        nanjing_btn.setFixedSize(100, 30)
        nanjing_btn.clicked.connect(lambda: self.load_city_coords("Nanjing"))
        city_btn_layout.addWidget(nanjing_btn)

        # Kathmandu Button
        kathmandu_btn = QPushButton("Kathmandu")
        kathmandu_btn.setFixedSize(100, 30)
        kathmandu_btn.clicked.connect(lambda: self.load_city_coords("Kathmandu"))
        city_btn_layout.addWidget(kathmandu_btn)

        main_layout.addLayout(city_btn_layout)

        # --------------------------
        # Save/Cancel Buttons
        # --------------------------
        btn_layout = QHBoxLayout()
        btn_layout.setAlignment(Qt.AlignRight)

        # Save Button (matches main app's button style)
        self.save_btn = QPushButton("Save")
        self.save_btn.setFixedSize(95, 30)
        self.save_btn.clicked.connect(self.save_settings)
        btn_layout.addWidget(self.save_btn)

        # Cancel Button
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedSize(95, 30)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        main_layout.addLayout(btn_layout)

        # Apply theme (match main app's dark_blue default)
        self.setStyleSheet("""
            QDialog {
                background-color: #1e293b;
                color: #f8fafc;
            }
            QLabel {
                color: #f8fafc;
                font-size: 11px;
            }
            QLineEdit {
                background-color: #0f172a;
                color: #f8fafc;
                border: 1px solid #38bdf8;
                border-radius: 6px;
                padding: 5px;
                font-size: 11px;
            }
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #38bdf8;
            }
        """)

    # --------------------------
    # NEW: Load City Coordinates to Input Fields
    # --------------------------
    def load_city_coords(self, city_name):
        """Load predefined coordinates for selected city into input fields"""
        coords = CITY_COORDS.get(city_name)
        if coords:
            self.lon_input.setText(str(coords["lon"]))
            self.lat_input.setText(str(coords["lat"]))
            # Optional: Show confirmation
            QMessageBox.information(self, "Loaded", f"Loaded coordinates for {city_name}!\nLong: {coords['lon']}\nLat: {coords['lat']}")

    # --------------------------
    # Save Settings (Validation + Preserve Existing Data)
    # --------------------------
    def save_settings(self):
        """Validate input and save to settings.json (preserve all existing fields)"""
        try:
            # Validate numeric input
            new_lon = float(self.lon_input.text().strip())
            new_lat = float(self.lat_input.text().strip())

            # Validate reasonable ranges (longitude: -180 to 180, latitude: -90 to 90)
            if not (-180 <= new_lon <= 180):
                QMessageBox.warning(self, "Invalid Input", "Longitude must be between -180 and 180!")
                return
            if not (-90 <= new_lat <= 90):
                QMessageBox.warning(self, "Invalid Input", "Latitude must be between -90 and 90!")
                return

            # Update only longitude/latitude (preserve all other settings)
            self.existing_settings["longitude"] = new_lon
            self.existing_settings["latitude"] = new_lat

            # Save back to settings.json
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(self.existing_settings, f, indent=4)

            # Success message
            QMessageBox.information(self, "Success", f"Location saved!\nLongitude: {new_lon}\nLatitude: {new_lat}")
            self.accept()  # Close dialog

        except ValueError:
            QMessageBox.critical(self, "Invalid Input", "Please enter valid numeric values (e.g., -74.0060)")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save settings: {str(e)}")

# --------------------------
# Run as Standalone App (Called by weather.py)
# --------------------------
if __name__ == "__main__":
    # Add parent directory to path (for PyQt5 compatibility)
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Match main app style
    
    # Open settings dialog
    dialog = LocationSettingsDialog()
    dialog.exec_()
    
    sys.exit(app.exec_())