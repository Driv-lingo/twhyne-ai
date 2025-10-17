import React, { createContext, useContext, useState } from 'react';

export interface ChatTurn {
  role: 'user' | 'assistant';
  content: string;
  ts: number;
  node: string;
}

interface ChatHistoryContextProps {
  history: ChatTurn[];
  addTurn: (turn: ChatTurn) => void;
  clearHistory: () => void;
}

const ChatHistoryContext = createContext<ChatHistoryContextProps | undefined>(undefined);

// Use 'any' for children to avoid React type issues in all environments
export function ChatHistoryProvider(props: { children: any }) {
  const [history, setHistory] = useState<ChatTurn[]>([]);
  const addTurn = (turn: ChatTurn) => setHistory(prev => [...prev, turn]);
  const clearHistory = () => setHistory([]);
  return (
    <ChatHistoryContext.Provider value={{ history, addTurn, clearHistory }}>
      {props.children}
    </ChatHistoryContext.Provider>
  );
}

export function useChatHistory() {
  const ctx = useContext(ChatHistoryContext);
  if (!ctx) throw new Error('useChatHistory must be used within ChatHistoryProvider');
  return ctx;
}
