#!/usr/bin/env python3
"""
Unit tests for telemetry, update_manager, and admin_api modules.
"""

import os
import sys
import json
import time
import unittest
import tempfile
import shutil

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Set up temp directories before importing modules
TEST_TEMP_DIR = tempfile.mkdtemp()
os.environ['TELEMETRY_DIR'] = os.path.join(TEST_TEMP_DIR, 'telemetry')
os.environ['DATA_DIR'] = os.path.join(TEST_TEMP_DIR, 'data')
os.environ['APP_VERSION'] = '1.0.0-test'
os.environ['SNF_ADMIN_SECRET'] = 'test-admin-secret'


class TestTelemetryCollector(unittest.TestCase):
    """Tests for the TelemetryCollector class."""

    def setUp(self):
        # Reset singleton and clean persisted files
        import telemetry
        telemetry._collector = None
        metrics_file = os.path.join(os.environ['TELEMETRY_DIR'], 'current_metrics.json')
        if os.path.exists(metrics_file):
            os.remove(metrics_file)
        self.collector = telemetry.TelemetryCollector()

    def test_default_metrics(self):
        """Test that default metrics are initialized correctly."""
        metrics = self.collector.get_metrics()
        self.assertEqual(metrics['total_queries'], 0)
        self.assertEqual(metrics['error_count'], 0)
        self.assertIsInstance(metrics['queries_by_node'], dict)
        self.assertIsInstance(metrics['uptime_seconds'], int)

    def test_record_query(self):
        """Test recording a query updates metrics."""
        self.collector.record_query('language-mistral-7b', 150.0, success=True)
        metrics = self.collector.get_metrics()
        self.assertEqual(metrics['total_queries'], 1)
        self.assertEqual(metrics['queries_by_node']['language-mistral-7b'], 1)
        self.assertAlmostEqual(metrics['avg_response_time_ms'], 150.0, places=1)

    def test_record_multiple_queries(self):
        """Test recording multiple queries aggregates correctly."""
        self.collector.record_query('language-mistral-7b', 100.0)
        self.collector.record_query('code-codellama-7b', 200.0)
        self.collector.record_query('language-mistral-7b', 300.0)
        metrics = self.collector.get_metrics()
        self.assertEqual(metrics['total_queries'], 3)
        self.assertEqual(metrics['queries_by_node']['language-mistral-7b'], 2)
        self.assertEqual(metrics['queries_by_node']['code-codellama-7b'], 1)
        self.assertAlmostEqual(metrics['avg_response_time_ms'], 200.0, places=1)

    def test_record_error(self):
        """Test recording errors updates metrics."""
        self.collector.record_error('query_processing')
        self.collector.record_error('query_processing')
        self.collector.record_error('timeout')
        metrics = self.collector.get_metrics()
        self.assertEqual(metrics['error_count'], 3)
        self.assertEqual(metrics['errors_by_type']['query_processing'], 2)
        self.assertEqual(metrics['errors_by_type']['timeout'], 1)

    def test_record_failed_query(self):
        """Test that failed queries increment error count."""
        self.collector.record_query('language-mistral-7b', 50.0, success=False)
        metrics = self.collector.get_metrics()
        self.assertEqual(metrics['total_queries'], 1)
        self.assertEqual(metrics['error_count'], 1)

    def test_node_status(self):
        """Test recording node availability."""
        self.collector.record_node_status('language-mistral-7b', True)
        self.collector.record_node_status('code-codellama-7b', False)
        metrics = self.collector.get_metrics()
        self.assertTrue(metrics['node_availability']['language-mistral-7b']['available'])
        self.assertFalse(metrics['node_availability']['code-codellama-7b']['available'])

    def test_concurrent_tracking(self):
        """Test concurrent query tracking."""
        self.collector.track_concurrent_start()
        self.collector.track_concurrent_start()
        self.collector.track_concurrent_start()
        self.collector.track_concurrent_end()
        metrics = self.collector.get_metrics()
        self.assertEqual(metrics['peak_concurrent_queries'], 3)

    def test_kpi_summary(self):
        """Test KPI summary includes expected fields."""
        self.collector.record_query('language-mistral-7b', 100.0)
        kpis = self.collector.get_kpi_summary()
        self.assertIn('uptime_hours', kpis)
        self.assertIn('total_queries', kpis)
        self.assertIn('queries_per_hour', kpis)
        self.assertIn('avg_response_time_ms', kpis)
        self.assertIn('error_rate', kpis)
        self.assertIn('node_utilization', kpis)
        self.assertIn('version', kpis)
        self.assertEqual(kpis['total_queries'], 1)

    def test_kpi_no_pii(self):
        """Test that KPI summary contains no PII."""
        self.collector.record_query('test-node', 100.0)
        kpis = self.collector.get_kpi_summary()
        kpi_str = json.dumps(kpis)
        # Should not contain any user/query content
        self.assertNotIn('prompt', kpi_str)
        self.assertNotIn('email', kpi_str)
        self.assertNotIn('password', kpi_str)

    def test_uptime_formatting(self):
        """Test uptime formatting."""
        self.assertEqual(self.collector._format_uptime(90), '1m')
        self.assertEqual(self.collector._format_uptime(3700), '1h 1m')
        self.assertEqual(self.collector._format_uptime(90061), '1d 1h 1m')

    def test_flush_to_disk(self):
        """Test metrics can be flushed to disk."""
        self.collector.record_query('test-node', 100.0)
        self.collector._flush_to_disk()
        metrics_file = os.path.join(os.environ['TELEMETRY_DIR'], 'current_metrics.json')
        self.assertTrue(os.path.exists(metrics_file))
        with open(metrics_file, 'r') as f:
            saved = json.load(f)
        self.assertEqual(saved['total_queries'], 1)


