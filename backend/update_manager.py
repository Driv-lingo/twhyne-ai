#!/usr/bin/env python3
"""
Update manager for checking and notifying about available updates.
Supports version checking against a remote manifest and self-update notifications.
"""

import os
import json
import time
import threading
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Current application version
CURRENT_VERSION = os.environ.get('APP_VERSION', '1.0.0')

# Remote update check endpoint
UPDATE_API = os.environ.get(
    'UPDATE_API_URL',
    os.environ.get('LICENSE_API_URL', '')
)

# How often to check for updates (seconds)
UPDATE_CHECK_INTERVAL = 86400  # 24 hours

# Local update state file
UPDATE_STATE_DIR = Path(os.environ.get('DATA_DIR', '/app/data'))
UPDATE_STATE_FILE = UPDATE_STATE_DIR / 'update_state.json'


class UpdateManager:
    """Manages version checking and update notifications."""

    def __init__(self):
        self._lock = threading.Lock()
        self._current_version = CURRENT_VERSION
        self._latest_version = None
        self._update_available = False
        self._update_notes = ''
        self._update_url = ''
        self._last_check = None
        self._check_thread = None
        self._running = False

        # Load persisted state
        self._load_state()

    def _load_state(self):
        """Load persisted update state."""
        try:
            UPDATE_STATE_DIR.mkdir(parents=True, exist_ok=True)
            if UPDATE_STATE_FILE.exists():
                with open(UPDATE_STATE_FILE, 'r') as f:
                    state = json.load(f)
                self._latest_version = state.get('latest_version')
                self._update_available = state.get('update_available', False)
                self._update_notes = state.get('update_notes', '')
                self._update_url = state.get('update_url', '')
                self._last_check = state.get('last_check')
        except Exception as e:
            logger.warning(f"Could not load update state: {e}")

    def _save_state(self):
        """Persist update state to disk."""
        try:
            UPDATE_STATE_DIR.mkdir(parents=True, exist_ok=True)
            state = {
                'current_version': self._current_version,
                'latest_version': self._latest_version,
                'update_available': self._update_available,
                'update_notes': self._update_notes,
                'update_url': self._update_url,
                'last_check': self._last_check,
            }
            with open(UPDATE_STATE_FILE, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save update state: {e}")

    def start(self):
        """Start background update check thread."""
        if self._running:
            return
        self._running = True

        if UPDATE_API:
            self._check_thread = threading.Thread(
                target=self._check_loop, daemon=True, name="UpdateChecker"
            )
            self._check_thread.start()
            logger.info(f"Update checker started (interval: {UPDATE_CHECK_INTERVAL}s)")

    def check_for_updates(self) -> Dict:
        """
        Check for available updates.
        Returns update status dictionary.
        """
        result = {
            'current_version': self._current_version,
            'latest_version': self._latest_version,
            'update_available': False,
            'update_notes': '',
            'update_url': '',
            'last_check': self._last_check,
        }

        if not UPDATE_API:
            result['message'] = 'Update checking not configured'
            return result

        try:
            import requests
            response = requests.get(
                f"{UPDATE_API}/api/updates/check",
                params={'current_version': self._current_version},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                with self._lock:
                    self._latest_version = data.get('latest_version', self._current_version)
                    self._update_available = data.get('update_available', False)
                    self._update_notes = data.get('release_notes', '')
                    self._update_url = data.get('update_url', '')
                    self._last_check = datetime.now().isoformat()

                result.update({
                    'latest_version': self._latest_version,
                    'update_available': self._update_available,
                    'update_notes': self._update_notes,
                    'update_url': self._update_url,
                    'last_check': self._last_check,
                })

                self._save_state()
                logger.info(f"Update check complete: current={self._current_version}, "
                            f"latest={self._latest_version}")
            else:
                result['message'] = f'Update server returned status {response.status_code}'

        except Exception as e:
            logger.debug(f"Update check failed: {e}")
            result['message'] = 'Could not reach update server'
            # Return cached state
            result.update({
                'latest_version': self._latest_version,
                'update_available': self._update_available,
                'last_check': self._last_check,
            })

        return result

    def get_status(self) -> Dict:
        """Get current update status without making a remote call."""
        return {
            'current_version': self._current_version,
            'latest_version': self._latest_version,
            'update_available': self._update_available,
            'update_notes': self._update_notes,
            'update_url': self._update_url,
            'last_check': self._last_check,
        }

    def _check_loop(self):
        """Periodically check for updates."""
        # Initial check after a short delay
        time.sleep(30)
        self.check_for_updates()

        while self._running:
            time.sleep(UPDATE_CHECK_INTERVAL)
            self.check_for_updates()


# Singleton instance
_manager: Optional[UpdateManager] = None


def get_update_manager() -> UpdateManager:
    """Get or create the singleton update manager."""
    global _manager
    if _manager is None:
        _manager = UpdateManager()
    return _manager
