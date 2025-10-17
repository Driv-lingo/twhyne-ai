import React, { createContext, useContext, useState } from 'react';

// ChatTurn interface:
// - role: 'user' | 'assistant'
// - content: string
// - ts: number (timestamp)
// - node: string (node type that processed the message)

const ChatHistoryContext = createContext(undefined);

// ChatHistoryProvider manages the chat history state
export function ChatHistoryProvider(props) {
  const [history, setHistory] = useState([]);
  
  // Add a new turn to the chat history
  const addTurn = (turn) => setHistory(prev => [...prev, turn]);
  
  // Clear the entire chat history
  const clearHistory = () => setHistory([]);
  
  return (
    <ChatHistoryContext.Provider value={{ history, addTurn, clearHistory }}>
      {props.children}
    </ChatHistoryContext.Provider>
  );
}

// Hook to access the chat history context
export function useChatHistory() {
  const ctx = useContext(ChatHistoryContext);
  if (!ctx) throw new Error('useChatHistory must be used within ChatHistoryProvider');
  return ctx;
}
