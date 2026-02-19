// Copyright (c) 2025 Twhyne AI
// SPDX-License-Identifier: MIT

import React, { useState, useEffect, useCallback } from 'react';
import { FaSyncAlt, FaCheckCircle, FaExclamationTriangle } from 'react-icons/fa';
import './UpdateBanner.css';

const UpdateBanner = () => {
  const [updateInfo, setUpdateInfo] = useState(null);
  const [checking, setChecking] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  const checkForUpdates = useCallback(async () => {
    setChecking(true);
    try {
      const response = await fetch('/api/updates/check');
      if (response.ok) {
        const data = await response.json();
        setUpdateInfo(data);
      }
    } catch (error) {
      // API not reachable — silently ignore
      setUpdateInfo(null);
    } finally {
      setChecking(false);
    }
  }, []);

  useEffect(() => {
    checkForUpdates();
  }, [checkForUpdates]);

  if (dismissed || !updateInfo) {
    return null;
  }

  const { current_version, latest_version, update_available, update_url } = updateInfo;

  return (
    <div className={`update-banner ${update_available ? 'update-available' : 'up-to-date'}`}>
      <div className="update-banner-content">
        {update_available ? (
          <>
            <FaExclamationTriangle className="update-icon" />
            <span className="update-text">
              Update available: <strong>v{latest_version}</strong> (current: v{current_version}).
              Run <code>docker pull twhyne/twhyne:latest</code> to update.
            </span>
            {update_url && (
              <a
                href={update_url}
                className="update-link"
                target="_blank"
                rel="noopener noreferrer"
              >
                Release Notes
              </a>
            )}
          </>
        ) : (
          <>
            <FaCheckCircle className="update-icon" />
            <span className="update-text">
              Running <strong>v{current_version}</strong> — you're up to date.
            </span>
          </>
        )}
        <div className="update-actions">
          <button
            className="update-check-btn"
            onClick={checkForUpdates}
            disabled={checking}
            title="Check for updates"
            aria-label="Check for updates"
          >
            <FaSyncAlt className={checking ? 'spin' : ''} />
          </button>
          <button
            className="update-dismiss-btn"
            onClick={() => setDismissed(true)}
            title="Dismiss"
            aria-label="Dismiss update banner"
          >
            ×
          </button>
        </div>
      </div>
    </div>
  );
};

export default UpdateBanner;
