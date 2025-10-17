// Copyright (c) 2025 SNF-AI
// SPDX-License-Identifier: MIT

import React from 'react';
import './ProgressBar.css';

/**
 * Progress bar component for streaming responses
 * 
 * @param {Object} props Component props
 * @param {number} props.percent Percentage of completion (0-100)
 * @param {number} props.tokensProcessed Number of tokens processed so far
 * @param {number} props.estimatedTotal Estimated total number of tokens
 * @returns {JSX.Element} Progress bar component
 */
const ProgressBar = ({ percent, tokensProcessed, estimatedTotal }) => {
  // Ensure percent is between 0 and 100
  const clampedPercent = Math.min(Math.max(percent, 0), 100);
  
  return (
    <div className="progress-container">
      <div className="progress-bar">
        <div 
          className="progress-fill"
          style={{ width: `${clampedPercent}%` }}
        />
      </div>
      <div className="progress-stats">
        <span className="progress-percent">{Math.round(clampedPercent)}%</span>
        <span className="progress-tokens">
          {tokensProcessed.toLocaleString()} / {estimatedTotal.toLocaleString()} tokens
        </span>
      </div>
    </div>
  );
};

export default ProgressBar;
