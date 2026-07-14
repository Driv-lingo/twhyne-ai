// Copyright (c) 2025 Twhyne AI
// SPDX-License-Identifier: MIT

import React, { useState, useEffect, useCallback, useRef } from 'react';
import ReactFlow, {
  useNodesState,
  useEdgesState,
  Background,
  Controls,
  MiniMap
} from 'reactflow';
import 'reactflow/dist/style.css';
import './App.css';
import './modern-theme.css';
import './twhyne-theme.css';
import axios from 'axios';
import CustomNode from './components/CustomNode';
import FeedbackButtons from './components/FeedbackButtons';
import ConversationManager from './components/ConversationManager';
import './components/ConversationManager.css';
import RAGManager from './components/RAGManager';
import { TrustStrip, MessageBody } from './components/TrustLayer';
import './components/RAGManager.css';
import { 
  FaCode, 
  FaCalculator, 
  FaImage, 
  FaProjectDiagram, 
  FaServer,
  FaInfoCircle,
  FaTrash,
  FaKeyboard,
  FaQuestion,
  FaLightbulb
} from 'react-icons/fa';

// Suppress ResizeObserver error
const originalError = console.error;
const originalWarn = console.warn;
console.error = (...args) => {
  if (args[0]?.includes?.('ResizeObserver loop completed with undelivered notifications')) {
    return;
  }
  originalError(...args);
};
console.warn = (...args) => {
  if (args[0]?.includes?.('ResizeObserver loop completed with undelivered notifications')) {
    return;
  }
  originalWarn(...args);
};

// Additional ResizeObserver error suppression
window.addEventListener('error', (event) => {
  if (event.message?.includes('ResizeObserver loop completed with undelivered notifications')) {
    event.preventDefault();
    return false;
  }
});

window.addEventListener('unhandledrejection', (event) => {
  if (event.reason?.message?.includes('ResizeObserver loop completed with undelivered notifications')) {
    event.preventDefault();
    return false;
  }
});

// Error boundary for React Flow
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    // Don't show error boundary for ResizeObserver errors
    if (error.message?.includes('ResizeObserver loop completed with undelivered notifications')) {
      return { hasError: false };
    }
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    // Suppress ResizeObserver errors
    if (error.message?.includes('ResizeObserver loop completed with undelivered notifications')) {
      return;
    }
    console.log('React Flow Error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError && !this.state.error?.message?.includes('ResizeObserver')) {
      return <div>Node visualization temporarily unavailable</div>;
    }
    return this.props.children;
  }
}

// Define node types for ReactFlow
const nodeTypes = {
  customNode: CustomNode
};

// Tooltips for node types
const nodeTooltips = {
  language: "Natural language processing for general queries and conversations",
  code: "Code generation, analysis, and programming assistance",
  math: "Mathematical computation and equation solving",
  vision: "Image understanding and visual content analysis",
  planner: "Task planning and workflow decomposition",
  claude: "Not available - Twhyne runs fully local"
};

