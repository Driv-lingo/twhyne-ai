// Copyright (c) 2025 Twhyne AI
// SPDX-License-Identifier: MIT

import React from 'react';
import { FaWindows, FaApple, FaDocker, FaFileArchive, FaSyncAlt } from 'react-icons/fa';
import './DownloadPage.css';

const GITHUB_RELEASE_BASE = 'https://github.com/Driv-lingo/twhyne-ai/releases';
const DOCKER_IMAGE = 'twhyne/twhyne';

const downloads = [
  {
    id: 'docker',
    title: 'Docker (Recommended)',
    icon: <FaDocker />,
    description: 'Pull the official Docker image — the standard way to install and update.',
    command: `docker pull ${DOCKER_IMAGE}:latest`,
    href: `https://hub.docker.com/r/${DOCKER_IMAGE}`,
    label: 'View on Docker Hub',
  },
  {
    id: 'windows',
    title: 'Windows',
    icon: <FaWindows />,
    description: 'Windows installer package with batch scripts for easy setup.',
    fileName: 'SNF-AI-Windows.zip',
    href: `${GITHUB_RELEASE_BASE}/latest/download/SNF-AI-Windows.zip`,
  },
  {
    id: 'mac',
    title: 'macOS',
    icon: <FaApple />,
    description: 'macOS package with shell scripts for quick start.',
    fileName: 'SNF-AI-Mac.zip',
    href: `${GITHUB_RELEASE_BASE}/latest/download/SNF-AI-Mac.zip`,
  },
  {
    id: 'source',
    title: 'Source Archive',
    icon: <FaFileArchive />,
    description: 'Full source code archive for custom builds.',
    fileName: 'SNF-AI-Windsurf-3.0.0.zip',
    href: `${GITHUB_RELEASE_BASE}/latest`,
    label: 'View Release',
  },
];

const DownloadPage = ({ onNavigate }) => {
  return (
    <div className="download-page">
      <div className="download-container">
        <h2 className="download-title">Download Twhyne AI</h2>
        <p className="download-subtitle">
          Choose a package for your platform to get started
        </p>

        <div className="download-grid">
          {downloads.map((item) => (
            <div key={item.id} className={`download-card ${item.id === 'docker' ? 'recommended' : ''}`}>
              <div className="download-icon">{item.icon}</div>
              <h3>{item.title}</h3>
              <p>{item.description}</p>
              {item.command && (
                <code className="download-command">{item.command}</code>
              )}
              {item.fileName && (
                <span className="download-filename">{item.fileName}</span>
              )}
              <a
                href={item.href}
                className="download-button"
                target="_blank"
                rel="noopener noreferrer"
              >
                {item.label || 'Download'}
              </a>
            </div>
          ))}
        </div>

        <div className="update-instructions">
          <h3><FaSyncAlt /> How Clients Get Updates</h3>
          <p>
            Twhyne AI uses Docker images for versioned releases. Each version is
            tagged (e.g. <code>twhyne/twhyne:1.0.0</code>) and{' '}
            <code>:latest</code> always points to the newest stable release.
          </p>
          <div className="update-steps">
            <div className="update-step">
              <span className="step-number">1</span>
              <div>
                <strong>Pull the latest image</strong>
                <code>docker pull {DOCKER_IMAGE}:latest</code>
              </div>
            </div>
            <div className="update-step">
              <span className="step-number">2</span>
              <div>
                <strong>Restart the container</strong>
                <code>docker compose up -d</code>
              </div>
            </div>
            <div className="update-step">
              <span className="step-number">3</span>
              <div>
                <strong>Verify</strong>
                <span>The app checks for updates automatically and shows a banner when a new version is available.</span>
              </div>
            </div>
          </div>
        </div>

        <div className="download-footer-links">
          <button className="link-button" onClick={() => onNavigate('app')}>
            ← Back to App
          </button>
          <button className="link-button" onClick={() => onNavigate('signup')}>
            Create Account
          </button>
        </div>
      </div>
    </div>
  );
};

export default DownloadPage;
