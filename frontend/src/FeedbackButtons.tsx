import React, { useState } from 'react';

interface FeedbackButtonsProps {
  prompt: string;
  response: string;
  onFeedbackSent?: (rating: number, edit?: string) => void;
}

export const FeedbackButtons: React.FC<FeedbackButtonsProps> = ({ prompt, response, onFeedbackSent }) => {
  const [feedback, setFeedback] = useState<'up' | 'down' | 'edit' | null>(null);
  const [editValue, setEditValue] = useState('');
  const [editing, setEditing] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sendFeedback = async (rating: number, edit?: string) => {
    setSending(true);
    setError(null);
    setFeedback(rating === 1 ? 'up' : rating === -1 ? 'down' : 'edit');
    if (onFeedbackSent) onFeedbackSent(rating, edit);
    try {
      await fetch('/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt, response, rating, edit: edit || null })
      });
    } catch (e) {
      setError('Failed to send feedback');
    }
    setSending(false);
    setEditing(false);
    setEditValue('');
  };

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <button
        aria-label="Thumbs up"
        disabled={sending}
        style={{ color: feedback === 'up' ? 'green' : undefined }}
        onClick={() => sendFeedback(1)}
      >👍</button>
      <button
        aria-label="Thumbs down"
        disabled={sending}
        style={{ color: feedback === 'down' ? 'red' : undefined }}
        onClick={() => sendFeedback(-1)}
      >👎</button>
      <button
        aria-label="Edit answer"
        disabled={sending}
        style={{ color: feedback === 'edit' ? 'orange' : undefined }}
        onClick={() => setEditing(true)}
      >✏️</button>
      {editing && (
        <form
          style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}
          onSubmit={e => {
            e.preventDefault();
            sendFeedback(0, editValue);
          }}
        >
          <input
            type="text"
            value={editValue}
            onChange={e => setEditValue(e.target.value)}
            placeholder="Suggest a better answer"
            style={{ width: 180 }}
            disabled={sending}
            required
          />
          <button type="submit" disabled={sending}>Send</button>
          <button type="button" disabled={sending} onClick={() => { setEditing(false); setEditValue(''); }}>Cancel</button>
        </form>
      )}
      {error && <span style={{ color: 'red', marginLeft: 8 }}>{error}</span>}
    </div>
  );
};

export default FeedbackButtons;