class TestUpdateManager(unittest.TestCase):
    """Tests for the UpdateManager class."""

    def setUp(self):
        import update_manager
        update_manager._manager = None
        self.manager = update_manager.UpdateManager()

    def test_initial_status(self):
        """Test initial update status."""
        status = self.manager.get_status()
        self.assertEqual(status['current_version'], '1.0.0-test')
        self.assertFalse(status['update_available'])

    def test_get_status_fields(self):
        """Test that status contains all expected fields."""
        status = self.manager.get_status()
        self.assertIn('current_version', status)
        self.assertIn('latest_version', status)
        self.assertIn('update_available', status)
        self.assertIn('update_notes', status)
        self.assertIn('update_url', status)
        self.assertIn('last_check', status)

    def test_check_for_updates_no_api(self):
        """Test update check when no API is configured."""
        import update_manager
        original = update_manager.UPDATE_API
        update_manager.UPDATE_API = ''
        try:
            mgr = update_manager.UpdateManager()
            result = mgr.check_for_updates()
            self.assertIn('message', result)
            self.assertEqual(result['message'], 'Update checking not configured')
        finally:
            update_manager.UPDATE_API = original


class TestAdminAPI(unittest.TestCase):
    """Tests for admin API endpoints."""

    def setUp(self):
        from flask import Flask
        from admin_api import admin_bp
        self.app = Flask(__name__)
        self.app.register_blueprint(admin_bp)
        self.client = self.app.test_client()

    def test_admin_requires_auth(self):
        """Test that admin endpoints require authentication."""
        response = self.client.get('/api/admin/kpis')
        self.assertEqual(response.status_code, 401)

    def test_admin_rejects_wrong_secret(self):
        """Test that wrong admin secret is rejected."""
        response = self.client.get(
            '/api/admin/kpis',
            headers={'X-Admin-Secret': 'wrong-secret'}
        )
        self.assertEqual(response.status_code, 401)

    def test_admin_kpis_with_auth(self):
        """Test that admin KPIs endpoint works with correct auth."""
        response = self.client.get(
            '/api/admin/kpis',
            headers={'X-Admin-Secret': 'test-admin-secret'}
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn('total_queries', data)

    def test_admin_dashboard_with_auth(self):
        """Test that admin dashboard endpoint works with correct auth."""
        response = self.client.get(
            '/api/admin/dashboard',
            headers={'X-Admin-Secret': 'test-admin-secret'}
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn('kpis', data)
        self.assertIn('update_status', data)
        self.assertIn('system', data)

    def test_admin_update_status(self):
        """Test update status endpoint."""
        response = self.client.get(
            '/api/admin/updates/status',
            headers={'X-Admin-Secret': 'test-admin-secret'}
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn('current_version', data)

    def test_admin_bearer_auth(self):
        """Test that Bearer token authentication works."""
        response = self.client.get(
            '/api/admin/kpis',
            headers={'Authorization': 'Bearer test-admin-secret'}
        )
        self.assertEqual(response.status_code, 200)


class TestLicenseAPIServer(unittest.TestCase):
    """Tests for the license API server admin endpoints."""

    def setUp(self):
        os.environ['SNF_ADMIN_SECRET'] = 'test-admin-secret'
        import license_api_server
        self.app = license_api_server.app
        self.client = self.app.test_client()
        # Clear licenses for clean state
        license_api_server.LICENSES.clear()
        license_api_server.TELEMETRY_STORE.clear()

    def test_list_licenses_requires_auth(self):
        """Test that license listing requires admin auth."""
        response = self.client.get('/api/admin/licenses')
        self.assertEqual(response.status_code, 401)

    def test_list_licenses_with_auth(self):
        """Test listing licenses with correct auth."""
        response = self.client.get(
            '/api/admin/licenses?admin_secret=test-admin-secret'
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn('total', data)
        self.assertIn('licenses', data)

    def test_admin_kpis(self):
        """Test admin KPI summary endpoint."""
        response = self.client.get(
            '/api/admin/kpis?admin_secret=test-admin-secret'
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn('license_kpis', data)
        self.assertIn('telemetry', data)

    def test_telemetry_ingestion(self):
        """Test telemetry report ingestion."""
        report = {
            'instance_id': 'test-instance',
            'total_queries': 42,
            'queries_per_hour': 5.0,
            'avg_response_time_ms': 200.0,
            'error_rate': 1.5,
            'error_count': 3,
            'uptime_hours': 10.0,
            'version': '1.0.0',
        }
        response = self.client.post(
            '/api/telemetry/report',
            json=report,
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)

        # Verify it's reflected in KPIs
        kpi_response = self.client.get(
            '/api/admin/kpis?admin_secret=test-admin-secret'
        )
        kpi_data = kpi_response.get_json()
        self.assertEqual(
            kpi_data['telemetry']['aggregate_queries'], 42
        )

    def test_update_check(self):
        """Test update check endpoint."""
        response = self.client.get(
            '/api/updates/check?current_version=0.9.0'
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn('latest_version', data)
        self.assertIn('update_available', data)

    def test_admin_set_update(self):
        """Test admin set update endpoint."""
        response = self.client.post(
            '/api/admin/updates/set',
            json={
                'admin_secret': 'test-admin-secret',
                'latest_version': '2.0.0',
                'release_notes': 'New features',
                'update_url': 'https://example.com/update',
            },
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)

        # Verify update is reflected
        check_response = self.client.get(
            '/api/updates/check?current_version=1.0.0'
        )
        check_data = check_response.get_json()
        self.assertTrue(check_data['update_available'])
        self.assertEqual(check_data['latest_version'], '2.0.0')

    def test_register_and_list(self):
        """Test that registered licenses appear in admin listing."""
        # Register a license
        reg_response = self.client.post(
            '/api/registration/register',
            json={'email': 'test@example.com', 'duration_days': 30},
            content_type='application/json'
        )
        self.assertEqual(reg_response.status_code, 200)

        # List licenses
        list_response = self.client.get(
            '/api/admin/licenses?admin_secret=test-admin-secret'
        )
        data = list_response.get_json()
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['active'], 1)


def tearDownModule():
    """Clean up temp directories."""
    if os.path.exists(TEST_TEMP_DIR):
        shutil.rmtree(TEST_TEMP_DIR, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
