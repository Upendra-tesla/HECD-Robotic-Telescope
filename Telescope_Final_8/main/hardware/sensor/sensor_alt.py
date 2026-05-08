#!/usr/bin/env python3
"""
sensor_alt.py - WT901BLE68 Sensor Parser (ALTITUDE) - SWAPPED FROM AZ
Stable readings with 500ms updates
Displays sensor values in original -180 to +180 format
Now using Angle X for altitude
"""

import struct
from datetime import datetime
import time
import math
from collections import deque

# Confirmed UUIDs for WT901BLE68 (matches your working code)
SERVICE_UUID = "0000ffe5-0000-1000-8000-00805f9a34fb"
DATA_CHAR_UUID = "0000ffe4-0000-1000-8000-00805f9a34fb"
COMMAND_CHAR_UUID = "0000ffe9-0000-1000-8000-00805f9a34fb"

DEVICE_PATTERNS = ["WT901", "WTSDCL", "WT901BLE", "JY901", "GY-901"]

class WT901BLE68Sensor:  # Now handles ALTITUDE
    def __init__(self):
        self.client = None
        self.is_connected = False
        self.data_buffer = bytearray()
        self.last_parsed_data = None
        
        # Stability improvements
        self.last_update_time = 0
        self.update_interval = 0.5  # 500ms between updates
        self.last_stable_angle_x = 0.0  # Store last stable altitude (Angle X)
        
        # Moving average filter
        self.acc_x_history = deque(maxlen=5)
        self.acc_y_history = deque(maxlen=5)
        self.acc_z_history = deque(maxlen=5)
        self.gyro_x_history = deque(maxlen=5)
        self.gyro_y_history = deque(maxlen=5)
        self.gyro_z_history = deque(maxlen=5)
        self.angle_x_history = deque(maxlen=5)  # Altitude (most important)
        self.angle_y_history = deque(maxlen=5)
        self.angle_z_history = deque(maxlen=5)
        self.mag_x_history = deque(maxlen=5)
        self.mag_y_history = deque(maxlen=5)
        self.mag_z_history = deque(maxlen=5)

    def moving_average(self, history, new_value):
        """Calculate moving average"""
        history.append(new_value)
        return sum(history) / len(history)

    def parse_5561_packet(self, packet):
        """
        Parse WT901BLE68 28-byte 0x5561 packet
        Returns data with angles in original -180 to +180 range
        Now using Angle X for altitude
        """
        if len(packet) != 28 or packet[0] != 0x55 or packet[1] != 0x61:
            return None
            
        try:
            # Parse raw values
            raw_acc_x = int.from_bytes(packet[2:4], byteorder='little', signed=True) / 32768.0 * 16
            raw_acc_y = int.from_bytes(packet[4:6], byteorder='little', signed=True) / 32768.0 * 16
            raw_acc_z = int.from_bytes(packet[6:8], byteorder='little', signed=True) / 32768.0 * 16
            
            raw_gyro_x = int.from_bytes(packet[8:10], byteorder='little', signed=True) / 32768.0 * 2000
            raw_gyro_y = int.from_bytes(packet[10:12], byteorder='little', signed=True) / 32768.0 * 2000
            raw_gyro_z = int.from_bytes(packet[12:14], byteorder='little', signed=True) / 32768.0 * 2000
            
            raw_angle_x = int.from_bytes(packet[14:16], byteorder='little', signed=True) / 32768.0 * 180  # Altitude
            raw_angle_y = int.from_bytes(packet[16:18], byteorder='little', signed=True) / 32768.0 * 180
            raw_angle_z = int.from_bytes(packet[18:20], byteorder='little', signed=True) / 32768.0 * 180
            
            raw_mag_x = int.from_bytes(packet[20:22], byteorder='little', signed=True)
            raw_mag_y = int.from_bytes(packet[22:24], byteorder='little', signed=True)
            raw_mag_z = int.from_bytes(packet[24:26], byteorder='little', signed=True)
            
            raw_temp = int.from_bytes(packet[26:28], byteorder='little', signed=True) / 100.0
            
            # Apply moving average for stability
            results = {
                'type': 'comprehensive',
                'acc_x': self.moving_average(self.acc_x_history, raw_acc_x),
                'acc_y': self.moving_average(self.acc_y_history, raw_acc_y),
                'acc_z': self.moving_average(self.acc_z_history, raw_acc_z),
                'gyro_x': self.moving_average(self.gyro_x_history, raw_gyro_x),
                'gyro_y': self.moving_average(self.gyro_y_history, raw_gyro_y),
                'gyro_z': self.moving_average(self.gyro_z_history, raw_gyro_z),
                # Angles in original -180 to +180 range with smoothing
                'angle_x': self.moving_average(self.angle_x_history, raw_angle_x),  # Altitude (smoothed)
                'angle_y': self.moving_average(self.angle_y_history, raw_angle_y),
                'angle_z': self.moving_average(self.angle_z_history, raw_angle_z),
                'mag_x': self.moving_average(self.mag_x_history, raw_mag_x),
                'mag_y': self.moving_average(self.mag_y_history, raw_mag_y),
                'mag_z': self.moving_average(self.mag_z_history, raw_mag_z),
                'temperature': raw_temp,
                # Include raw values for reference
                'raw_angle_x': raw_angle_x  # Raw altitude
            }
            
            # Store last valid data
            self.last_parsed_data = results
            self.last_stable_angle_x = results['angle_x']  # Store stable altitude
            return results
            
        except Exception as e:
            print(f"⚠️ Packet parse error: {e}")
            return self.last_parsed_data

    def process_ble_data(self, data):
        """
        Process raw BLE data (buffered)
        Returns parsed data with 500ms throttling for stability
        """
        current_time = time.time()
        
        # Add new data to buffer
        self.data_buffer.extend(data)
        
        # Process complete 28-byte 0x5561 packets
        while len(self.data_buffer) >= 28:
            # Find start of valid 0x5561 packet (sync byte)
            start_idx = self.data_buffer.find(b'\x55\x61')
            
            if start_idx == -1:
                # No valid packet start - clear corrupted buffer
                self.data_buffer = bytearray()
                break
                
            # Remove garbage data before packet start
            if start_idx > 0:
                self.data_buffer = self.data_buffer[start_idx:]
                
            # Extract 28-byte packet
            if len(self.data_buffer) >= 28:
                packet = self.data_buffer[:28]
                self.data_buffer = self.data_buffer[28:]
                
                # Parse packet
                parsed_data = self.parse_5561_packet(packet)
                
                # Only return data at 500ms intervals for stability
                if parsed_data and (current_time - self.last_update_time) >= self.update_interval:
                    self.last_update_time = current_time
                    return parsed_data
        
        # Return None between updates (prevents UI flickering)
        return None

    def parse_sensor_data(self, data):
        """Alias for process_ble_data (matches sensor_controller.py expected method)"""
        return self.process_ble_data(data)

    def get_stable_altitude(self):
        """Get the most recent stable altitude reading (Angle X)"""
        return self.last_stable_angle_x

    def display_data(self, data_dict):
        """Print formatted data for debugging - shows original -180 to +180 angles"""
        if not data_dict or data_dict.get('type') != 'comprehensive':
            return
            
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        angle_x = round(data_dict['angle_x'], 1)  # Altitude (most important)
        angle_y = round(data_dict['angle_y'], 1)
        angle_z = round(data_dict['angle_z'], 1)
        raw_x = round(data_dict.get('raw_angle_x', angle_x), 1)  # Raw altitude
        
        # Show sign for negative angles
        x_str = f"+{angle_x:5.1f}" if angle_x >= 0 else f"{angle_x:6.1f}"
        y_str = f"+{angle_y:5.1f}" if angle_y >= 0 else f"{angle_y:6.1f}"
        z_str = f"+{angle_z:5.1f}" if angle_z >= 0 else f"{angle_z:6.1f}"
        raw_str = f"+{raw_x:5.1f}" if raw_x >= 0 else f"{raw_x:6.1f}"
        
        # Show both smoothed and raw with altitude (X) highlighted
        print(f"[ALT-SENSOR (WT901BLE68)] [{timestamp}] Smoothed: X:{x_str}° Y:{y_str}° Z:{z_str}° | Raw X:{raw_str}°")
        
        # Also show magnetic field strength
        mag_x = int(round(data_dict.get('mag_x', 0)))
        mag_y = int(round(data_dict.get('mag_y', 0)))
        mag_z = int(round(data_dict.get('mag_z', 0)))
        print(f"[ALT-SENSOR (WT901BLE68)] [{timestamp}] Mag: X:{mag_x:+6d} Y:{mag_y:+6d} Z:{mag_z:+6d} µT")

