import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import UpdateBanner from '../components/UpdateBanner';

describe('UpdateBanner', () => {
  afterEach(() => {
    if (global.fetch.mockRestore) {
      global.fetch.mockRestore();
    }
  });

  test('shows up-to-date message when no update available', async () => {
    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          current_version: '1.0.0',
          latest_version: '1.0.0',
          update_available: false,
        }),
      })
    );

    render(<UpdateBanner />);
    expect(await screen.findByText(/you're up to date/i)).toBeInTheDocument();
    expect(screen.getByText(/v1\.0\.0/)).toBeInTheDocument();
  });

  test('shows update available message with docker pull command', async () => {
    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          current_version: '1.0.0',
          latest_version: '1.1.0',
          update_available: true,
          update_url: 'https://github.com/Driv-lingo/twhyne-ai/releases/tag/v1.1.0',
        }),
      })
    );

    render(<UpdateBanner />);
    expect(await screen.findByText(/v1\.1\.0/)).toBeInTheDocument();
    expect(screen.getByText('docker pull twhyne/twhyne:latest')).toBeInTheDocument();
    expect(screen.getByText('Release Notes')).toHaveAttribute('href', 'https://github.com/Driv-lingo/twhyne-ai/releases/tag/v1.1.0');
  });

  test('renders nothing when API is unreachable', async () => {
    global.fetch = jest.fn(() => Promise.reject(new Error('Network error')));

    const { container } = render(<UpdateBanner />);
    // Wait for the fetch to complete
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    // Banner should not render
    expect(container.querySelector('.update-banner')).toBeNull();
  });

  test('can be dismissed', async () => {
    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          current_version: '1.0.0',
          latest_version: '1.0.0',
          update_available: false,
        }),
      })
    );

    const { container } = render(<UpdateBanner />);
    expect(await screen.findByText(/you're up to date/i)).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText('Dismiss update banner'));
    expect(container.querySelector('.update-banner')).toBeNull();
  });

  test('has a check for updates button', async () => {
    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          current_version: '1.0.0',
          latest_version: '1.0.0',
          update_available: false,
        }),
      })
    );

    render(<UpdateBanner />);
    expect(await screen.findByText(/you're up to date/i)).toBeInTheDocument();
    const checkBtn = screen.getByLabelText('Check for updates');
    expect(checkBtn).toBeInTheDocument();
    fireEvent.click(checkBtn);
    // fetch called twice: once on mount, once on click
    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(2));
  });
});