function App() {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [query, setQuery] = useState('');
  const [history, setHistory] = useState([]);
  const [response, setResponse] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  // Request tracking: cancelling must invalidate the in-flight request so a
  // late-arriving response can never attach to a later question (this caused
  // an off-by-one where every answer landed under the wrong message).
  const requestIdRef = useRef(0);
  const activeRequestRef = useRef(null);
  const abortRef = useRef(null);
  const activeClientIdRef = useRef(null);
  const [progressText, setProgressText] = useState('');
  const [selectedNode, setSelectedNode] = useState(null);
  const [nodeStatus, setNodeStatus] = useState({});
  const [useRemote, setUseRemote] = useState(false);
  const [file, setFile] = useState(null);
  const [feedbackSent, setFeedbackSent] = useState(false);
  const [showHelp, setShowHelp] = useState(false);
  const [processingNode, setProcessingNode] = useState(null);
  const [currentConversation, setCurrentConversation] = useState(null);
  const messagesEndRef = useRef(null);
  const queryInputRef = useRef(null);
  
  // Fix ResizeObserver error
  useEffect(() => {
    const resizeObserverErrorHandler = (e) => {
      if (e.message === 'ResizeObserver loop completed with undelivered notifications.' ||
          e.message === 'ResizeObserver loop limit exceeded') {
        e.stopImmediatePropagation();
      }
    };
    window.addEventListener('error', resizeObserverErrorHandler);
    return () => window.removeEventListener('error', resizeObserverErrorHandler);
  }, []);

  // Help overlay state
  const [showHelpOverlay, setShowHelpOverlay] = useState(false);
  const [graphCollapsed, setGraphCollapsed] = useState(() => {
    try { return localStorage.getItem('twhyne_graph_collapsed') === '1'; } catch (e) { return false; }
  });
  const toggleGraph = () => setGraphCollapsed(v => {
    const nv = !v;
    try { localStorage.setItem('twhyne_graph_collapsed', nv ? '1' : '0'); } catch (e) {}
    return nv;
  });
  
  // Toggle help overlay
  const toggleHelp = () => {
    setShowHelpOverlay(!showHelpOverlay);
  };
  
  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyPress = (e) => {
      // Ctrl+Enter to submit query
      if (e.ctrlKey && e.key === 'Enter') {
        handleSubmit();
      }
      
      // Esc to cancel operation
      if (e.key === 'Escape' && isLoading) {
        handleCancel();
      }
      
      // Alt+C to clear history
      if (e.altKey && e.key === 'c') {
        handleClearHistory();
      }
      
      // Alt+H to toggle help
      if (e.altKey && e.key === 'h') {
        toggleHelp();
      }
    };
    
    document.addEventListener('keydown', handleKeyPress);
    return () => {
      document.removeEventListener('keydown', handleKeyPress);
    };
  }, [isLoading]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      // Escape to close help if open
      if (e.key === 'Escape' && showHelpOverlay) {
        setShowHelpOverlay(false);
      }
    };
    
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [showHelpOverlay]);

  // Poll backend progress while a request is running, so the loading bubble
  // says WHAT is happening ("retrieving documents", "generating - code")
  // instead of showing a silent spinner during multi-minute generations.
  useEffect(() => {
    if (!isLoading) {
      setProgressText('');
      return;
    }
    const iv = setInterval(async () => {
      try {
        const r = await axios.get('http://127.0.0.1:5002/progress');
        const { state, detail } = r.data || {};
        if (state && state !== 'idle') {
          setProgressText(detail ? `${state} — ${detail}` : state);
        }
      } catch (e) { /* keep last text if the poll fails */ }
    }, 2000);
    return () => clearInterval(iv);
  }, [isLoading]);

  // Governed timers (layer 9 v0.1). Timers fire at READ time: the backend
  // computes their state from the clock only when the list is observed.
  // This poll is the user's client observing on their behalf — the system
  // itself never acts between reads.
  const [timers, setTimers] = useState([]);
  const seenElapsedRef = useRef(new Set());
  const firstTimerPollRef = useRef(true);
  useEffect(() => {
    let alive = true;
    const poll = async () => {
      try {
        const r = await axios.get('http://127.0.0.1:5002/api/timers');
        if (!alive) return;
        const list = (r.data && r.data.timers) || [];
        setTimers(list);
        if (firstTimerPollRef.current) {
          // Anything already elapsed before this session opened is STALE:
          // acknowledge silently, never announce it. Announcements are only
          // for elapses observed live in this session.
          firstTimerPollRef.current = false;
          list.forEach(t => {
            if (t.status === 'elapsed') seenElapsedRef.current.add(t.id);
          });
          return;
        }
        list.forEach(t => {
          if (t.status === 'elapsed' && !seenElapsedRef.current.has(t.id)) {
            seenElapsedRef.current.add(t.id);
            setHistory(h => [...h, {
              role: 'system',
              content: `⏱ Timer elapsed: ${t.label || t.id} (observed just now — read-time firing)`
            }]);
          }
        });
      } catch (e) { /* backend down; try again next tick */ }
    };
    poll();
    const iv = setInterval(poll, 5000);
    // 1s re-render so pending countdowns tick smoothly between polls
    // (display only — the authoritative state transition happens server-side
    // at read time).
    const tick = setInterval(() => setTimers(ts => ts.length ? [...ts] : ts), 1000);
    return () => { alive = false; clearInterval(iv); clearInterval(tick); };
  }, []);
  const dismissTimer = async (id) => {
    try { await axios.delete(`http://127.0.0.1:5002/api/timers/${id}`); } catch (e) {}
    setTimers(ts => ts.map(t => t.id === id ? { ...t, status: 'cancelled' } : t));
  };
  // Strip shows live timers only: pending, or elapsed within the last ten
  // minutes. Stale elapsed timers neither render nor notify — they remain
  // queryable ("check my timers") and in the audit ledger, but the UI never
  // nags about the past.
  const visibleTimers = timers.filter(
    t => t.status === 'pending' ||
      (t.status === 'elapsed' && Date.now() - (t.fired_at || 0) * 1000 < 600000));

  // Scroll to bottom of chat
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [history]);

  // Fetch node status
  const fetchNodeStatus = useCallback(async () => {
    try {
      const res = await axios.get('http://127.0.0.1:5002/nodes');
      const nodeList = res.data;
      
      // Convert node list to object for easier lookup
      const nodeData = {};
      nodeList.forEach(node => {
        nodeData[node.node_id] = node;
      });
      
      setNodeStatus(nodeData);
      
      // Create nodes for visualization
      const flowNodes = [];
      const flowEdges = [];
      
      // Add kernel node at the center
      flowNodes.push({
        id: 'kernel',
        type: 'customNode',
        data: { 
          label: 'Flux Kernel',
          type: 'kernel',
          status: 'online',
          description: 'Central router',
          tooltip: 'Routes queries to appropriate expert nodes'
        },
        position: { x: 200, y: 200 },
      });
      
      // Add expert nodes around the kernel - adjusted positions to prevent cutoff
      // The code node id depends on which model is installed (Qwen default,
      // CodeLlama legacy), so resolve it from the live node list.
      const codeNodeId = Object.keys(nodeData).find(id => id.startsWith('code-')) || 'code-qwen-coder-7b';
      const expertNodes = [
        { id: 'language-mistral-7b', label: 'Language', type: 'language', position: { x: 50, y: 50 } },
        { id: codeNodeId, label: 'Code', type: 'code', position: { x: 350, y: 50 } },
        { id: 'math-llm-eval', label: 'Math', type: 'math', position: { x: 50, y: 350 } },
        { id: 'vision-llava-1.6-7b', label: 'Vision', type: 'vision', position: { x: 350, y: 350 } },
        { id: 'planner-mistral-7b', label: 'Planner', type: 'planner', position: { x: 380, y: 200 } }
      ];
      
      expertNodes.forEach(node => {
        const nd = nodeData[node.id];
        const status = nd ? nd.status : 'offline';
        flowNodes.push({
          id: node.id,
          type: 'customNode',
          data: {
            label: node.label,
            type: node.type,
            status: status,
            description: `${node.label} expert`,
            // Nielsen: visibility of system status - when a node is offline,
            // say WHY (e.g. "model not downloaded - re-run the launcher").
            statusDetail: nd && nd.status_detail ? nd.status_detail : null,
            tooltip: nodeTooltips[node.type],
            isProcessing: processingNode === node.id
          },
          position: node.position,
        });

        // Add edge from kernel to this node
        flowEdges.push({
          id: `kernel-to-${node.id}`,
          source: 'kernel',
          target: node.id,
          animated: processingNode === node.id
        });
      });
      
      
      setNodes(flowNodes);
      setEdges(flowEdges);
    } catch (error) {
      console.error('Error fetching node status:', error);
      console.error('Error details:', error.response?.data || error.message);
      // Only set nodes offline for actual network errors
      if (error.code === 'ECONNREFUSED' || error.code === 'NETWORK_ERROR') {
        setNodeStatus({});
      } else {
        // For other errors, keep trying but log the issue
        console.warn('API error but keeping current node status');
        return;
      }
      
      // Create offline nodes for visualization
      const flowNodes = [];
      const flowEdges = [];
      
      // Add kernel node at the center (offline)
      flowNodes.push({
        id: 'kernel',
        type: 'customNode',
        data: { 
          label: 'Flux Kernel',
          type: 'kernel',
          status: 'offline',
          description: 'Network error',
          tooltip: 'Cannot connect to API server'
        },
        position: { x: 200, y: 200 },
      });
      
      // Add expert nodes (all offline) - adjusted positions to prevent cutoff
      const expertNodes = [
        { id: 'language-mistral-7b', label: 'Language', type: 'language', position: { x: 50, y: 50 } },
        { id: 'code-qwen-coder-7b', label: 'Code', type: 'code', position: { x: 350, y: 50 } },
        { id: 'math-llm-eval', label: 'Math', type: 'math', position: { x: 50, y: 350 } },
        { id: 'vision-llava-1.6-7b', label: 'Vision', type: 'vision', position: { x: 350, y: 350 } },
        { id: 'planner-mistral-7b', label: 'Planner', type: 'planner', position: { x: 380, y: 200 } }
      ];
      
      expertNodes.forEach(node => {
        flowNodes.push({
          id: node.id,
          type: 'customNode',
          data: { 
            label: node.label, 
            type: node.type,
            status: 'offline',
            description: `${node.label} expert`,
            tooltip: 'API server not reachable'
          },
          position: node.position,
        });

        // Add edge from kernel to this node
        flowEdges.push({
          id: `kernel-to-${node.id}`,
          source: 'kernel',
          target: node.id,
          animated: false
        });
      });
      
      setNodes(flowNodes);
      setEdges(flowEdges);
    }
  }, [setNodes, setEdges, processingNode]);
  
  // Initial fetch
  useEffect(() => {
    fetchNodeStatus();
    const interval = setInterval(fetchNodeStatus, 5000);
    return () => clearInterval(interval);
  }, [fetchNodeStatus]);
  
  // Handle file selection
  const handleFileChange = (e) => {
    if (e.target.files.length > 0) {
      setFile(e.target.files[0]);
    }
  };
  
  // Handle query submission
  const handleSubmit = async () => {
    if ((!query.trim() && !file) || isLoading) return;

    const myRequestId = ++requestIdRef.current;
    activeRequestRef.current = myRequestId;
    abortRef.current = new AbortController();
    const signal = abortRef.current.signal;
    // Backend-visible id: lets Cancel skip this job if it is still queued.
    const clientRequestId = `${Date.now()}-${myRequestId}`;
    activeClientIdRef.current = clientRequestId;

    const userQuery = query; // Save query before clearing
    const userTurn = {
      role: 'user',
      content: userQuery
    };
    
    // Update UI state immediately for instant feedback
    setIsLoading(true);
    setFeedbackSent(false);
    setHistory(prev => [...prev, userTurn]);
    setQuery('');
    
    // Small delay to ensure React renders the UI updates
    await new Promise(resolve => setTimeout(resolve, 0));
    
    try {
      let endpoint;
      let payload;
      let uploadedFilePath = null;
      // Create form data if file is attached
      if (file) {
        // Use upload endpoint for file uploads
        endpoint = 'http://127.0.0.1:5002/upload';
        const formData = new FormData();
        formData.append('file', file); // Ensure key is 'file' to match backend expectation
        formData.append('prompt', userQuery);
        // Add conversation history for context
        formData.append('conversation_history', JSON.stringify(history));
        // Only add node_id if a specific node is selected
        if (selectedNode) {
          formData.append('node_id', selectedNode);
        }
        payload = formData;
        // Make upload request
        const uploadRes = await axios.post(endpoint, payload, { headers: { 'Content-Type': 'multipart/form-data' }, signal });
        uploadedFilePath = uploadRes.data.filepath;
        setFile(null); // Clear the file after upload
        // Now make a query request with the uploaded file path
        endpoint = 'http://127.0.0.1:5002/query';
        payload = {
          prompt: userQuery,
          image_path: uploadedFilePath,
          conversation_history: history,
          client_request_id: clientRequestId
        };
        if (selectedNode) {
          payload.node_id = selectedNode;
        }
        const queryRes = await axios.post(endpoint, payload, {
          headers: {
            'Content-Type': 'application/json'
          },
          signal
        });
        // Discard if this request was cancelled while in flight.
        if (activeRequestRef.current !== myRequestId) return;
        const assistantTurn = {
          role: 'assistant',
          content: queryRes.data.response,
          node: queryRes.data.node_id,
          gates: queryRes.data.gates,
          sources: queryRes.data.sources,
          evidence: queryRes.data.evidence,
        };
        setHistory(prev => [...prev, assistantTurn]);
        setResponse(queryRes.data.response);
      } else {
        // Use query endpoint for text-only queries
        endpoint = 'http://127.0.0.1:5002/query';
        payload = {
          prompt: userQuery,
          conversation_history: history,
          client_request_id: clientRequestId
        };
        // Only add node_id if a specific node is selected
        if (selectedNode) {
          payload.node_id = selectedNode;
        }
        const res = await axios.post(endpoint, payload, {
          headers: {
            'Content-Type': 'application/json'
          },
          signal
        });
        // Discard if this request was cancelled while in flight.
        if (activeRequestRef.current !== myRequestId) return;
        const assistantTurn = {
          role: 'assistant',
          content: res.data.response,
          node: res.data.node_id,
          gates: res.data.gates,
          sources: res.data.sources,
          evidence: res.data.evidence,
        };
        setHistory(prev => [...prev, assistantTurn]);
        setResponse(res.data.response);
      }
    } catch (err) {
      // A cancelled/stale request must not write anything to the chat.
      if (activeRequestRef.current !== myRequestId || axios.isCancel?.(err) || err.name === 'CanceledError') return;
      console.error('Error submitting query:', err);
      console.error('Error details:', err.response?.data || err.message);
      let errorMessage;
      if (err.response && err.response.data && err.response.data.error) {
        errorMessage = `Error: ${err.response.data.error}. Try a different node or query.`;
      } else if (err.message.includes('Network Error')) {
        errorMessage = 'Network error: Please check that the API server is running.';
      } else {
        errorMessage = `Error: ${err.message || 'Unknown error occurred'}. Try a different node or query.`;
      }
      
      setResponse(errorMessage);
      // Add error message to history
      setHistory(prev => [...prev, {
        role: 'system',
        content: errorMessage,
        error: true
      }]);
    } finally {
      if (activeRequestRef.current === myRequestId) setIsLoading(false);
    }
  };
  
  // Handle continue request
  const handleContinue = async () => {
    if (history.length === 0 || isLoading) return;

    const myRequestId = ++requestIdRef.current;
    activeRequestRef.current = myRequestId;
    abortRef.current = new AbortController();
    const signal = abortRef.current.signal;
    const clientRequestId = `${Date.now()}-${myRequestId}`;
    activeClientIdRef.current = clientRequestId;

    setIsLoading(true);
    setFeedbackSent(false);
    
    try {
      const lastAssistantMessage = history.filter(msg => msg.role === 'assistant').pop();
      const activeNodeId = lastAssistantMessage?.node || 'language';
      
      // Set processing node for visualization
      setProcessingNode(activeNodeId);
      
      const res = await axios.post('http://127.0.0.1:5002/query', {
        prompt: 'Please continue your previous response.',
        conversation_history: history,
        node_id: activeNodeId,
        client_request_id: clientRequestId
      }, { signal });

      // Discard if this request was cancelled while in flight.
      if (activeRequestRef.current !== myRequestId) return;
      const assistantTurn = {
        role: 'assistant',
        content: res.data.result || res.data.response,
        node: res.data.node_id || activeNodeId,
        gates: res.data.gates,
        sources: res.data.sources,
        evidence: res.data.evidence,
      };
      
      setHistory(prev => [...prev, assistantTurn]);
      
    } catch (err) {
      if (activeRequestRef.current !== myRequestId || axios.isCancel?.(err) || err.name === 'CanceledError') return;
      let errorMessage;
      if (err.response && err.response.status === 503) {
        errorMessage = 'The language service is currently starting up. Please try again in a few seconds.';
      } else if (err.message.includes('Network Error')) {
        errorMessage = 'Network error: Please check that the API server is running.';
      } else {
        errorMessage = `Error: ${err.message || 'Unknown error occurred'}. Try a different query.`;
      }
      
      setResponse(errorMessage);
      
      // Add error message to history
      setHistory(prev => [...prev, {
        role: 'system',
        content: errorMessage,
        error: true
      }]);
    } finally {
      if (activeRequestRef.current === myRequestId) {
        setIsLoading(false);
        setProcessingNode(null);
      }
    }
  };
  
  // Handle feedback submission
  const handleFeedback = async (isPositive) => {
    try {
      await axios.post('http://127.0.0.1:5002/feedback', {
        positive: isPositive,
        feedback: isPositive ? 'positive' : 'negative'
      });
      setFeedbackSent(true);
    } catch (error) {
      console.error('Error sending feedback:', error);
    }
  };
  
  // Handle cancel operation
  const handleCancel = () => {
    if (!isLoading) return;

    // Invalidate the in-flight request so its response is DISCARDED when it
    // eventually arrives (never attached to a later question), and abort the
    // HTTP request client-side. The backend may still finish computing the
    // abandoned answer; it just goes nowhere.
    activeRequestRef.current = null;
    if (abortRef.current) {
      try { abortRef.current.abort(); } catch (e) { /* already settled */ }
    }
    // Tell the backend so a still-queued job is skipped, not computed.
    if (activeClientIdRef.current) {
      axios.post('http://127.0.0.1:5002/cancel',
        { client_request_id: activeClientIdRef.current }).catch(() => {});
    }
    setIsLoading(false);
    setProcessingNode(null);
    
    // Add cancellation message to history
    setHistory(prev => [...prev, {
      role: 'system',
      content: 'Operation cancelled by user.',
      error: true
    }]);
  };
  
  // Handle clear history
  const handleClearHistory = () => {
    if (isLoading) return;
    
    setHistory([]);
    setResponse('');
    setProcessingNode(null);
    setCurrentConversation(null);
  };
  
  // Conversation management handlers
  const handleLoadConversation = (conversation) => {
    setHistory(conversation.messages || []);
    setCurrentConversation(conversation);
    setResponse('');
    setProcessingNode(null);
  };
  
  const handleNewConversation = () => {
    setHistory([]);
    setResponse('');
    setProcessingNode(null);
    setCurrentConversation(null);
  };
  
  const handleDeleteConversation = (id) => {
    if (currentConversation?.id === id) {
      handleNewConversation();
    }
  };
  
  // Example queries - using auto-routing
  const exampleQueries = [
    { text: "Write a function to calculate Fibonacci numbers", node: null, icon: <FaCode /> },
    { text: "Solve the quadratic equation x² + 5x + 6 = 0", node: null, icon: <FaCalculator /> },
    { text: "Create a task plan for building a todo app", node: null, icon: <FaProjectDiagram /> },
    { text: "What can you tell me about this image?", node: null, icon: <FaImage /> },
    { text: "Explain quantum computing concepts", node: null, icon: <FaServer /> }
  ];
  
  const handleExampleQuery = (query, node) => {
    setQuery(query);
    setSelectedNode(node);
    
    // Focus the query input
    queryInputRef.current?.focus();
  };

  // Handle RAG node creation
  const handleRAGNodeCreated = (dataset) => {
    // Refresh node status to include new RAG node
    fetchNodeStatus();
  };

  return (
    <div className="app">
      {/* Conversation Manager */}
      <ConversationManager
        currentConversation={currentConversation}
        onLoadConversation={handleLoadConversation}
        onNewConversation={handleNewConversation}
        onDeleteConversation={handleDeleteConversation}
        currentHistory={history}
      />
      
      {/* RAG Manager */}
      <RAGManager onNodeCreated={handleRAGNodeCreated} />
      
      <header className="header">
          <div className="logo">
          <h1><span className="highlight">Twhyne</span></h1>
          <div className="subtitle">Local-first verified AI &mdash; permissioned &amp; auditable</div>
            </div>
        <div className="status-bar">
          <div className="status-item">
            <span className="status-label">API:</span>
            <span className="status-value online">Connected</span>
          </div>
          <div className="status-item">
            <span className="status-label">Nodes:</span>
            <span className="status-value">{Object.values(nodeStatus).filter(n => n.status === 'online').length} Online</span>
        </div>
          <div className="help-button" onClick={() => setShowHelpOverlay(!showHelpOverlay)} aria-label="Help">
            <FaQuestion />
          </div>
        </div>
      </header>
      
      {showHelpOverlay && (
        <div className="help-overlay">
          <div className="help-content">
            <h2>Twhyne Help</h2>
            <button className="close-help" onClick={() => setShowHelpOverlay(false)}>×</button>
            
            <h3>What is Twhyne?</h3>
            <p>Twhyne routes every question to the cheapest capability that can answer it verifiably - exact math, a quoted document span, verified code, or a local model - under your roles and permissions, with a tamper-evident audit trail. Nothing leaves your machine.</p>
            
            <h3>Expert Nodes</h3>
            <div className="help-nodes">
              <div className="help-node">
                <div className="node-icon language">L</div>
                <div className="node-info">
                  <h4>Language</h4>
                  <p>Mistral-7B for grounded answers, synthesis and summaries</p>
                </div>
              </div>
              <div className="help-node">
                <div className="node-icon code">C</div>
                <div className="node-info">
                  <h4>Code</h4>
                  <p>Qwen2.5-Coder-7B for verified programming and code generation</p>
                </div>
              </div>
              <div className="help-node">
                <div className="node-icon math">M</div>
                <div className="node-info">
                  <h4>Math</h4>
                  <p>SymPy symbolic engine - exact answers, zero model time</p>
                </div>
              </div>
              <div className="help-node">
                <div className="node-icon vision">V</div>
                <div className="node-info">
                  <h4>Vision</h4>
                  <p>LLaVA-1.6-7B for image analysis</p>
                </div>
              </div>
              <div className="help-node">
                <div className="node-icon planner">P</div>
                <div className="node-info">
                  <h4>Planner</h4>
                  <p>Mistral-7B for planning and task decomposition</p>
                </div>
              </div>
              <div className="help-node">
                <div className="node-icon planner">+</div>
                <div className="node-info">
                  <h4>Your models</h4>
                  <p>Import any Hugging Face GGUF as a governed node with its own role permissions (admin console)</p>
                </div>
              </div>
            </div>
            
            <h3>Example Queries</h3>
            <div className="help-examples">
              {exampleQueries.map((eq, index) => (
                <button
                  key={index}
                  className={`example-query ${eq.node}`}
                  onClick={() => {
                    handleExampleQuery(eq.text, eq.node);
                    setShowHelpOverlay(false);
                  }}
                  disabled={isLoading}
                  title={nodeTooltips[eq.node]}
                >
                  <span className="query-icon">{eq.icon}</span>
                  <span className="query-text">{eq.text}</span>
                </button>
              ))}
            </div>
            
            <h3>Keyboard Shortcuts</h3>
            <div className="shortcuts">
              <div className="shortcut">
                <kbd>Ctrl</kbd> + <kbd>Enter</kbd>
                <span>Submit query</span>
              </div>
              <div className="shortcut">
                <kbd>Alt</kbd> + <kbd>H</kbd>
                <span>Toggle help</span>
              </div>
              <div className="shortcut">
                <kbd>Alt</kbd> + <kbd>C</kbd>
                <span>Clear history</span>
              </div>
              <div className="shortcut">
                <kbd>Esc</kbd>
                <span>Close help / Cancel</span>
              </div>
            </div>
          </div>
        </div>
      )}
      
      <div className="content">
        {/* Left panel with conversation */}
        <div className="left-panel">
          <div className="interaction-panel">
            {visibleTimers.length > 0 && (
              <div className="timer-strip" role="status" aria-label="Timers">
                {visibleTimers.map(t => {
                  const rem = Math.max(0, Math.round(t.due_at * 1000 - Date.now()) / 1000);
                  const mm = Math.floor(rem / 60), ss = Math.floor(rem % 60);
                  return (
                    <span key={t.id}
                          className={`timer-chip ${t.status}`}
                          title={t.status === 'pending'
                            ? 'Fires at read time: state is computed from the clock when checked'
                            : 'Elapsed (observed at last check)'}>
                      {t.status === 'pending'
                        ? `⏱ ${t.label || 'timer'} — ${mm}:${String(ss).padStart(2, '0')}`
                        : `⏱ ${t.label || 'timer'} — ELAPSED`}
                      <button className="timer-dismiss" aria-label="Dismiss timer"
                              onClick={() => dismissTimer(t.id)}>×</button>
                    </span>
                  );
                })}
              </div>
            )}
            {/* Chat history */}
            <div className="chat-history">
              <h3>
                {currentConversation ? currentConversation.name : 'New Conversation'}
                {history.length > 0 && (
                  <button 
                    className="clear-history-button" 
                    onClick={handleClearHistory}
                    aria-label="Clear conversation history"
                  >
                    <FaTrash />
                  </button>
                )}
              </h3>
              <div className="chat-messages">
              {history.length === 0 ? (
                  <div className="empty-history">
                  <p>Ask a question. Twhyne routes it to the right capability, checks the evidence, and labels each answer with how it was produced &mdash; computed exactly, cited from your documents, verified by running the code, or generated by a model.</p>
                  <div className="starter-chips">
                    {[
                      { t: 'What is 4,096 divided by 16?', h: 'exact math' },
                      { t: 'Write a function to reverse a linked list', h: 'verified code' },
                      { t: 'Summarize the key points of the uploaded document', h: 'cited answer' },
                    ].map((s, i) => (
                      <button key={i} className="starter-chip" onClick={() => { setQuery(s.t); }}>
                        <span className="starter-text">{s.t}</span>
                        <span className="starter-hint">{s.h}</span>
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                  history.map((msg, index) => (
                    <div key={index} className={`chat-bubble ${msg.role} ${msg.error ? 'error' : ''}`}>
                      <span className="chat-meta">
                        {msg.role === 'user' ? 'You' : msg.role === 'system' ? 'System' : 'Twhyne'}
                      </span>
                      {msg.role === 'assistant'
                        ? <MessageBody content={msg.content} />
                        : msg.content}
                      {msg.role === 'assistant' && (msg.gates || msg.node) && (
                        <TrustStrip node={msg.node} gates={msg.gates} sources={msg.sources} evidence={msg.evidence} />
                      )}
                  </div>
                ))
              )}
                {isLoading && (
                  <div className="chat-bubble assistant loading">
                    <span className="chat-meta">Twhyne {processingNode && `• ${processingNode} node`}{progressText && ` • ${progressText}`}</span>
                    <div className="typing-indicator">
                      <span></span>
                      <span></span>
                      <span></span>
                    </div>
                  </div>
                )}
              <div ref={messagesEndRef} />
            </div>
          </div>
            
            {/* Query input */}
            <div className="query-input">
              <textarea
                ref={queryInputRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Ask anything — it will be routed, verified, and labeled. (Enter to send, Shift+Enter for a new line)"
                disabled={isLoading}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                    e.preventDefault();
                    handleSubmit();
                  }
                }}
              />
              
              <div className="query-options">
                <div className="file-input">
                  <label htmlFor="file-input" title="Attach an image for vision analysis">
                    {file ? file.name : "Attach File"}
                  </label>
                  <input
                    type="file"
                    id="file-input"
                    onChange={handleFileChange}
                    disabled={isLoading}
                    accept="image/*"
                  />
                </div>
                

                <div className="keyboard-shortcut-hint">
                  <FaKeyboard />
                  <span>Enter to send · Shift+Enter for newline</span>
                </div>
                
                <button
                  className="process-button"
                  onClick={handleSubmit}
                  disabled={isLoading || (!query.trim() && !file)}
                  title="Send your query to Twhyne"
                >
                  {isLoading ? 'Processing...' : 'Send'}
                </button>
                
                {isLoading && (
                  <button
                    className="cancel-button"
                    onClick={handleCancel}
                    title="Cancel current operation"
                  >
                    Cancel
                  </button>
                )}
              </div>
            </div>
            
            {/* Feedback and continue */}
            {history.length > 0 && history[history.length - 1].role === 'assistant' && (
              <div className="response-actions">
                {!feedbackSent ? (
                  <>
                    <button className="feedback-btn" onClick={() => handleFeedback('positive')} title="Good response">👍</button>
                    <button className="feedback-btn" onClick={() => handleFeedback('negative')} title="Bad response">👎</button>
                  </>
                ) : null}
                
                {(() => {
                  const lastMsg = history[history.length - 1];
                  const content = lastMsg.content || '';
                  // Only show continue if response seems incomplete (doesn't end with proper punctuation and is reasonably long)
                  const seemsIncomplete = content.length > 50 && !content.trim().endsWith('.') && !content.trim().endsWith('!') && !content.trim().endsWith('?') && !content.trim().endsWith('...');
                  return seemsIncomplete ? (
                    <button
                      className="continue-btn"
                      onClick={handleContinue}
                      disabled={isLoading}
                      title="Continue the response"
                    >
                      Continue
                    </button>
                  ) : null;
                })()}
            </div>
            )}
          </div>
        </div>
        
        {/* Right panel with graph visualization */}
        <div className={`right-panel ${graphCollapsed ? 'collapsed' : ''}`}>
          <button className="graph-toggle" onClick={toggleGraph}
            title={graphCollapsed ? 'Show node activity' : 'Hide node activity'}
            aria-label={graphCollapsed ? 'Show node activity' : 'Hide node activity'}>
            {graphCollapsed ? '‹ nodes' : 'nodes ›'}
          </button>
          <div className="graph-container">
            <ErrorBoundary>
              <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                nodeTypes={nodeTypes}
                fitView
                fitViewOptions={{ padding: 0.2, includeHiddenNodes: false }}
                minZoom={0.5}
                maxZoom={1.5}
                defaultViewport={{ x: 0, y: 0, zoom: 0.8 }}
                proOptions={{ hideAttribution: true }}
                deleteKeyCode={null}
                multiSelectionKeyCode={null}
                selectionKeyCode={null}
                preventScrolling={false}
                nodesDraggable={false}
                nodesConnectable={false}
                elementsSelectable={false}
              >
                <Background color="#aaa" gap={16} />
                <Controls />
                <MiniMap
                  nodeStrokeColor={(n) => {
                    if (n.type === 'customNode') return '#fff';
                    return '#555';
                  }}
                  nodeColor={(n) => {
                    if (n.data.type === 'kernel') return '#004e92';
                    if (n.data.type === 'language') return '#1a2a6c';
                    if (n.data.type === 'code') return '#134e5e';
                    if (n.data.type === 'vision') return '#5f2c82';
                    if (n.data.type === 'math') return '#2c3e50';
                    if (n.data.type === 'planner') return '#4b6cb7';
                    if (n.data.type === 'claude') return '#6a11cb';
                    return '#666';
                  }}
                  maskColor="rgba(0,0,0,0.2)"
                />
              </ReactFlow>
            </ErrorBoundary>
          </div>
        </div>
      </div>
      
      <footer className="footer">
        <div>Twhyne • local-first • every answer computed, cited, verified, or refused</div>
      </footer>
    </div>
  );
}

export default App;
