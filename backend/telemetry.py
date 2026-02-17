#!/usr/bin/env python3
"""
Anonymous telemetry module for KPI tracking.
Collects aggregate system metrics WITHOUT individual user data/PII.
All metrics are anonymized and only track system-level performance.
"""

import os
import json
import time
import threading
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Telemetry data directory
TELEMETRY_DIR = Path(os.environ.get('TELEMETRY_DIR', '/app/data/telemetry'))

# Remote telemetry endpoint (license API server)
TELEMETRY_API = os.environ.get(
    'TELEMETRY_API_URL',
    os.environ.get('LICENSE_API_URL', '')
)

# How often to flush metrics to disk (seconds)
FLUSH_INTERVAL = 300  # 5 minutes

# How often to send telemetry to remote server (seconds)
REPORT_INTERVAL = 3600  # 1 hour


class TelemetryCollector:
    """
    Collects anonymous, aggregate system metrics.
    No individual user data, queries, or PII is stored.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._start_time = time.time()
        self._metrics = self._default_metrics()
        self._flush_thread = None
        self._report_thread = None
        self._running = False

        # Ensure telemetry directory exists
        TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)

        # Load persisted metrics
        self._load_persisted_metrics()

    @staticmethod
    def _default_metrics() -> Dict:
        """Return default metrics structure."""
        return {
            'instance_id': os.environ.get('HOSTNAME', 'unknown'),
            'version': os.environ.get('APP_VERSION', '1.0.0'),
            'period_start': datetime.now().isoformat(),
            'total_queries': 0,
            'queries_by_node': {},
            'error_count': 0,
            'errors_by_type': {},
            'avg_response_time_ms': 0.0,
            'total_response_time_ms': 0.0,
            'node_availability': {},
            'uptime_seconds': 0,
            'restarts': 0,
            'peak_concurrent_queries': 0,
            '_current_concurrent': 0,
        }

    def _load_persisted_metrics(self):
        """Load metrics from disk if available."""
        metrics_file = TELEMETRY_DIR / 'current_metrics.json'
        try:
            if metrics_file.exists():
                with open(metrics_file, 'r') as f:
                    saved = json.load(f)
                # Merge persisted counters into current
                with self._lock:
                    self._metrics['total_queries'] = saved.get('total_queries', 0)
                    self._metrics['error_count'] = saved.get('error_count', 0)
                    self._metrics['queries_by_node'] = saved.get('queries_by_node', {})
                    self._metrics['errors_by_type'] = saved.get('errors_by_type', {})
                    self._metrics['restarts'] = saved.get('restarts', 0) + 1
                logger.info("Loaded persisted telemetry metrics")
        except Exception as e:
            logger.warning(f"Could not load persisted metrics: {e}")

    def start(self):
        """Start background telemetry threads."""
        if self._running:
            return
        self._running = True

        # Background flush to disk
        self._flush_thread = threading.Thread(
            target=self._flush_loop, daemon=True, name="TelemetryFlush"
        )
        self._flush_thread.start()

        # Background remote reporting
        if TELEMETRY_API:
            self._report_thread = threading.Thread(
                target=self._report_loop, daemon=True, name="TelemetryReport"
            )
            self._report_thread.start()

        logger.info("Telemetry collector started")

    def record_query(self, node_id: str, response_time_ms: float, success: bool = True):
        """Record a query event (anonymous - no query content stored)."""
        with self._lock:
            self._metrics['total_queries'] += 1
            self._metrics['queries_by_node'][node_id] = \
                self._metrics['queries_by_node'].get(node_id, 0) + 1
            self._metrics['total_response_time_ms'] += response_time_ms
            if self._metrics['total_queries'] > 0:
                self._metrics['avg_response_time_ms'] = (
                    self._metrics['total_response_time_ms'] /
                    self._metrics['total_queries']
                )
            if not success:
                self._metrics['error_count'] += 1

    def record_error(self, error_type: str):
        """Record an error event (anonymous - no error details stored)."""
        with self._lock:
            self._metrics['error_count'] += 1
            self._metrics['errors_by_type'][error_type] = \
                self._metrics['errors_by_type'].get(error_type, 0) + 1

    def record_node_status(self, node_id: str, is_available: bool):
        """Record node availability status."""
        with self._lock:
            self._metrics['node_availability'][node_id] = {
                'available': is_available,
                'last_checked': datetime.now().isoformat()
            }

    def track_concurrent_start(self):
        """Track start of a concurrent query."""
        with self._lock:
            self._metrics['_current_concurrent'] += 1
            if self._metrics['_current_concurrent'] > self._metrics['peak_concurrent_queries']:
                self._metrics['peak_concurrent_queries'] = self._metrics['_current_concurrent']

    def track_concurrent_end(self):
        """Track end of a concurrent query."""
        with self._lock:
            self._metrics['_current_concurrent'] = max(0, self._metrics['_current_concurrent'] - 1)

    def get_metrics(self) -> Dict:
        """Get current metrics snapshot (safe copy)."""
        with self._lock:
            metrics = dict(self._metrics)
            metrics['uptime_seconds'] = int(time.time() - self._start_time)
            # Remove internal tracking fields
            metrics.pop('_current_concurrent', None)
            metrics.pop('total_response_time_ms', None)
            return metrics

    def get_kpi_summary(self) -> Dict:
        """Get high-level KPI summary for admin dashboard."""
        metrics = self.get_metrics()
        uptime = metrics['uptime_seconds']
        uptime_hours = uptime / 3600

        return {
            'uptime_hours': round(uptime_hours, 2),
            'uptime_formatted': self._format_uptime(uptime),
            'total_queries': metrics['total_queries'],
            'queries_per_hour': round(metrics['total_queries'] / max(uptime_hours, 0.01), 2),
            'avg_response_time_ms': round(metrics['avg_response_time_ms'], 1),
            'error_rate': round(
                (metrics['error_count'] / max(metrics['total_queries'], 1)) * 100, 2
            ),
            'error_count': metrics['error_count'],
            'node_utilization': metrics['queries_by_node'],
            'node_availability': metrics['node_availability'],
            'peak_concurrent_queries': metrics['peak_concurrent_queries'],
            'version': metrics['version'],
            'restarts': metrics['restarts'],
        }

    @staticmethod
    def _format_uptime(seconds: int) -> str:
        """Format uptime in human-readable form."""
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        minutes = (seconds % 3600) // 60
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"

    def _flush_to_disk(self):
        """Persist current metrics to disk."""
        try:
            metrics = self.get_metrics()
            metrics_file = TELEMETRY_DIR / 'current_metrics.json'
            with open(metrics_file, 'w') as f:
                json.dump(metrics, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to flush telemetry to disk: {e}")

    def _flush_loop(self):
        """Periodically flush metrics to disk."""
        while self._running:
            time.sleep(FLUSH_INTERVAL)
            self._flush_to_disk()

    def _report_to_server(self):
        """Send anonymous aggregate metrics to remote telemetry endpoint."""
        if not TELEMETRY_API:
            return
        try:
            import requests
            metrics = self.get_kpi_summary()
            metrics['instance_id'] = self._metrics.get('instance_id', 'unknown')
            requests.post(
                f"{TELEMETRY_API}/api/telemetry/report",
                json=metrics,
                timeout=10
            )
            logger.debug("Telemetry report sent to server")
        except Exception as e:
            logger.debug(f"Could not send telemetry report: {e}")

    def _report_loop(self):
        """Periodically send metrics to remote server."""
        while self._running:
            time.sleep(REPORT_INTERVAL)
            self._report_to_server()


# Singleton instance
_collector: Optional[TelemetryCollector] = None


def get_telemetry_collector() -> TelemetryCollector:
    """Get or create the singleton telemetry collector."""
    global _collector
    if _collector is None:
        _collector = TelemetryCollector()
    return _collector
