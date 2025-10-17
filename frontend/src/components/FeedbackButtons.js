// Copyright (c) 2025 SNF-AI
// SPDX-License-Identifier: MIT

import React, { useState } from 'react';
import { FaThumbsUp, FaThumbsDown } from 'react-icons/fa';

const FeedbackButtons = ({ onFeedback, disabled }) => {
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleFeedback = async (isPositive) => {
    if (disabled || isSubmitting) return;
    
    setIsSubmitting(true);
    try {
      await onFeedback(isPositive);
    } catch (error) {
      console.error('Error submitting feedback:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="feedback-buttons">
      <button 
        className="feedback-button positive"
        onClick={() => handleFeedback(true)}
        disabled={disabled || isSubmitting}
        aria-label="Helpful response"
      >
        <FaThumbsUp /> Helpful
      </button>
      
      <button 
        className="feedback-button negative"
        onClick={() => handleFeedback(false)}
        disabled={disabled || isSubmitting}
        aria-label="Not helpful response"
      >
        <FaThumbsDown /> Not Helpful
      </button>
    </div>
  );
};

export default FeedbackButtons;
