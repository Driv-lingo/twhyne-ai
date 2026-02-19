// Copyright (c) 2025 Twhyne AI
// SPDX-License-Identifier: MIT

import React from 'react';
import { FaWindows, FaApple, FaDocker, FaFileArchive } from 'react-icons/fa';
import './DownloadPage.css';

const GITHUB_RELEASE_BASE = 'https://github.com/Driv-lingo/twhyne-ai/releases';

const downloads = [
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
    id: 'docker',
    title: 'Docker',
    icon: <FaDocker />,
    description: 'Docker Compose setup for containerized deployment.',
    fileName: 'docker-compose.yml',
    href: `${GITHUB_RELEASE_BASE}/latest`,
    label: 'View Release',
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
            <div key={item.id} className="download-card">
              <div className="download-icon">{item.icon}</div>
              <h3>{item.title}</h3>
              <p>{item.description}</p>
              <span className="download-filename">{item.fileName}</span>
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
