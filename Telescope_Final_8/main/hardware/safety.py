#!/usr/bin/env python3
"""
Safety monitoring system for telescope hardware
Monitors critical conditions and triggers emergency stops when needed
"""

import threading
import time
from typing import List, Dict, Callable, Optional, Any
from dataclasses import dataclass
from enum import Enum
from collections import deque

# Add parent directory to path
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.logging import logger


class SafetyLevel(Enum):
    """Safety severity levels"""
    NORMAL = 0
    WARNING = 1
    CRITICAL = 2
    EMERGENCY = 3


@dataclass
class SafetyCondition:
    """Represents a condition to monitor"""
    name: str
    check_func: Callable[[], bool]  # Returns True if condition is triggered
    level: SafetyLevel
    message: str
    auto_recover: bool = False
    recovery_func: Optional[Callable] = None
    cooldown: float = 5.0  # Seconds between alerts


class SafetyMonitor:
    """Monitors system safety and triggers alerts"""
    
    def __init__(self, check_interval: float = 0.1, max_history: int = 100):
        """
        Initialize safety monitor
        
        Args:
            check_interval: Seconds between condition checks
            max_history: Maximum number of events to keep in history
        """
        self.conditions: List[SafetyCondition] = []
        self.current_level = SafetyLevel.NORMAL
        self.active_alarms: Dict[str, float] = {}
        self.callbacks: Dict[SafetyLevel, List[Callable]] = {
            level: [] for level in SafetyLevel
        }
        self.event_history: deque = deque(maxlen=max_history)
        
        self._monitor_thread = None
        self._running = False
        self._lock = threading.RLock()
        self.check_interval = check_interval
    
    def add_condition(self, condition: SafetyCondition) -> None:
        """Add a safety condition to monitor"""
        with self._lock:
            self.conditions.append(condition)
            logger.info(f"Added safety condition: {condition.name}")
    
    def register_callback(self, level: SafetyLevel, callback: Callable) -> None:
        """Register callback for specific safety level"""
        self.callbacks[level].append(callback)
    
    def start(self) -> None:
        """Start monitoring thread"""
        with self._lock:
            if self._running:
                return
            self._running = True
        
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="SafetyMonitor"
        )
        self._monitor_thread.start()
        logger.info("Safety monitor started")
    
    def stop(self) -> None:
        """Stop monitoring thread"""
        with self._lock:
            self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)
        logger.info("Safety monitor stopped")
    
    def _monitor_loop(self) -> None:
        """Main monitoring loop"""
        while self._running:
            try:
                for condition in self.conditions:
                    self._check_condition(condition)
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Safety monitor error: {e}")
    
    def _check_condition(self, condition: SafetyCondition) -> None:
        """Check a single condition"""
        try:
            if condition.check_func():
                # Condition triggered
                now = time.time()
                last_alert = self.active_alarms.get(condition.name, 0)
                
                if now - last_alert > condition.cooldown:
                    self.active_alarms[condition.name] = now
                    
                    # Update current level
                    if condition.level.value > self.current_level.value:
                        self.current_level = condition.level
                    
                    # Add to history
                    self._add_to_history({
                        'time': now,
                        'name': condition.name,
                        'level': condition.level.name,
                        'message': condition.message,
                        'action': 'triggered'
                    })
                    
                    # Log and notify
                    logger.warning(f"Safety alarm: {condition.message}", 
                                  level=condition.level.name)
                    
                    # Notify callbacks
                    for callback in self.callbacks[condition.level]:
                        try:
                            callback(condition)
                        except Exception as e:
                            logger.error(f"Safety callback error: {e}")
            else:
                # Condition cleared
                if condition.name in self.active_alarms:
                    del self.active_alarms[condition.name]
                    
                    # Add to history
                    self._add_to_history({
                        'time': time.time(),
                        'name': condition.name,
                        'level': condition.level.name,
                        'message': condition.message,
                        'action': 'cleared'
                    })
                    
                    # Recalculate current level
                    self._update_current_level()
                    
                    if condition.auto_recover and condition.recovery_func:
                        try:
                            condition.recovery_func()
                            logger.info(f"Auto-recovered: {condition.name}")
                        except Exception as e:
                            logger.error(f"Recovery failed: {e}")
                            
        except Exception as e:
            logger.error(f"Condition check failed for {condition.name}: {e}")
    
    def _add_to_history(self, event: Dict[str, Any]) -> None:
        """Add event to history"""
        with self._lock:
            self.event_history.append(event)
    
    def _update_current_level(self) -> None:
        """Update current safety level based on active alarms"""
        max_level = SafetyLevel.NORMAL
        for name in self.active_alarms:
            condition = next((c for c in self.conditions if c.name == name), None)
            if condition and condition.level.value > max_level.value:
                max_level = condition.level
        self.current_level = max_level
    
    def get_status(self) -> Dict:
        """Get current safety status"""
        with self._lock:
            return {
                'level': self.current_level.name,
                'active_alarms': list(self.active_alarms.keys()),
                'monitoring': self._running,
                'conditions_count': len(self.conditions)
            }
    
    def get_history(self, limit: Optional[int] = None) -> List[Dict]:
        """Get event history"""
        with self._lock:
            history = list(self.event_history)
            if limit:
                history = history[-limit:]
            return history
    
    def clear_history(self) -> None:
        """Clear event history"""
        with self._lock:
            self.event_history.clear()
            logger.info("Safety event history cleared")


