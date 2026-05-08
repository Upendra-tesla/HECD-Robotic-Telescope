#!/usr/bin/env python3
"""
Unified Sensor Controller (DUAL SENSOR SUPPORT - SWAPPED)
WT901BLE68 (ALT) + WTSDCL (AZ) - Fixed for concurrent BLE connections
- Added connection verification
- Added delays between connections
- Added service discovery validation
- UPDATED: Using ConfigManager and Logger
"""

import asyncio
import threading
import sys
import os
import time
from collections import deque
from typing import Dict, Optional, Callable
from dataclasses import dataclass
from PyQt5.QtCore import QObject, pyqtSignal
from bleak import BleakClient, BleakError, BleakScanner

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import utilities
from hardware.config_manager import config
from utils.logging import logger

# Import sensor parsers
try:
    from sensor.sensor_az import WTSDCLSensor  # WTSDCL is now azimuth
    logger.info("Successfully imported WTSDCLSensor (now AZIMUTH)")
except ImportError as e:
    logger.error(f"Could not import WTSDCLSensor: {e}")
    # Define mock class
    class WTSDCLSensor:
        def __init__(self):
            logger.debug("[MOCK] WTSDCLSensor created (azimuth)")
        def parse_sensor_data(self, data):
            return None

try:
    from sensor.sensor_alt import WT901BLE68Sensor  # WT901BLE68 is now altitude
    logger.info("Successfully imported WT901BLE68Sensor (now ALTITUDE)")
except ImportError as e:
    logger.error(f"Could not import WT901BLE68Sensor: {e}")
    class WT901BLE68Sensor:
        def __init__(self):
            logger.debug("[MOCK] WT901BLE68Sensor created (altitude)")
        def process_ble_data(self, data):
            return None


# --------------------------
# DUAL SENSOR CONFIG - VERIFIED MACS
# --------------------------
# IMPORTANT: Verify these MAC addresses are correct!
# Run the diagnostic function to confirm which MAC belongs to which sensor
SENSOR_CONFIG = {
    "alt": {  # WT901BLE68 now handles altitude
        "mac": "D5:54:BF:32:D1:B0",  # Verify this is actually the WT901BLE68
        "data_uuid": "0000ffe4-0000-1000-8000-00805f9a34fb",
        "service_uuid": "0000ffe5-0000-1000-8000-00805f9a34fb",
        "timeout": 20.0,
        "expected_name": "WT901BLE68"  # Adjust based on actual device name
    },
    "az": {   # WTSDCL now handles azimuth 
        "mac": "FD:D7:B0:A2:6B:3F",  # Verify this is actually the WTSDCL
        "data_uuid": "0000ffe4-0000-1000-8000-00805f9a34fb",
        "service_uuid": "0000ffe5-0000-1000-8000-00805f9a34fb",
        "timeout": 20.0,
        "expected_name": "WTSDCL"  # Adjust based on actual device name
    }
}


@dataclass
class SensorReading:
    """Immutable sensor reading for thread safety"""
    timestamp: float
    sensor_index: int
    angles: tuple  # (x, y, z)
    mag: tuple     # (x, y, z)
    sensor_type: str


class ThreadSafeSensorBuffer:
    """Thread-safe buffer for sensor readings"""
    
    def __init__(self, max_size: int = 100):
        self._lock = threading.RLock()
        self._buffer = deque(maxlen=max_size)
        self._latest: Optional[SensorReading] = None
        self._callbacks: Dict[str, Callable] = {}
        
    def add(self, reading: SensorReading) -> None:
        """Add reading - thread safe"""
        with self._lock:
            self._buffer.append(reading)
            self._latest = reading
            self._notify(reading)
    
    def get_latest(self) -> Optional[SensorReading]:
        """Get latest reading - thread safe"""
        with self._lock:
            return self._latest
    
    def get_all(self) -> list:
        """Get all readings - thread safe"""
        with self._lock:
            return list(self._buffer)
    
    def register_callback(self, name: str, callback: Callable) -> None:
        """Register callback for new readings"""
        with self._lock:
            self._callbacks[name] = callback
    
    def _notify(self, reading: SensorReading) -> None:
        """Notify all callbacks"""
        for callback in self._callbacks.values():
            try:
                callback(reading)
            except Exception as e:
                logger.error(f"Callback error: {e}")


