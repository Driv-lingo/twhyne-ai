#!/usr/bin/env python3
"""
Secure license validation with hardware binding and heartbeat monitoring.
Provides decryption seeds for encrypted models.
"""

import os
import sys
import time
import uuid
import hashlib
import platform
import threading
import requests
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Tuple, Optional, Dict

logger = logging.getLogger(__name__)

# License API endpoint
LICENSE_API = os.environ.get(
    'SNF_LICENSE_API',
    'https://web-production-5980e.up.railway.app'
)

# Grace period for offline validation (hours)
GRACE_PERIOD_HOURS = 72  # 3 days
HEARTBEAT_INTERVAL_HOURS = 6  # Re-validate every 6 hours


class HardwareFingerprint:
    """Generate unique hardware fingerprint for device binding."""
    
    @staticmethod
    def get_device_id() -> str:
        """
        Generate unique device identifier from hardware characteristics.
        This binds the license to specific hardware.
        """
        # Collect hardware identifiers
        mac_address = uuid.getnode()
        hostname = platform.node()
        system = platform.system()
        machine = platform.machine()
        processor = platform.processor()
        
        # Create composite fingerprint
        fingerprint_data = f"{mac_address}:{hostname}:{system}:{machine}:{processor}"
        
        # Hash for privacy and consistency
        device_hash = hashlib.sha256(fingerprint_data.encode()).hexdigest()
        
        # Return first 16 characters for readability
        return device_hash[:16]
    
    @staticmethod
    def get_docker_container_id() -> Optional[str]:
        """Get Docker container ID if running in Docker."""
        try:
            with open('/proc/self/cgroup', 'r') as f:
                for line in f:
                    if 'docker' in line:
                        return line.split('/')[-1].strip()[:12]
        except:
            pass
        return None