# Example factory functions for common safety conditions

def create_motor_safety_conditions(motor_az, motor_alt) -> List[SafetyCondition]:
    """Create safety conditions for motors"""
    return [
        SafetyCondition(
            name="azimuth_range",
            check_func=lambda: abs(motor_az.current_position) > 360,
            level=SafetyLevel.EMERGENCY,
            message="Azimuth outside safe range (0-360°)",
            auto_recover=False
        ),
        SafetyCondition(
            name="altitude_range",
            check_func=lambda: motor_alt.current_position < -5 or motor_alt.current_position > 95,
            level=SafetyLevel.EMERGENCY,
            message="Altitude outside safe range (-5° to 95°)",
            auto_recover=False
        ),
        SafetyCondition(
            name="sensor_timeout_az",
            check_func=lambda: (hasattr(motor_az, 'last_sensor_update') and 
                               time.time() - motor_az.last_sensor_update > 5.0),
            level=SafetyLevel.WARNING,
            message="AZ sensor data timeout",
            auto_recover=True
        ),
        SafetyCondition(
            name="sensor_timeout_alt",
            check_func=lambda: (hasattr(motor_alt, 'last_sensor_update') and 
                               time.time() - motor_alt.last_sensor_update > 5.0),
            level=SafetyLevel.WARNING,
            message="ALT sensor data timeout",
            auto_recover=True
        )
    ]


def create_power_safety_conditions(power_monitor) -> List[SafetyCondition]:
    """Create safety conditions for power monitoring"""
    return [
        SafetyCondition(
            name="low_voltage",
            check_func=lambda: power_monitor.get_voltage() < 11.0,
            level=SafetyLevel.CRITICAL,
            message="Low voltage detected (<11V)",
            auto_recover=True
        ),
        SafetyCondition(
            name="overcurrent",
            check_func=lambda: power_monitor.get_current() > 5.0,
            level=SafetyLevel.EMERGENCY,
            message="Overcurrent detected (>5A)",
            auto_recover=False
        )
    ]


def create_environment_safety_conditions(sensor) -> List[SafetyCondition]:
    """Create safety conditions for environmental monitoring"""
    return [
        SafetyCondition(
            name="high_temperature",
            check_func=lambda: sensor.get_temperature() > 50,
            level=SafetyLevel.CRITICAL,
            message="High temperature (>50°C)",
            auto_recover=True,
            cooldown=30.0
        ),
        SafetyCondition(
            name="high_humidity",
            check_func=lambda: sensor.get_humidity() > 80,
            level=SafetyLevel.WARNING,
            message="High humidity (>80%)",
            auto_recover=True,
            cooldown=60.0
        )
    ]