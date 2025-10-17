import React from 'react';

export default function ContinueButton({ onContinue, disabled }) {
  return (
    <button className="continue-btn" onClick={onContinue} disabled={disabled}>
      Continue Generating
    </button>
  );
}
