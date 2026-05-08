#!/usr/bin/env python3
"""
sensor_az.py - WTSDCL Sensor Parser (AZIMUTH) - SWAPPED FROM ALT
Buffered packet handling with stability improvements and 500ms updates
Displays sensor values in original -180 to +180 format
Now using Angle Z for azimuth
"""

import struct
from datetime import datetime
import time
from collections import deque

# WTSDCL UUIDs (confirm these match your sensor!)
SERVICE_UUID = "0000ffe5-0000-1000-8000-00805f9a34fb"
DATA_CHAR_UUID = "0000ffe4-0000-1000-8000-00805f9a34fb"
COMMAND_CHAR_UUID = "0000ffe9-0000-1000-8000-00805f9a34fb"

DEVICE_PATTERNS = ["WTSDCL", "WT901", "JY901", "GY-901"]

class WTSDCLSensor:  # Now handles AZIMUTH
    def __init__(self):
        self.client = None
        self.is_connected = False
        self.data_buffer = bytearray()  # Critical: buffer for partial packets
        self.last_parsed_data = None    # Fallback for motor.py
        
        # Stability improvements
        self.last_update_time = 0
        self.update_interval = 0.5  # 500ms between updates
        self.last_stable_angle_z = 0.0  # Store last stable azimuth (Angle Z)
        
        # Moving average filter for all data types
        self.acc_x_history = deque(maxlen=5)
        self.acc_y_history = deque(maxlen=5)
        self.acc_z_history = deque(maxlen=5)
        self.gyro_x_history = deque(maxlen=5)
        self.gyro_y_history = deque(maxlen=5)
        self.gyro_z_history = deque(maxlen=5)
        self.angle_x_history = deque(maxlen=5)
        self.angle_y_history = deque(maxlen=5)
        self.angle_z_history = deque(maxlen=5)  # Azimuth (most important)
        self.mag_x_history = deque(maxlen=5)
        self.mag_y_history = deque(maxlen=5)
        self.mag_z_history = deque(maxlen=5)

    def moving_average(self, history, new_value):
        """Calculate moving average"""
        history.append(new_value)
        return sum(history) / len(history)

    def parse_wtsdcl_packet(self, packet):
        """
        Parse WTSDCL packet (28-byte 0x5561 format)
        Returns data with angles in original -180 to +180 range
        Now using Angle Z for azimuth
        """
        if len(packet) != 28 or packet[0] != 0x55 or packet[1] != 0x61:
            return None
            
        try:
            # Parse raw values (-180 to 180 range)
            raw_acc_x = int.from_bytes(packet[2:4], byteorder='little', signed=True) / 32768.0 * 16
            raw_acc_y = int.from_bytes(packet[4:6], byteorder='little', signed=True) / 32768.0 * 16
            raw_acc_z = int.from_bytes(packet[6:8], byteorder='little', signed=True) / 32768.0 * 16
            
            raw_gyro_x = int.from_bytes(packet[8:10], byteorder='little', signed=True) / 32768.0 * 2000
            raw_gyro_y = int.from_bytes(packet[10:12], byteorder='little', signed=True) / 32768.0 * 2000
            raw_gyro_z = int.from_bytes(packet[12:14], byteorder='little', signed=True) / 32768.0 * 2000
            
            raw_angle_x = int.from_bytes(packet[14:16], byteorder='little', signed=True) / 32768.0 * 180
            raw_angle_y = int.from_bytes(packet[16:18], byteorder='little', signed=True) / 32768.0 * 180
            raw_angle_z = int.from_bytes(packet[18:20], byteorder='little', signed=True) / 32768.0 * 180  # Azimuth
            
            raw_mag_x = int.from_bytes(packet[20:22], byteorder='little', signed=True)
            raw_mag_y = int.from_bytes(packet[22:24], byteorder='little', signed=True)
            raw_mag_z = int.from_bytes(packet[24:26], byteorder='little', signed=True)
            
            raw_temp = int.from_bytes(packet[26:28], byteorder='little', signed=True) / 100.0
            
            # Apply moving average for stability - KEEP ORIGINAL -180 to +180 RANGE
            results = {
                'type': 'comprehensive',
                'acc_x': self.moving_average(self.acc_x_history, raw_acc_x),
                'acc_y': self.moving_average(self.acc_y_history, raw_acc_y),
                'acc_z': self.moving_average(self.acc_z_history, raw_acc_z),
                'gyro_x': self.moving_average(self.gyro_x_history, raw_gyro_x),
                'gyro_y': self.moving_average(self.gyro_y_history, raw_gyro_y),
                'gyro_z': self.moving_average(self.gyro_z_history, raw_gyro_z),
                # Angles in original -180 to +180 range with smoothing
                'angle_x': self.moving_average(self.angle_x_history, raw_angle_x),
                'angle_y': self.moving_average(self.angle_y_history, raw_angle_y),
                'angle_z': self.moving_average(self.angle_z_history, raw_angle_z),  # Azimuth (smoothed)
                'mag_x': self.moving_average(self.mag_x_history, raw_mag_x),
                'mag_y': self.moving_average(self.mag_y_history, raw_mag_y),
                'mag_z': self.moving_average(self.mag_z_history, raw_mag_z),
                'temperature': raw_temp,
                # Store raw angles for debugging
                'raw_angle_x': raw_angle_x,
                'raw_angle_y': raw_angle_y,
                'raw_angle_z': raw_angle_z  # Raw azimuth
            }
            
            # Store last valid data
            self.last_parsed_data = results
            self.last_stable_angle_z = results['angle_z']  # Store stable azimuth
            return results
            
        except Exception as e:
            print(f"⚠️ WTSDCL parse error: {e}")
            return self.last_parsed_data

    def parse_sensor_data(self, data):
        """
        Buffered packet processing with 500ms throttling
        This is what sensor_controller.py calls
        """
        current_time = time.time()
        
        # Add new data to buffer
        self.data_buffer.extend(data)
        
        # Process complete packets
        while len(self.data_buffer) >= 28:
            # Find start of valid WTSDCL packet (0x5561 sync bytes)
            start_idx = self.data_buffer.find(b'\x55\x61')
            
            if start_idx == -1:
                self.data_buffer = bytearray()
                break
                
            if start_idx > 0:
                self.data_buffer = self.data_buffer[start_idx:]
                
            if len(self.data_buffer) >= 28:
                packet = self.data_buffer[:28]
                self.data_buffer = self.data_buffer[28:]
                
                parsed = self.parse_wtsdcl_packet(packet)
                
                # Only return data at 500ms intervals for stability
                if parsed and (current_time - self.last_update_time) >= self.update_interval:
                    self.last_update_time = current_time
                    return parsed
        
        # Return None between updates (prevents UI blanking)
        return None

    def get_stable_azimuth(self):
        """Get the most recent stable azimuth reading (Angle Z)"""
        return self.last_stable_angle_z

    # Debug helper (test standalone)
    def display_data(self, data_dict):
        """Print formatted data with 500ms updates - shows original -180 to +180 angles"""
        if not data_dict:
            return
            
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        # Get smoothed values
        angle_x = round(data_dict['angle_x'], 1)
        angle_y = round(data_dict['angle_y'], 1)
        angle_z = round(data_dict['angle_z'], 1)  # Azimuth (most important)
        
        # Get raw values for comparison
        raw_x = round(data_dict.get('raw_angle_x', angle_x), 1)
        raw_y = round(data_dict.get('raw_angle_y', angle_y), 1)
        raw_z = round(data_dict.get('raw_angle_z', angle_z), 1)  # Raw azimuth
        
        # Show sign for negative angles
        x_str = f"+{angle_x:5.1f}" if angle_x >= 0 else f"{angle_x:6.1f}"
        y_str = f"+{angle_y:5.1f}" if angle_y >= 0 else f"{angle_y:6.1f}"
        z_str = f"+{angle_z:5.1f}" if angle_z >= 0 else f"{angle_z:6.1f}"
        raw_z_str = f"+{raw_z:5.1f}" if raw_z >= 0 else f"{raw_z:6.1f}"
        
        # Show both smoothed and raw with azimuth (Z) highlighted
        print(f"[AZ-SENSOR (WTSDCL)] [{timestamp}] Smoothed: X:{x_str}° Y:{y_str}° Z:{z_str}° | Raw Z:{raw_z_str}°")
        
        # Also show magnetic field strength
        mag_x = int(round(data_dict.get('mag_x', 0)))
        mag_y = int(round(data_dict.get('mag_y', 0)))
        mag_z = int(round(data_dict.get('mag_z', 0)))
        
        # Check if values seem valid
        if abs(mag_x) > 1000 or abs(mag_y) > 1000 or abs(mag_z) > 1000:
            mag_status = "⚠️ High"
        else:
            mag_status = "✓ Normal"
            
        print(f"[AZ-SENSOR (WTSDCL)] [{timestamp}] Mag: X:{mag_x:+6d} Y:{mag_y:+6d} Z:{mag_z:+6d} µT {mag_status}")