# ------------------------------
# Test this file standalone
# ------------------------------
if __name__ == "__main__":
    import asyncio
    from bleak import BleakClient, BleakScanner

    class TestSensorConnection:
        def __init__(self):
            self.sensor = WT901BLE68Sensor()
            self.display_counter = 0

        async def notification_handler(self, sender, data):
            """Test BLE data handler - updates at 500ms intervals"""
            parsed = self.sensor.process_ble_data(data)
            if parsed:
                self.sensor.display_data(parsed)
                self.display_counter += 1

        async def search_and_connect(self):
            """Test connection"""
            print("=" * 80)
            print("WT901BLE68 Sensor Test - Stable ALTITUDE Readings (500ms updates, using Angle X)")
            print("=" * 80)
            print("🔍 Scanning for WT901BLE68 (5s)...")
            devices = await BleakScanner.discover(timeout=5.0)
            
            sensor_address = None
            sensor_name = None
            for device in devices:
                if device.name and any(pat in device.name.upper() for pat in DEVICE_PATTERNS):
                    sensor_address = device.address
                    sensor_name = device.name
                    print(f"✅ Found sensor: {device.name} ({sensor_address})")
                    break

            if not sensor_address:
                print("\n❌ No WT901BLE68 found")
                print("\n📋 Available devices:")
                for i, device in enumerate(devices, 1):
                    name = device.name or "Unknown"
                    print(f"   {i}. {name} - {device.address}")
                return

            # Connect and stream
            try:
                print(f"\n🔗 Connecting to {sensor_name}...")
                async with BleakClient(sensor_address) as client:
                    if client.is_connected:
                        print(f"✅ Connected - streaming stable altitude data (2 updates/sec, Ctrl+C to stop)...")
                        print("-" * 100)
                        print("Time        Roll(X)    Pitch(Y)   Yaw(Z)     Raw X     (all in -180° to +180°)")
                        print("-" * 100)
                        
                        # Track display rate
                        start_time = time.time()
                        
                        await client.start_notify(DATA_CHAR_UUID, self.notification_handler)
                        
                        while client.is_connected:
                            await asyncio.sleep(0.1)
                            
            except KeyboardInterrupt:
                print(f"\n\n🛑 Stopped by user - displayed {self.display_counter} updates")
                elapsed = time.time() - start_time
                print(f"📊 Update rate: {self.display_counter/elapsed:.1f} updates/sec")
            except Exception as e:
                print(f"\n❌ Connection error: {e}")

    # Run test
    try:
        asyncio.run(TestSensorConnection().search_and_connect())
    except KeyboardInterrupt:
        print("\n👋 Exiting...")
    except Exception as e:
        print(f"\n💥 Test error: {e}")