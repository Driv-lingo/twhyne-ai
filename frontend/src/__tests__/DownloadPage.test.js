import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import DownloadPage from '../components/DownloadPage';

describe('DownloadPage', () => {
  const mockNavigate = jest.fn();

  beforeEach(() => {
    mockNavigate.mockClear();
  });

  test('renders download page with title', () => {
    render(<DownloadPage onNavigate={mockNavigate} />);
    expect(screen.getByText('Download Twhyne AI')).toBeInTheDocument();
    expect(screen.getByText('Choose a package for your platform to get started')).toBeInTheDocument();
  });

  test('renders all download cards', () => {
    render(<DownloadPage onNavigate={mockNavigate} />);
    expect(screen.getByText('Docker (Recommended)')).toBeInTheDocument();
    expect(screen.getByText('Windows')).toBeInTheDocument();
    expect(screen.getByText('macOS')).toBeInTheDocument();
    expect(screen.getByText('Source Archive')).toBeInTheDocument();
  });

  test('renders docker pull command for Docker card', () => {
    render(<DownloadPage onNavigate={mockNavigate} />);
    const pullCommands = screen.getAllByText(/docker pull twhyne\/twhyne:latest/);
    expect(pullCommands.length).toBeGreaterThanOrEqual(1);
  });

  test('renders download links with correct attributes', () => {
    render(<DownloadPage onNavigate={mockNavigate} />);
    const downloadButtons = screen.getAllByText('Download');
    expect(downloadButtons.length).toBeGreaterThanOrEqual(2);
    downloadButtons.forEach(btn => {
      expect(btn.closest('a')).toHaveAttribute('target', '_blank');
      expect(btn.closest('a')).toHaveAttribute('rel', 'noopener noreferrer');
    });
  });

  test('renders update instructions section', () => {
    render(<DownloadPage onNavigate={mockNavigate} />);
    expect(screen.getByText('How Clients Get Updates')).toBeInTheDocument();
    expect(screen.getByText('Pull the latest image')).toBeInTheDocument();
    expect(screen.getByText('Restart the container')).toBeInTheDocument();
  });

  test('shows docker compose command in update steps', () => {
    render(<DownloadPage onNavigate={mockNavigate} />);
    expect(screen.getByText('docker compose up -d')).toBeInTheDocument();
  });

  test('navigates back to app', () => {
    render(<DownloadPage onNavigate={mockNavigate} />);
    fireEvent.click(screen.getByText('← Back to App'));
    expect(mockNavigate).toHaveBeenCalledWith('app');
  });

  test('navigates to sign-up page', () => {
    render(<DownloadPage onNavigate={mockNavigate} />);
    fireEvent.click(screen.getByText('Create Account'));
    expect(mockNavigate).toHaveBeenCalledWith('signup');
  });

  test('shows file names for downloadable packages', () => {
    render(<DownloadPage onNavigate={mockNavigate} />);
    expect(screen.getByText('SNF-AI-Windows.zip')).toBeInTheDocument();
    expect(screen.getByText('SNF-AI-Mac.zip')).toBeInTheDocument();
    expect(screen.getByText('SNF-AI-Windsurf-3.0.0.zip')).toBeInTheDocument();
  });
});
