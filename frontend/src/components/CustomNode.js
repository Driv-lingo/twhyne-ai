// Copyright (c) 2025 SNF-AI
// SPDX-License-Identifier: MIT

import React from 'react';
import { Handle, Position } from 'reactflow';
import { 
  FaLanguage, 
  FaCode, 
  FaCalculator, 
  FaImage, 
  FaProjectDiagram, 
  FaServer,
  FaNetworkWired
} from 'react-icons/fa';

const getNodeIcon = (type) => {
  switch (type) {
    case 'language':
      return <FaLanguage />;
    case 'code':
      return <FaCode />;
    case 'math':
      return <FaCalculator />;
    case 'vision':
      return <FaImage />;
    case 'planner':
      return <FaProjectDiagram />;
    case 'claude':
      return <FaServer />;
    case 'kernel':
      return <FaNetworkWired />;
    default:
      return null;
  }
};

const getNodeColor = (type) => {
  switch (type) {
    case 'language':
      return { background: 'linear-gradient(135deg, #1a2a6c, #4361ee)', border: '#4361ee' };
    case 'code':
      return { background: 'linear-gradient(135deg, #134e5e, #71b280)', border: '#71b280' };
    case 'math':
      return { background: 'linear-gradient(135deg, #2c3e50, #4ca1af)', border: '#4ca1af' };
    case 'vision':
      return { background: 'linear-gradient(135deg, #5f2c82, #49a09d)', border: '#49a09d' };
    case 'planner':
      return { background: 'linear-gradient(135deg, #4b6cb7, #182848)', border: '#4b6cb7' };
    case 'claude':
      return { background: 'linear-gradient(135deg, #6a11cb, #2575fc)', border: '#2575fc' };
    case 'kernel':
      return { background: 'linear-gradient(135deg, #000428, #004e92)', border: '#004e92' };
    default:
      return { background: 'linear-gradient(135deg, #232526, #414345)', border: '#414345' };
  }
};

const getNodeDescription = (type) => {
  switch (type) {
    case 'language':
      return 'Language expert';
    case 'code':
      return 'Code generation';
    case 'math':
      return 'Math computation';
    case 'vision':
      return 'Image analysis';
    case 'planner':
      return 'Task planning';
    case 'claude':
      return 'Advanced reasoning';
    case 'kernel':
      return 'Routing kernel';
    default:
      return 'Unknown node';
  }
};

const CustomNode = ({ data }) => {
  const { type, label, status, isProcessing, statusDetail } = data;
  const colors = getNodeColor(type);
  const nodeIcon = getNodeIcon(type);
  const description = getNodeDescription(type);
  const titleText = statusDetail ? `${label}: ${status} — ${statusDetail}` : `${label}: ${status}`;

  return (
    <div className={`custom-node ${status} ${isProcessing ? 'processing' : ''}`} title={titleText}>
      <Handle
        type="target"
        position={Position.Top}
        style={{ background: colors.border }}
      />

      <div className="node-body" style={{ background: colors.background, borderColor: colors.border }}>
        <div className="node-header">
          <div className="node-icon">{nodeIcon}</div>
          <div className="node-title">{label}</div>
        </div>

        <div className="node-content">
          <div className="node-description">{description}</div>
          <div className={`node-status ${status}`}>{status}</div>
          {status === 'offline' && statusDetail && (
            <div className="node-status-detail">{statusDetail}</div>
          )}
        </div>
        
        {isProcessing && (
          <div className="node-processing-indicator">
            <div className="pulse-ring"></div>
          </div>
        )}
      </div>
      
      <Handle
        type="source"
        position={Position.Bottom}
        style={{ background: colors.border }}
      />
    </div>
  );
};

export default CustomNode;