class ConnectionManager:
    """Manages BLE connections with auto-reconnect"""
    
    def __init__(self, max_retries: int = 5, retry_delay: float = 2.0):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.connection_status: Dict[str, dict] = {}
        self.reconnect_tasks: Dict[str, asyncio.Task] = {}
        self._lock = threading.RLock()
        
    async def connect_with_retry(self, sensor_id: str, connect_func, 
                                  on_success=None, on_failure=None):
        """Connect with exponential backoff retry"""
        retries = 0
        base_delay = self.retry_delay
        
        while retries < self.max_retries:
            try:
                logger.info(f"Connecting {sensor_id} (attempt {retries + 1}/{self.max_retries})...")
                result = await connect_func()
                
                if result:
                    logger.info(f"✅ {sensor_id} connected successfully")
                    with self._lock:
                        self.connection_status[sensor_id] = {
                            'connected': True,
                            'last_connect': time.time(),
                            'retries': retries
                        }
                    if on_success:
                        await on_success()
                    return True
                    
            except asyncio.CancelledError:
                logger.info(f"Connection cancelled for {sensor_id}")
                raise
            except Exception as e:
                logger.warning(f"Connection attempt {retries + 1} failed: {e}")
            
            # Exponential backoff
            retries += 1
            delay = base_delay * (2 ** (retries - 1))
            logger.debug(f"Waiting {delay:.1f}s before retry...")
            await asyncio.sleep(delay)
        
        logger.error(f"Failed to connect {sensor_id} after {self.max_retries} attempts")
        with self._lock:
            self.connection_status[sensor_id] = {
                'connected': False,
                'last_attempt': time.time(),
                'retries': retries
            }
        if on_failure:
            await on_failure()
        return False
    
    async def monitor_connection(self, sensor_id: str, client, 
                                  check_interval: float = 1.0):
        """Monitor connection and trigger reconnect if needed"""
        while True:
            try:
                if client and hasattr(client, 'is_connected') and client.is_connected:
                    await asyncio.sleep(check_interval)
                    continue
                
                # Connection lost - trigger reconnect
                logger.warning(f"{sensor_id} connection lost - reconnecting...")
                # Signal to main loop to reconnect
                return False
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor error: {e}")
            await asyncio.sleep(check_interval)
        
        return True
    
    def get_status(self, sensor_id: str) -> dict:
        """Get connection status for a sensor"""
        with self._lock:
            return self.connection_status.get(sensor_id, {
                'connected': False,
                'last_connect': 0,
                'retries': 0
            })


