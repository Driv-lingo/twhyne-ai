import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import SignUpPage from '../components/SignUpPage';

describe('SignUpPage', () => {
  const mockNavigate = jest.fn();

  beforeEach(() => {
    mockNavigate.mockClear();
  });

  test('renders sign-up form with all fields', () => {
    render(<SignUpPage onNavigate={mockNavigate} />);
    expect(screen.getByText('Create Account')).toBeInTheDocument();
    expect(screen.getByLabelText('Email Address')).toBeInTheDocument();
    expect(screen.getByLabelText('Password')).toBeInTheDocument();
    expect(screen.getByLabelText('Confirm Password')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Sign Up' })).toBeInTheDocument();
  });

  test('shows error when passwords do not match', async () => {
    render(<SignUpPage onNavigate={mockNavigate} />);
    fireEvent.change(screen.getByLabelText('Email Address'), { target: { value: 'test@example.com' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'password123' } });
    fireEvent.change(screen.getByLabelText('Confirm Password'), { target: { value: 'different' } });
    fireEvent.click(screen.getByRole('button', { name: 'Sign Up' }));
    expect(await screen.findByText('Passwords do not match.')).toBeInTheDocument();
  });

  test('shows error when password is too short', async () => {
    render(<SignUpPage onNavigate={mockNavigate} />);
    fireEvent.change(screen.getByLabelText('Email Address'), { target: { value: 'test@example.com' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: '123' } });
    fireEvent.change(screen.getByLabelText('Confirm Password'), { target: { value: '123' } });
    fireEvent.click(screen.getByRole('button', { name: 'Sign Up' }));
    expect(await screen.findByText('Password must be at least 6 characters.')).toBeInTheDocument();
  });

  test('navigates to app when back button is clicked', () => {
    render(<SignUpPage onNavigate={mockNavigate} />);
    fireEvent.click(screen.getByText('← Back to App'));
    expect(mockNavigate).toHaveBeenCalledWith('app');
  });

  test('navigates to downloads page', () => {
    render(<SignUpPage onNavigate={mockNavigate} />);
    fireEvent.click(screen.getByText('Download Packages'));
    expect(mockNavigate).toHaveBeenCalledWith('downloads');
  });

  test('submits form successfully', async () => {
    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ success: true, message: 'Registration successful.' }),
      })
    );

    render(<SignUpPage onNavigate={mockNavigate} />);
    fireEvent.change(screen.getByLabelText('Email Address'), { target: { value: 'test@example.com' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'password123' } });
    fireEvent.change(screen.getByLabelText('Confirm Password'), { target: { value: 'password123' } });
    fireEvent.click(screen.getByRole('button', { name: 'Sign Up' }));

    expect(await screen.findByText('Registration successful! You can now use the system.')).toBeInTheDocument();

    global.fetch.mockRestore();
  });

  test('shows server error message', async () => {
    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: false,
        json: () => Promise.resolve({ error: 'Email already registered' }),
      })
    );

    render(<SignUpPage onNavigate={mockNavigate} />);
    fireEvent.change(screen.getByLabelText('Email Address'), { target: { value: 'test@example.com' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'password123' } });
    fireEvent.change(screen.getByLabelText('Confirm Password'), { target: { value: 'password123' } });
    fireEvent.click(screen.getByRole('button', { name: 'Sign Up' }));

    expect(await screen.findByText('Email already registered')).toBeInTheDocument();

    global.fetch.mockRestore();
  });
});
