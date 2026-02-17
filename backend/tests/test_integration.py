#!/usr/bin/env python3
"""
Integration tests that run against live test_server and license_api_server.

These tests require both servers to be running:
  - test_server.py on port 5002
  - license_api_server.py on port 5003

Set environment variables:
  TEST_SERVER_URL=http://localhost:5002
  LICENSE_SERVER_URL=http://localhost:5003
  SNF_ADMIN_SECRET=<your-admin-secret>
"""

import os
import sys
import json
import unittest
import requests

# Server URLs (configurable via env vars)
TEST_SERVER_URL = os.environ.get('TEST_SERVER_URL', 'http://localhost:5002')
LICENSE_SERVER_URL = os.environ.get('LICENSE_SERVER_URL', 'http://localhost:5003')
ADMIN_SECRET = os.environ.get('SNF_ADMIN_SECRET', 'test-admin-secret')


class TestServerIntegration(unittest.TestCase):
    """Integration tests for test_server.py endpoints."""

    def test_health_check(self):
        """Test /status returns healthy."""
        resp = requests.get(f'{TEST_SERVER_URL}/status', timeout=5)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['status'], 'healthy')

    def test_get_nodes(self):
        """Test /nodes returns node list."""
        resp = requests.get(f'{TEST_SERVER_URL}/nodes', timeout=5)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('nodes', data)
        self.assertIsInstance(data['nodes'], list)
        self.assertTrue(len(data['nodes']) > 0)

    def test_query_endpoint(self):
        """Test POST /query returns a response."""
        resp = requests.post(
            f'{TEST_SERVER_URL}/query',
            json={'prompt': 'Hello, world!'},
            timeout=10
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('response', data)
        self.assertEqual(data['status'], 'success')

    def test_registration(self):
        """Test POST /api/registration/register creates a license."""
        resp = requests.post(
            f'{TEST_SERVER_URL}/api/registration/register',
            json={'email': 'integration-test@example.com'},
            timeout=5
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertIn('license_key', data)
        self.assertTrue(data['license_key'].startswith('SNF-'))


class LicenseServerIntegration(unittest.TestCase):
    """Integration tests for license_api_server.py endpoints."""

    def test_server_info(self):
        """Test root endpoint returns server info."""
        resp = requests.get(f'{LICENSE_SERVER_URL}/', timeout=5)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['service'], 'SNF-AI License Server')
        self.assertIn('endpoints', data)

    def test_server_status(self):
        """Test /api/status returns health status."""
        resp = requests.get(f'{LICENSE_SERVER_URL}/api/status', timeout=5)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['status'], 'healthy')
        self.assertIn('total_licenses', data)
        self.assertIn('active_licenses', data)

    def test_registration_flow(self):
        """Test full registration → validation → admin listing flow."""
        # Step 1: Register
        reg_resp = requests.post(
            f'{LICENSE_SERVER_URL}/api/registration/register',
            json={'email': 'flow-test@example.com', 'duration_days': 30},
            timeout=5
        )
        self.assertEqual(reg_resp.status_code, 200)
        reg_data = reg_resp.json()
        self.assertTrue(reg_data['success'])
        license_key = reg_data['license_key']
        self.assertTrue(license_key.startswith('SNF-'))

        # Step 2: Validate (with device binding)
        val_resp = requests.post(
            f'{LICENSE_SERVER_URL}/api/registration/validate',
            json={
                'license_key': license_key,
                'device_id': 'test-device-001',
                'request_seed': True
            },
            timeout=5
        )
        self.assertEqual(val_resp.status_code, 200)
        val_data = val_resp.json()
        self.assertTrue(val_data['valid'])
        self.assertEqual(val_data['email'], 'flow-test@example.com')
        self.assertIn('decryption_seed', val_data)

        # Step 3: Validate on different device should fail
        val2_resp = requests.post(
            f'{LICENSE_SERVER_URL}/api/registration/validate',
            json={
                'license_key': license_key,
                'device_id': 'different-device-999',
            },
            timeout=5
        )
        self.assertEqual(val2_resp.status_code, 403)
        val2_data = val2_resp.json()
        self.assertFalse(val2_data['valid'])

        # Step 4: Admin can see the license
        list_resp = requests.get(
            f'{LICENSE_SERVER_URL}/api/admin/licenses',
            params={'admin_secret': ADMIN_SECRET},
            timeout=5
        )
        self.assertEqual(list_resp.status_code, 200)
        list_data = list_resp.json()
        keys = [lic['license_key'] for lic in list_data['licenses']]
        self.assertIn(license_key, keys)

    def test_registration_validation(self):
        """Test registration rejects invalid input."""
        # Missing email
        resp = requests.post(
            f'{LICENSE_SERVER_URL}/api/registration/register',
            json={'duration_days': 30},
            timeout=5
        )
        self.assertEqual(resp.status_code, 400)

        # Invalid email format
        resp = requests.post(
            f'{LICENSE_SERVER_URL}/api/registration/register',
            json={'email': 'not-an-email'},
            timeout=5
        )
        self.assertEqual(resp.status_code, 400)

    def test_admin_auth_required(self):
        """Test admin endpoints require authentication."""
        # No secret
        resp = requests.get(f'{LICENSE_SERVER_URL}/api/admin/licenses', timeout=5)
        self.assertEqual(resp.status_code, 401)

        # Wrong secret
        resp = requests.get(
            f'{LICENSE_SERVER_URL}/api/admin/licenses',
            params={'admin_secret': 'wrong-secret'},
            timeout=5
        )
        self.assertEqual(resp.status_code, 401)

    def test_admin_kpis(self):
        """Test admin KPI endpoint returns aggregate data."""
        resp = requests.get(
            f'{LICENSE_SERVER_URL}/api/admin/kpis',
            params={'admin_secret': ADMIN_SECRET},
            timeout=5
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('license_kpis', data)
        self.assertIn('telemetry', data)
        self.assertIn('total_licenses', data['license_kpis'])

    def test_telemetry_ingestion(self):
        """Test anonymous telemetry report ingestion."""
        report = {
            'instance_id': 'integration-test-instance',
            'total_queries': 100,
            'queries_per_hour': 10.0,
            'avg_response_time_ms': 250.0,
            'error_rate': 2.0,
            'error_count': 5,
            'uptime_hours': 24.0,
            'version': '1.0.0',
        }
        resp = requests.post(
            f'{LICENSE_SERVER_URL}/api/telemetry/report',
            json=report,
            timeout=5
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['success'])

        # Verify reflected in KPIs
        kpi_resp = requests.get(
            f'{LICENSE_SERVER_URL}/api/admin/kpis',
            params={'admin_secret': ADMIN_SECRET},
            timeout=5
        )
        kpi_data = kpi_resp.json()
        self.assertGreaterEqual(
            kpi_data['telemetry']['aggregate_queries'], 100
        )

    def test_update_check(self):
        """Test update checking endpoint."""
        resp = requests.get(
            f'{LICENSE_SERVER_URL}/api/updates/check',
            params={'current_version': '0.1.0'},
            timeout=5
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('update_available', data)
        self.assertIn('latest_version', data)
        self.assertTrue(data['update_available'])

    def test_admin_set_and_check_update(self):
        """Test setting a new release then checking for it."""
        # Set new release
        set_resp = requests.post(
            f'{LICENSE_SERVER_URL}/api/admin/updates/set',
            json={
                'admin_secret': ADMIN_SECRET,
                'latest_version': '99.0.0',
                'release_notes': 'Integration test release',
                'update_url': 'https://example.com/test-update',
            },
            timeout=5
        )
        self.assertEqual(set_resp.status_code, 200)

        # Check for update
        check_resp = requests.get(
            f'{LICENSE_SERVER_URL}/api/updates/check',
            params={'current_version': '1.0.0'},
            timeout=5
        )
        check_data = check_resp.json()
        self.assertTrue(check_data['update_available'])
        self.assertEqual(check_data['latest_version'], '99.0.0')
        self.assertEqual(check_data['release_notes'], 'Integration test release')

    def test_license_revoke_and_extend(self):
        """Test license revocation and extension."""
        # Register a license
        reg_resp = requests.post(
            f'{LICENSE_SERVER_URL}/api/registration/register',
            json={'email': 'revoke-test@example.com', 'duration_days': 30},
            timeout=5
        )
        license_key = reg_resp.json()['license_key']

        # Revoke
        revoke_resp = requests.post(
            f'{LICENSE_SERVER_URL}/api/admin/revoke',
            json={'license_key': license_key, 'admin_secret': ADMIN_SECRET},
            timeout=5
        )
        self.assertEqual(revoke_resp.status_code, 200)

        # Validate should fail (revoked)
        val_resp = requests.post(
            f'{LICENSE_SERVER_URL}/api/registration/validate',
            json={'license_key': license_key, 'device_id': 'test-device'},
            timeout=5
        )
        self.assertEqual(val_resp.status_code, 401)
        self.assertFalse(val_resp.json()['valid'])

        # Extend (still revoked but expiry is extended)
        ext_resp = requests.post(
            f'{LICENSE_SERVER_URL}/api/admin/extend',
            json={
                'license_key': license_key,
                'additional_days': 60,
                'admin_secret': ADMIN_SECRET
            },
            timeout=5
        )
        self.assertEqual(ext_resp.status_code, 200)
        self.assertIn('new_expiry', ext_resp.json())


if __name__ == '__main__':
    unittest.main()
