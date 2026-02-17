#!/usr/bin/env python3
"""
Admin API endpoints for system management.
Provides admin dashboard data, KPI metrics, user/license overview,
and remote update management.
All data is aggregate — no individual user data/PII is exposed.
"""

import os
import logging
from flask import Blueprint, request, jsonify
from functools import wraps

logger = logging.getLogger(__name__)

# Admin secret for authentication
ADMIN_SECRET = os.environ.get('SNF_ADMIN_SECRET', '')

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')


def require_admin(f):
    """Decorator to require admin authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        admin_secret = request.headers.get('X-Admin-Secret', '')
        body_secret = None

        # Support secret in request body for POST requests
        if request.is_json:
            body_secret = request.get_json(silent=True) or {}
            body_secret = body_secret.get('admin_secret', '')

        # Check all possible auth sources
        provided_secret = admin_secret or body_secret or ''

        # Also check Bearer token
        if auth_header.startswith('Bearer '):
            provided_secret = auth_header[7:]

        if not ADMIN_SECRET:
            return jsonify({'error': 'Admin access not configured (SNF_ADMIN_SECRET not set)'}), 503

        if provided_secret != ADMIN_SECRET:
            return jsonify({'error': 'Unauthorized'}), 401

        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/dashboard', methods=['GET'])
@require_admin
def admin_dashboard():
    """
    Get admin dashboard overview.
    Returns aggregate KPIs, system health, and license summary.
    No individual user data is returned.
    """
    from telemetry import get_telemetry_collector
    from update_manager import get_update_manager

    telemetry = get_telemetry_collector()
    updater = get_update_manager()

    kpis = telemetry.get_kpi_summary()
    update_status = updater.get_status()

    return jsonify({
        'kpis': kpis,
        'update_status': update_status,
        'system': {
            'status': 'running',
            'uptime': kpis['uptime_formatted'],
            'version': kpis['version'],
        }
    })


@admin_bp.route('/kpis', methods=['GET'])
@require_admin
def admin_kpis():
    """
    Get detailed KPI metrics.
    All metrics are aggregate — no PII or individual query data.
    """
    from telemetry import get_telemetry_collector

    telemetry = get_telemetry_collector()
    return jsonify(telemetry.get_kpi_summary())


@admin_bp.route('/metrics', methods=['GET'])
@require_admin
def admin_metrics():
    """Get raw aggregate metrics for detailed analysis."""
    from telemetry import get_telemetry_collector

    telemetry = get_telemetry_collector()
    return jsonify(telemetry.get_metrics())


@admin_bp.route('/updates/check', methods=['POST'])
@require_admin
def admin_check_updates():
    """Trigger an update check."""
    from update_manager import get_update_manager

    updater = get_update_manager()
    result = updater.check_for_updates()
    return jsonify(result)


@admin_bp.route('/updates/status', methods=['GET'])
@require_admin
def admin_update_status():
    """Get current update status."""
    from update_manager import get_update_manager

    updater = get_update_manager()
    return jsonify(updater.get_status())
