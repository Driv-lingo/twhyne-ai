import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
// Make sure we import jest-dom explicitly in the test file
import '@testing-library/jest-dom';
import axios from 'axios';
import MockAdapter from 'axios-mock-adapter';
import WrappedApp from '../App';

// Add a Jest setup to extend expect with DOM matchers
declare global {
  namespace jest {
    interface Matchers<R> {
      toBeInTheDocument(): R;
    }
  }
}

const mock = new MockAdapter(axios);

describe('Chat multi-turn and continue', () => {
  afterEach(() => mock.reset());

  it('renders 3-turn chat and continue, with 4 bubbles and last non-empty', async () => {
    // Mock backend responses
    mock.onPost('/chat').replyOnce(200, { response: 'Assistant reply 1' });
    mock.onPost('/chat').replyOnce(200, { response: 'Assistant reply 2' });
    mock.onPost('/chat').replyOnce(200, { response: 'Assistant reply 3' });
    mock.onPost('/chat').replyOnce(200, { response: 'Continued reply' });

    render(<WrappedApp />);

    // Send first user message
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Hi' } });
    fireEvent.click(screen.getByText(/send/i));
    await waitFor(() => expect(screen.getByText('Assistant reply 1')).toBeInTheDocument());

    // Send second user message
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'How are you?' } });
    fireEvent.click(screen.getByText(/send/i));
    await waitFor(() => expect(screen.getByText('Assistant reply 2')).toBeInTheDocument());

    // Send third user message
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Tell me a joke.' } });
    fireEvent.click(screen.getByText(/send/i));
    await waitFor(() => expect(screen.getByText('Assistant reply 3')).toBeInTheDocument());

    // Click Continue
    fireEvent.click(screen.getByText(/continue generating/i));
    await waitFor(() => expect(screen.getByText('Continued reply')).toBeInTheDocument());

    // There should be 4 assistant bubbles rendered
    const bubbles = screen.getAllByText(/assistant/i, { selector: '.chat-bubble.assistant *' });
    expect(bubbles.length).toBeGreaterThanOrEqual(4);
    // Last bubble is not empty
    expect(screen.getByText('Continued reply')).toBeInTheDocument();
  });
});