class UnifiedSensorController(QObject):
    connection_status = pyqtSignal(int, bool, str)  # (index, connected, type)
    sensor_data = pyqtSignal(int, dict)             # (index, parsed_data)
    error_msg = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        logger.info("Initializing UnifiedSensorController (SWAPPED)...")
        
        # Initialize sensor parsers
        self.sensor_alt = WT901BLE68Sensor()  # Now handles altitude (was azimuth)
        self.sensor_az = WTSDCLSensor()       # Now handles azimuth (was altitude)
        
        # Thread-safe buffer
        self.buffer = ThreadSafeSensorBuffer(max_size=100)
        
        # Connection state tracking
        self.running = False
        self.alt_connected = False  # WT901BLE68
        self.az_connected = False   # WTSDCL
        
        # BLE client instances
        self.alt_client = None
        self.az_client = None

        # Connection manager for auto-reconnect
        self.conn_manager = ConnectionManager(max_retries=5, retry_delay=2.0)

        # Single loop for both sensors
        self.loop = None
        self.thread = None
        
        # Stop event
        self.stop_event = threading.Event()
        
        # Debug counters
        self.alt_data_count = 0
        self.az_data_count = 0
        self.last_debug_time = time.time()
        
        # Health check
        self.last_alt_update = 0
        self.last_az_update = 0
        
        # Register callbacks
        self.buffer.register_callback('main', self._on_buffer_update)

    def _on_buffer_update(self, reading: SensorReading):
        """Handle new reading from buffer"""
        # Emit signals based on sensor index
        if reading.sensor_index == 0:
            self.last_az_update = reading.timestamp
        elif reading.sensor_index == 1:
            self.last_alt_update = reading.timestamp

    async def diagnose_sensors(self):
        """Diagnose each sensor separately - run this first to verify MACs"""
        logger.info("=" * 60)
        logger.info("SENSOR DIAGNOSTIC - Verifying MAC addresses")
        logger.info("=" * 60)
        
        for name, config in SENSOR_CONFIG.items():
            logger.info(f"\nTesting {name.upper()} sensor at {config['mac']}...")
            
            # First try to discover the device
            devices = await BleakScanner.discover(timeout=3.0)
            found = False
            for device in devices:
                if device.address == config['mac']:
                    found = True
                    logger.info(f"✅ Found device: {device.name} ({device.address})")
                    logger.info(f"   RSSI: {device.rssi}")
                    logger.info(f"   Details: {device.details}")
                    break
            
            if not found:
                logger.error(f"❌ Device {config['mac']} not found in scan")
                continue
            
            # Try to connect and verify services
            client = BleakClient(config["mac"], timeout=10.0)
            try:
                logger.info(f"   Attempting connection...")
                if await client.connect():
                    logger.info(f"   ✅ Connected successfully")
                    
                    # Get services
                    services = client.services
                    logger.info(f"   Services found: {len(services)}")
                    
                    # Check for expected service
                    expected_service = config["service_uuid"]
                    service_found = False
                    for service in services:
                        logger.info(f"     Service: {service.uuid}")
                        if service.uuid.lower() == expected_service.lower():
                            service_found = True
                            
                        # List characteristics
                        for char in service.characteristics:
                            if char.uuid.lower() == config["data_uuid"].lower():
                                logger.info(f"       ✅ Data char found: {char.uuid}")
                    
                    if service_found:
                        logger.info(f"   ✅ Expected service found")
                    else:
                        logger.warning(f"   ⚠️ Expected service {expected_service} not found")
                    
                    await client.disconnect()
                    logger.info(f"   Disconnected")
                else:
                    logger.error(f"   ❌ Failed to connect")
                    
            except Exception as e:
                logger.error(f"   ❌ Connection error: {e}")
            
            # Delay between tests
            await asyncio.sleep(2)
        
        logger.info("=" * 60)
        logger.info("Diagnostic complete. Verify MAC addresses match expected sensors.")
        logger.info("If MACs are swapped, update SENSOR_CONFIG in sensor_controller.py")
        logger.info("=" * 60)

    def start(self, run_diagnostic_first=False):
        """Start sensor connections (sequential)"""
        self.running = True
        self.stop_event.clear()
        
        logger.info("Starting sensor connections...")
        
        # Start single thread for both sensors
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(
            target=self._run_loop, 
            daemon=True, 
            name="Sensor-Thread"
        )
        self.thread.start()
        
        # Optionally run diagnostic
        if run_diagnostic_first:
            # Schedule diagnostic to run after loop starts
            asyncio.run_coroutine_threadsafe(
                self.diagnose_sensors(), 
                self.loop
            )
        
    def _run_loop(self):
        """Run the main sensor loop"""
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._sensor_loop())
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Sensor loop error: {e}")
        finally:
            # Clean up
            try:
                pending = asyncio.all_tasks(self.loop)
                for task in pending:
                    task.cancel()
                if pending:
                    self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            except:
                pass
            finally:
                try:
                    self.loop.close()
                except:
                    pass

    def stop(self):
        """Stop all sensor connections"""
        logger.info("Stopping sensors...")
        self.running = False
        self.stop_event.set()

        if self.loop and self.loop.is_running():
            try:
                # Schedule cleanup
                future = asyncio.run_coroutine_threadsafe(
                    self._cleanup_clients(), 
                    self.loop
                )
                future.result(timeout=3.0)
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
            finally:
                try:
                    self.loop.call_soon_threadsafe(self.loop.stop)
                except:
                    pass

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=3)
        
        logger.info(f"Sensors stopped - ALT: {self.alt_data_count} updates, AZ: {self.az_data_count} updates")

    async def _cleanup_clients(self):
        """Cleanup all sensor clients"""
        # Cleanup ALT (WT901BLE68)
        if self.alt_client and self.alt_client.is_connected:
            try:
                await self.alt_client.stop_notify(SENSOR_CONFIG["alt"]["data_uuid"])
                await self.alt_client.disconnect()
                logger.debug("ALT client disconnected")
            except Exception as e:
                logger.error(f"ALT disconnect error: {e}")
        self.alt_client = None
        
        # Cleanup AZ (WTSDCL)
        if self.az_client and self.az_client.is_connected:
            try:
                await self.az_client.stop_notify(SENSOR_CONFIG["az"]["data_uuid"])
                await self.az_client.disconnect()
                logger.debug("AZ client disconnected")
            except Exception as e:
                logger.error(f"AZ disconnect error: {e}")
        self.az_client = None
    
    async def _verify_sensor_services(self, client, config, sensor_name):
        """Verify sensor has expected services"""
        try:
            services = client.services
            if not services:
                logger.error(f"{sensor_name}: No services found")
                return False
            
            # Check for service UUID
            service_found = False
            data_char_found = False
            
            for service in services:
                if service.uuid.lower() == config["service_uuid"].lower():
                    service_found = True
                    logger.debug(f"{sensor_name}: Found service {service.uuid}")
                
                # Check characteristics
                for char in service.characteristics:
                    if char.uuid.lower() == config["data_uuid"].lower():
                        data_char_found = True
                        logger.debug(f"{sensor_name}: Found data char {char.uuid}")
            
            if not service_found:
                logger.warning(f"{sensor_name}: Expected service {config['service_uuid']} not found")
                # List available services
                logger.debug(f"{sensor_name} available services:")
                for service in services:
                    logger.debug(f"  - {service.uuid}")
            
            return data_char_found
            
        except Exception as e:
            logger.error(f"{sensor_name}: Service verification error: {e}")
            return False
    
    async def _connect_alt_sensor(self, config):
        """Connect ALT sensor with verification"""
        logger.info(f"Attempting to connect to ALT sensor: {config['mac']}")
        
        try:
            self.alt_client = BleakClient(
                config["mac"],
                timeout=config["timeout"],
                disconnected_callback=self._alt_disconnected
            )
            
            if await self.alt_client.connect():
                logger.info(f"ALT: Physical connection established")
                
                # Wait for services to be discovered
                await asyncio.sleep(0.5)
                
                # Verify services
                if not await self._verify_sensor_services(self.alt_client, config, "ALT"):
                    logger.error(f"ALT: Service verification failed - wrong device?")
                    await self.alt_client.disconnect()
                    return False
                
                # Set up notification handler
                async def alt_handler(sender, data):
                    parsed = self.sensor_alt.process_ble_data(data)
                    if parsed:
                        self.alt_data_count += 1
                        current_time = time.time()
                        
                        # Create reading
                        reading = SensorReading(
                            timestamp=current_time,
                            sensor_index=1,
                            angles=(
                                round(parsed["angle_x"], 1),
                                round(parsed["angle_y"], 1),
                                round(parsed["angle_z"], 1)
                            ),
                            mag=(
                                parsed["mag_x"],
                                parsed["mag_y"],
                                parsed["mag_z"]
                            ),
                            sensor_type="altitude"
                        )
                        
                        # Add to buffer
                        self.buffer.add(reading)
                        
                        # Emit signal
                        motor_data = {
                            "angle": list(reading.angles),
                            "mag": list(reading.mag)
                        }
                        self.sensor_data.emit(1, motor_data)
                        
                        # Log sensor data periodically
                        if self.alt_data_count % 10 == 0:
                            logger.sensor_data("altitude", motor_data)
                
                await self.alt_client.start_notify(config["data_uuid"], alt_handler)
                logger.info("ALT sensor (WT901BLE68) fully operational")
                return True
            else:
                logger.error(f"ALT: Failed to establish connection")
                return False
                
        except Exception as e:
            logger.error(f"ALT connection error: {e}")
            return False
    
    async def _connect_az_sensor(self, config):
        """Connect AZ sensor with verification"""
        logger.info(f"Attempting to connect to AZ sensor: {config['mac']}")
        
        try:
            self.az_client = BleakClient(
                config["mac"],
                timeout=config["timeout"],
                disconnected_callback=self._az_disconnected
            )
            
            if await self.az_client.connect():
                logger.info(f"AZ: Physical connection established")
                
                # Wait for services to be discovered
                await asyncio.sleep(0.5)
                
                # Verify services
                if not await self._verify_sensor_services(self.az_client, config, "AZ"):
                    logger.error(f"AZ: Service verification failed - wrong device?")
                    await self.az_client.disconnect()
                    return False
                
                # Set up notification handler
                async def az_handler(sender, data):
                    parsed = self.sensor_az.parse_sensor_data(data)
                    if parsed:
                        self.az_data_count += 1
                        current_time = time.time()
                        
                        # Create reading
                        reading = SensorReading(
                            timestamp=current_time,
                            sensor_index=0,
                            angles=(
                                round(parsed.get("angle_x", 0), 1),
                                round(parsed.get("angle_y", 0), 1),
                                round(parsed.get("angle_z", 0), 1)
                            ),
                            mag=(
                                parsed.get("mag_x", 0),
                                parsed.get("mag_y", 0),
                                parsed.get("mag_z", 0)
                            ),
                            sensor_type="azimuth"
                        )
                        
                        # Add to buffer
                        self.buffer.add(reading)
                        
                        # Emit signal
                        motor_data = {
                            "angle": list(reading.angles),
                            "mag": list(reading.mag)
                        }
                        self.sensor_data.emit(0, motor_data)
                        
                        # Log sensor data periodically
                        if self.az_data_count % 10 == 0:
                            logger.sensor_data("azimuth", motor_data)
                
                await self.az_client.start_notify(config["data_uuid"], az_handler)
                logger.info("AZ sensor (WTSDCL) fully operational")
                return True
            else:
                logger.error(f"AZ: Failed to establish connection")
                return False
                
        except Exception as e:
            logger.error(f"AZ connection error: {e}")
            return False

    async def _sensor_loop(self):
        """Main sensor loop with auto-reconnect"""
        alt_config = SENSOR_CONFIG["alt"]
        az_config = SENSOR_CONFIG["az"]
        
        logger.info("Starting ALT sensor connection (WT901BLE68)...")
        
        while self.running and not self.stop_event.is_set():
            try:
                # --------------------------
                # STEP 1: Connect ALT Sensor
                # --------------------------
                if not self.alt_connected:
                    success = await self.conn_manager.connect_with_retry(
                        "alt",
                        lambda: self._connect_alt_sensor(alt_config),
                        on_success=lambda: self._on_alt_connected(),
                        on_failure=lambda: logger.error("ALT sensor connection failed")
                    )
                    
                    if not success:
                        logger.warning("ALT connection failed, retrying in 5s...")
                        await asyncio.sleep(5)
                        continue
                    
                    # CRITICAL: Give BLE stack time to stabilize after first connection
                    logger.info("ALT connected. Waiting 3 seconds for BLE stack to stabilize...")
                    await asyncio.sleep(3)
                
                # --------------------------
                # STEP 2: Connect AZ Sensor
                # --------------------------
                if self.alt_connected and not self.az_connected:
                    logger.info("Now connecting AZ sensor (WTSDCL)...")
                    
                    success = await self.conn_manager.connect_with_retry(
                        "az",
                        lambda: self._connect_az_sensor(az_config),
                        on_success=lambda: self._on_az_connected(),
                        on_failure=lambda: logger.error("AZ sensor connection failed")
                    )
                    
                    if not success:
                        logger.warning("AZ connection failed, will retry...")
                        # Don't disconnect ALT, just retry AZ
                        await asyncio.sleep(2)
                        continue
                
                # --------------------------
                # Keep both connections alive
                # --------------------------
                while (self.running and not self.stop_event.is_set() 
                       and self.alt_connected and self.az_connected):
                    
                    # Health check
                    current_time = time.time()
                    
                    if current_time - self.last_alt_update > 5.0:
                        logger.warning("ALT sensor heartbeat timeout")
                        self.alt_connected = False
                        break
                    
                    if current_time - self.last_az_update > 5.0:
                        logger.warning("AZ sensor heartbeat timeout")
                        self.az_connected = False
                        break
                    
                    await asyncio.sleep(0.1)
                
                # If we get here, one of the sensors disconnected
                if not self.alt_connected and not self.az_connected:
                    logger.info("Both sensors disconnected, restarting connection process...")
                elif not self.alt_connected:
                    logger.info("ALT disconnected, will reconnect...")
                elif not self.az_connected:
                    logger.info("AZ disconnected, will reconnect...")
                
                # Clean up disconnected clients
                if not self.alt_connected and self.alt_client:
                    try:
                        await self.alt_client.disconnect()
                    except:
                        pass
                    self.alt_client = None
                
                if not self.az_connected and self.az_client:
                    try:
                        await self.az_client.disconnect()
                    except:
                        pass
                    self.az_client = None
                
                # Brief pause before reconnection attempts
                await asyncio.sleep(2)
                        
            except asyncio.CancelledError:
                break
            except BleakError as e:
                logger.error(f"BLE Error: {e}")
                await asyncio.sleep(3)
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                await asyncio.sleep(3)

    def _on_alt_connected(self):
        """Handle ALT connection success"""
        self.alt_connected = True
        self.connection_status.emit(1, True, "altitude")
        self.error_msg.emit(f"✅ Sensor-Alt (WT901BLE68) connected")
        logger.info("ALT sensor connected successfully")
    
    def _on_az_connected(self):
        """Handle AZ connection success"""
        self.az_connected = True
        self.connection_status.emit(0, True, "azimuth")
        self.error_msg.emit(f"✅ Sensor-Az (WTSDCL) connected")
        logger.info("AZ sensor connected successfully")
        logger.info("🎉 Both sensors connected successfully!")

    def _alt_disconnected(self, client):
        """Handle ALT disconnection"""
        self.alt_connected = False
        self.connection_status.emit(1, False, "altitude")
        logger.warning("Sensor-Alt (WT901BLE68) disconnected")

    def _az_disconnected(self, client):
        """Handle AZ disconnection"""
        self.az_connected = False
        self.connection_status.emit(0, False, "azimuth")
        logger.warning("Sensor-Az (WTSDCL) disconnected")
    
    def get_latest_reading(self, sensor_index: int) -> Optional[SensorReading]:
        """Get latest reading for a sensor"""
        latest = self.buffer.get_latest()
        if latest and latest.sensor_index == sensor_index:
            return latest
        return None
    
    def get_stats(self, window_seconds: float = 10.0) -> Dict:
        """Get statistics from sensor buffer"""
        readings = self.buffer.get_all()
        current_time = time.time()
        
        recent = [r for r in readings 
                 if current_time - r.timestamp <= window_seconds]
        
        if not recent:
            return {}
        
        # Group by sensor
        stats = {}
        for sensor_idx in [0, 1]:
            sensor_readings = [r for r in recent if r.sensor_index == sensor_idx]
            if sensor_readings:
                stats[f'sensor_{sensor_idx}'] = {
                    'count': len(sensor_readings),
                    'rate': len(sensor_readings) / window_seconds,
                    'last_update': max(r.timestamp for r in sensor_readings)
                }
        
        return stats