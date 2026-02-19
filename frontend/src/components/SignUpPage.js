// Copyright (c) 2025 Twhyne AI
// SPDX-License-Identifier: MIT

import React, { useState } from 'react';
import './SignUpPage.css';

const SignUpPage = ({ onNavigate }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [message, setMessage] = useState({ text: '', type: '' });
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setMessage({ text: '', type: '' });

    if (!email || !password) {
      setMessage({ text: 'Email and password are required.', type: 'error' });
      return;
    }

    if (password !== confirmPassword) {
      setMessage({ text: 'Passwords do not match.', type: 'error' });
      return;
    }

    if (password.length < 6) {
      setMessage({ text: 'Password must be at least 6 characters.', type: 'error' });
      return;
    }

    setIsSubmitting(true);

    try {
      const response = await fetch('/api/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });

      const data = await response.json();

      if (response.ok) {
        setMessage({ text: 'Registration successful! You can now use the system.', type: 'success' });
        setEmail('');
        setPassword('');
        setConfirmPassword('');
      } else {
        setMessage({ text: data.error || 'Registration failed. Please try again.', type: 'error' });
      }
    } catch (error) {
      setMessage({ text: 'Network error. Please check your connection and try again.', type: 'error' });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="signup-page">
      <div className="signup-container">
        <h2 className="signup-title">Create Account</h2>
        <p className="signup-subtitle">Sign up to access Twhyne AI</p>

        <form className="signup-form" onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="signup-email">Email Address</label>
            <input
              type="email"
              id="signup-email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Enter your email"
              disabled={isSubmitting}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="signup-password">Password</label>
            <input
              type="password"
              id="signup-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Create a password"
              disabled={isSubmitting}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="signup-confirm-password">Confirm Password</label>
            <input
              type="password"
              id="signup-confirm-password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Confirm your password"
              disabled={isSubmitting}
              required
            />
          </div>

          {message.text && (
            <div className={`signup-message ${message.type}`} role="alert">
              {message.text}
            </div>
          )}

          <button type="submit" className="signup-button" disabled={isSubmitting}>
            {isSubmitting ? 'Creating Account...' : 'Sign Up'}
          </button>
        </form>

        <div className="signup-footer-links">
          <button className="link-button" onClick={() => onNavigate('app')}>
            ← Back to App
          </button>
          <button className="link-button" onClick={() => onNavigate('downloads')}>
            Download Packages
          </button>
        </div>
      </div>
    </div>
  );
};

export default SignUpPage;