class SecureLicenseValidator:
    """
    Validates licenses with online verification, hardware binding,
    and periodic heartbeat checks.
    """
    
    def __init__(self, license_key: str):
        self.license_key = license_key
        self.device_id = HardwareFingerprint.get_device_id()
        self.container_id = HardwareFingerprint.get_docker_container_id()
        
        self.is_valid = False
        self.license_data = {}
        self.decryption_seed = None
        self.last_validation = 0
        self.heartbeat_thread = None
        
        logger.info(f"License validator initialized for device: {self.device_id}")
        if self.container_id:
            logger.info(f"Running in Docker container: {self.container_id}")
    
    def validate_online(self) -> Tuple[bool, str, Optional[str]]:
        """
        Validate license with server and get decryption seed.
        
        Returns:
            Tuple[bool, str, Optional[str]]: (valid, message, decryption_seed)
        """
        try:
            logger.info("Validating license with server...")
            
            response = requests.post(
                f"{LICENSE_API}/api/registration/validate",
                json={
                    "license_key": self.license_key,
                    "device_id": self.device_id,
                    "container_id": self.container_id,
                    "timestamp": int(time.time()),
                    "request_seed": True  # Request decryption seed
                },
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('valid'):
                    self.is_valid = True
                    self.license_data = data
                    self.decryption_seed = data.get('decryption_seed')
                    self.last_validation = time.time()
                    
                    # Log license info
                    email = data.get('email', 'Unknown')
                    expiry = data.get('expiry_date', 'Never')
                    logger.info(f"✓ License valid for {email}, expires: {expiry}")
                    
                    return True, "License validated successfully", self.decryption_seed
                else:
                    message = data.get('message', 'Invalid license key')
                    logger.error(f"License validation failed: {message}")
                    return False, message, None
            
            elif response.status_code == 401:
                return False, "License revoked or expired", None
            
            elif response.status_code == 403:
                return False, "License already in use on another device", None
            
            else:
                logger.error(f"Server returned status {response.status_code}")
                return False, "License server error", None
        
        except requests.exceptions.Timeout:
            logger.warning("License validation timed out")
            return self._offline_validation()
        
        except requests.exceptions.ConnectionError:
            logger.warning("Cannot connect to license server")
            return self._offline_validation()
        
        except Exception as e:
            logger.error(f"License validation error: {e}")
            return self._offline_validation()
    
    def _offline_validation(self) -> Tuple[bool, str, Optional[str]]:
        """
        Offline validation using cached license data.
        Only works within grace period.
        """
        if not self.license_data:
            return False, "Cannot validate license offline (no cached data)", None
        
        # Check grace period
        hours_since_last_check = (time.time() - self.last_validation) / 3600
        
        if hours_since_last_check > GRACE_PERIOD_HOURS:
            return False, f"License validation expired (offline > {GRACE_PERIOD_HOURS}h)", None
        
        # Check expiry date
        expiry = self.license_data.get('expiry_date')
        if expiry:
            expiry_date = datetime.fromisoformat(expiry)
            if expiry_date < datetime.now():
                return False, "License expired", None
        
        hours_remaining = GRACE_PERIOD_HOURS - hours_since_last_check
        logger.info(f"✓ License validated offline ({hours_remaining:.1f}h grace remaining)")
        
        return True, "License validated (offline mode)", self.decryption_seed
    
    def start_heartbeat(self):
        """
        Start periodic license validation in background.
        Re-validates every HEARTBEAT_INTERVAL_HOURS.
        """
        def heartbeat_worker():
            while True:
                time.sleep(HEARTBEAT_INTERVAL_HOURS * 3600)
                
                logger.info("Running license heartbeat check...")
                valid, message, _ = self.validate_online()
                
                if not valid:
                    logger.critical(f"License heartbeat failed: {message}")
                    logger.critical("Shutting down due to license failure")
                    os._exit(1)  # Force exit
        
        self.heartbeat_thread = threading.Thread(
            target=heartbeat_worker,
            daemon=True,
            name="LicenseHeartbeat"
        )
        self.heartbeat_thread.start()
        logger.info(f"License heartbeat started (interval: {HEARTBEAT_INTERVAL_HOURS}h)")
    
    def validate_device_binding(self) -> bool:
        """Verify license is bound to this device."""
        if not self.license_data:
            return False
        
        bound_device = self.license_data.get('device_id')
        if not bound_device:
            return True  # No binding required
        
        if bound_device != self.device_id:
            logger.error(f"Device mismatch: {self.device_id} != {bound_device}")
            return False
        
        return True


def verify_code_integrity() -> bool:
    """
    Verify critical security code hasn't been tampered with.
    This is a basic integrity check.
    """
    try:
        import inspect
        
        # Check if key security functions exist and have expected structure
        critical_functions = [
            SecureLicenseValidator.validate_online,
            HardwareFingerprint.get_device_id,
        ]
        
        for func in critical_functions:
            source = inspect.getsource(func)
            
            # Check for suspicious modifications
            if 'return True' in source and 'def validate_online' in source:
                # Someone may have hardcoded return True
                if source.count('return True') > 2:
                    logger.critical("Security: Code tampering detected!")
                    return False
        
        return True
    
    except Exception as e:
        logger.error(f"Code integrity check failed: {e}")
        return False


class SecureStartupValidator:
    """
    Complete startup validation:
    1. Code integrity check
    2. License validation
    3. Device binding check
    4. Model decryption
    5. Heartbeat start
    """
    
    def __init__(self):
        self.license_key = os.environ.get('SNF_LICENSE_KEY')
        self.validator = None
        
    def validate_and_start(self) -> Tuple[bool, str, Optional[str]]:
        """
        Run complete validation sequence.
        
        Returns:
            Tuple[bool, str, Optional[str]]: (success, message, decryption_seed)
        """
        # Step 1: Check license key provided
        if not self.license_key:
            return False, "SNF_LICENSE_KEY environment variable not set", None
        
        # Step 2: Code integrity check
        logger.info("Checking code integrity...")
        if not verify_code_integrity():
            return False, "Security: Code integrity check failed", None
        
        # Step 3: Online license validation
        logger.info("Validating license...")
        self.validator = SecureLicenseValidator(self.license_key)
        valid, message, seed = self.validator.validate_online()
        
        if not valid:
            return False, message, None
        
        # Step 4: Device binding check
        logger.info("Checking device binding...")
        if not self.validator.validate_device_binding():
            return False, "License not valid for this device", None
        
        # Step 5: Start heartbeat monitoring
        logger.info("Starting license heartbeat...")
        self.validator.start_heartbeat()
        
        logger.info("✓ All security checks passed")
        return True, "Validation successful", seed


if __name__ == '__main__':
    # Test validation
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("=" * 60)
    print("SNF-AI Secure License Validator Test")
    print("=" * 60)
    
    startup = SecureStartupValidator()
    success, message, seed = startup.validate_and_start()
    
    if success:
        print(f"\n✓ Validation successful!")
        print(f"  Message: {message}")
        print(f"  Decryption seed: {seed[:8]}..." if seed else "  No seed")
        print(f"  Device ID: {HardwareFingerprint.get_device_id()}")
    else:
        print(f"\n✗ Validation failed: {message}")
        sys.exit(1)