# Test standalone (confirm WTSDCL connection)
if __name__ == "__main__":
    import asyncio
    from bleak import BleakClient, BleakScanner

    class TestWTSDCLConnection:
        def __init__(self):
            self.sensor = WTSDCLSensor()
            self.display_counter = 0
            self.start_time = time.time()

        async def notification_handler(self, sender, data):
            parsed = self.sensor.parse_sensor_data(data)
            if parsed:
                self.sensor.display_data(parsed)
                self.display_counter += 1

        async def search_and_connect(self):
            print("=" * 100)
            print("WTSDCL Sensor Test - Stable AZIMUTH Readings (500ms updates, using Angle Z)")
            print("=" * 100)
            print("🔍 Scanning for WTSDCL (5s)...")
            devices = await BleakScanner.discover(timeout=5.0)
            
            sensor_address = None
            sensor_name = None
            for device in devices:
                if device.name and any(pat in device.name.upper() for pat in DEVICE_PATTERNS):
                    sensor_address = device.address
                    sensor_name = device.name
                    print(f"✅ Found WTSDCL: {device.name} ({sensor_address})")
                    break

            if not sensor_address:
                print("\n❌ No WTSDCL found")
                print("\n📋 Available devices:")
                for i, device in enumerate(devices, 1):
                    name = device.name or "Unknown"
                    print(f"   {i}. {name} - {device.address}")
                return

            try:
                print(f"\n🔗 Connecting to {sensor_name}...")
                async with BleakClient(sensor_address, timeout=20.0) as client:
                    if client.is_connected:
                        print(f"✅ Connected - streaming stable azimuth data (2 updates/sec, Ctrl+C to stop)...")
                        print("-" * 100)
                        print("Time        Roll(X)    Pitch(Y)   Yaw(Z)    Raw Z     (all in -180° to +180°)")
                        print("-" * 100)
                        
                        await client.start_notify(DATA_CHAR_UUID, self.notification_handler)
                        
                        while client.is_connected:
                            await asyncio.sleep(0.1)
                            
            except KeyboardInterrupt:
                elapsed = time.time() - self.start_time
                print(f"\n\n🛑 Stopped by user - displayed {self.display_counter} updates")
                print(f"📊 Update rate: {self.display_counter/elapsed:.1f} updates/sec")
                print(f"📈 Target: 2.0 updates/sec (500ms interval)")
            except Exception as e:
                print(f"\n❌ Connection error: {e}")

    try:
        asyncio.run(TestWTSDCLConnection().search_and_connect())
    except KeyboardInterrupt:
        print("\n👋 Exiting...")
    except Exception as e:
        print(f"\n💥 Test error: {e}")