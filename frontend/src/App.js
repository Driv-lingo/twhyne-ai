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
  claude: "Advanced reasoning via remote API (requires internet)"
};

function App() {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [query, setQuery] = useState('');
  const [history, setHistory] = useState([]);
  const [response, setResponse] = useState('');
  const [isLoading, setIsLoading] = useState(false);
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
      const expertNodes = [
        { id: 'language-mistral-7b', label: 'Language', type: 'language', position: { x: 50, y: 50 } },
        { id: 'code-codellama-7b', label: 'Code', type: 'code', position: { x: 350, y: 50 } },
        { id: 'math-llm-eval', label: 'Math', type: 'math', position: { x: 50, y: 350 } },
        { id: 'vision-llava-1.6-7b', label: 'Vision', type: 'vision', position: { x: 350, y: 350 } },
        { id: 'planner-mistral-7b', label: 'Planner', type: 'planner', position: { x: 380, y: 200 } }
      ];
      
      expertNodes.forEach(node => {
        const status = nodeData[node.id] ? nodeData[node.id].status : 'offline';
        flowNodes.push({
          id: node.id,
          type: 'customNode',
          data: { 
            label: node.label, 
            type: node.type,
            status: status,
            description: `${node.label} expert`,
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
      
      // Add Claude node if enabled
      if (useRemote) {
        flowNodes.push({
          id: 'claude',
          type: 'customNode',
          data: { 
            label: 'Claude', 
            type: 'claude',
            status: 'online',
            description: 'Remote expert',
            tooltip: nodeTooltips.claude
          },
          position: { x: 0, y: 200 },
        });
        
        flowEdges.push({
          id: 'kernel-to-claude',
          source: 'kernel',
          target: 'claude',
          animated: processingNode === 'claude'
        });
      }
      
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
        { id: 'code-codellama-7b', label: 'Code', type: 'code', position: { x: 350, y: 50 } },
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
  }, [setNodes, setEdges, useRemote, processingNode]);
  
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
        const uploadRes = await axios.post(endpoint, payload, { headers: { 'Content-Type': 'multipart/form-data' } });
        uploadedFilePath = uploadRes.data.filepath;
        setFile(null); // Clear the file after upload
        // Now make a query request with the uploaded file path
        endpoint = 'http://127.0.0.1:5002/query';
        payload = {
          prompt: userQuery,
          image_path: uploadedFilePath,
          conversation_history: history
        };
        if (selectedNode) {
          payload.node_id = selectedNode;
        }
        const queryRes = await axios.post(endpoint, payload, {
          headers: {
            'Content-Type': 'application/json'
          }
        });
        // Process response as usual
        const assistantTurn = {
          role: 'assistant',
          content: queryRes.data.response
        };
        setHistory(prev => [...prev, assistantTurn]);
        setResponse(queryRes.data.response);
      } else {
        // Use query endpoint for text-only queries
        endpoint = 'http://127.0.0.1:5002/query';
        payload = {
          prompt: userQuery,
          conversation_history: history,
        };
        // Only add node_id if a specific node is selected
        if (selectedNode) {
          payload.node_id = selectedNode;
        }
        const res = await axios.post(endpoint, payload, {
          headers: {
            'Content-Type': 'application/json'
          }
        });
        const assistantTurn = {
          role: 'assistant',
          content: res.data.response
        };
        setHistory(prev => [...prev, assistantTurn]);
        setResponse(res.data.response);
      }
    } catch (err) {
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
      setIsLoading(false);
    }
  };
  
  // Handle continue request
  const handleContinue = async () => {
    if (history.length === 0 || isLoading) return;
    
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
        node_id: activeNodeId
      });
      
      const assistantTurn = {
        role: 'assistant',
        content: res.data.result || res.data.response,
        node: activeNodeId,
        time: Date.now()
      };
      
      setHistory(prev => [...prev, assistantTurn]);
      
    } catch (err) {
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
      setIsLoading(false);
      setProcessingNode(null);
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
    
    // Cannot actually cancel the request, but we can reset the UI state
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
          <div className="subtitle">Intelligent Multi-Modal AI System</div>
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
            <p>Twhyne is an intelligent multi-modal AI system that seamlessly routes your queries to specialized expert models for optimal results.</p>
            
            <h3>Expert Nodes</h3>
            <div className="help-nodes">
              <div className="help-node">
                <div className="node-icon language">L</div>
                <div className="node-info">
                  <h4>Language</h4>
                  <p>Mistral-7B-Instruct for general text queries</p>
                </div>
              </div>
              <div className="help-node">
                <div className="node-icon code">C</div>
                <div className="node-info">
                  <h4>Code</h4>
                  <p>CodeLlama-7B for programming and code generation</p>
                </div>
              </div>
              <div className="help-node">
                <div className="node-icon math">M</div>
                <div className="node-info">
                  <h4>Math</h4>
                  <p>SymPy sandbox for mathematical calculations</p>
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
                  <p>TaskWeaver-3B for planning and task decomposition</p>
                </div>
              </div>
              <div className="help-node">
                <div className="node-icon claude">A</div>
                <div className="node-info">
                  <h4>Claude</h4>
                  <p>Optional remote Claude 3.7 for advanced reasoning (requires internet)</p>
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
                  disabled={isLoading || (eq.node === 'claude' && !useRemote)}
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
                  <p>No messages yet. Start by typing a query or click the help icon to see examples.</p>
                </div>
              ) : (
                  history.map((msg, index) => (
                    <div key={index} className={`chat-bubble ${msg.role} ${msg.error ? 'error' : ''}`}>
                      <span className="chat-meta">
                        {msg.role === 'user' ? 'You' : msg.role === 'system' ? 'System' : 'Twhyne'}
                        {msg.role === 'assistant' && msg.node && ` • ${msg.node} node`}
                        {msg.role === 'assistant' && msg.time && ` • ${msg.time}ms`}
                      </span>
                      {msg.content}
                  </div>
                ))
              )}
                {isLoading && (
                  <div className="chat-bubble assistant loading">
                    <span className="chat-meta">Twhyne {processingNode && `• ${processingNode} node`}</span>
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
                placeholder="Enter your query here... (Ctrl+Enter to submit)"
                disabled={isLoading}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && e.ctrlKey) {
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
                
                <label className="remote-toggle" title="Enable Claude for advanced reasoning (requires internet)">
                    <input
                      type="checkbox"
                      checked={useRemote}
                    onChange={() => setUseRemote(!useRemote)}
                    disabled={isLoading}
                    />
                    Use Claude
                  </label>
                
                <div className="keyboard-shortcut-hint">
                  <FaKeyboard />
                  <span>Ctrl+Enter to submit</span>
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
        <div className="right-panel">
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
        <div>Twhyne • v1.0 • Intelligent Multi-Modal AI System</div>
      </footer>
    </div>
  );
}

export default App;
