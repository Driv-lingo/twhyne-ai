// Copyright (c) 2025 SNF-AI
// SPDX-License-Identifier: MIT

import { useState, useEffect, useCallback, useRef } from 'react';
import axios, { AxiosError } from 'axios';

// --- Constants ---
const API_BASE_URL = 'http://127.0.0.1:5002';
const WS_BASE_URL = API_BASE_URL.replace(/^http/, 'ws');
const WS_RECONNECT_DELAY = 5000; // 5 seconds
const WS_MAX_RECONNECT_ATTEMPTS = 3;
const WS_HEARTBEAT_INTERVAL = 30000; // 30 seconds
const WS_HEARTBEAT_TIMEOUT = 5000; // 5 seconds
const WS_CONNECTION_TIMEOUT = 3000; // 3 seconds
const WS_SILENT_MODE = true; // Suppress WebSocket connection errors in console

// --- Type Definitions ---

export interface Node {
  id: string;
  name: string;
  description: string;
  capabilities: string[];
  keywords: string[];
  is_remote: boolean;
  status: 'online' | 'offline' | 'starting' | 'error';
  version: string;
  memory_requirements: number;
  vram_requirements: number | null;
  metadata: Record<string, string>;
}

export interface QueryRequest {
  query: string;
  parameters?: Record<string, any>;
  input_files?: string[];
  input_file_contents?: Record<string, string>;
}

export interface QueryResponse {
  text: string;
  output_files: Record<string, Uint8Array>;
  processing_time_ms: number;
  query_id: string;
  nodes: string[];
}

// --- WebSocket Message Interfaces ---

interface BaseMessage {
  type: string;
  data: any;
}

interface TokenMessage extends BaseMessage {
  type: 'token';
  data: { token: string; node_id: string };
}

interface TokenChunkMessage extends BaseMessage {
  type: 'token_chunk';
  data: { 
    chunk: string; 
    tokens_processed: number; 
    estimated_total: number; 
    percent_complete: number 
  };
}

interface ProgressMessage extends BaseMessage {
  type: 'progress';
  data: { 
    tokens_processed: number; 
    estimated_total: number; 
    percent_complete: number 
  };
}

interface EdgeActivationMessage extends BaseMessage {
  type: 'edge_activation';
  data: { source: string; target: string; active: boolean };
}

interface NodeSelectionMessage extends BaseMessage {
  type: 'node_selection';
  data: { node_id: string; selected: boolean };
}

interface CompleteMessage extends BaseMessage {
  type: 'complete';
  data: { total_tokens: number; processing_time_ms: number };
}

interface ErrorMessage extends BaseMessage {
  type: 'error';
  data: { message: string; recoverable: boolean };
}

interface PipelineModeMessage extends BaseMessage {
    type: 'pipeline_mode';
    data: { nodes: string[] };
}

interface PipelineStageMessage extends BaseMessage {
    type: 'pipeline_stage' | 'pipeline_stage_complete';
    data: { stage: number; total_stages: number };
}

interface PipelineCompleteMessage extends BaseMessage {
    type: 'pipeline_complete';
    data: {};
}

interface HeartbeatMessage extends BaseMessage {
    type: 'heartbeat';
    data: {};
}

type WebSocketMessage = 
  | TokenMessage 
  | TokenChunkMessage
  | ProgressMessage
  | EdgeActivationMessage 
  | NodeSelectionMessage 
  | CompleteMessage 
  | ErrorMessage
  | PipelineModeMessage
  | PipelineStageMessage
  | PipelineCompleteMessage
  | HeartbeatMessage;

// --- Hook Return Type ---

export interface UseFluxReturn {
  nodes: Node[];
  loading: boolean;
  error: string | null;
  isStreaming: boolean;
  streamingResponse: string;
  activeEdges: [string, string][];
  selectedNodes: string[];
  progress: {
    tokensProcessed: number;
    estimatedTotal: number;
    percentComplete: number;
  };
  fetchNodes: () => Promise<void>;
  startNode: (nodeId: string) => Promise<boolean>;
  submitQuery: (request: QueryRequest) => Promise<void>;
  submitImageQuery: (imageFile: File, queryText: string) => Promise<void>;
  cancelStream: () => void;
  clearError: () => void;
}

/**
 * Custom hook for interacting with the Flux API and WebSocket streaming.
 */
export function useFlux(): UseFluxReturn {
  // --- State ---
  const [nodes, setNodes] = useState<Node[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [streamingResponse, setStreamingResponse] = useState<string>('');
  const [activeEdges, setActiveEdges] = useState<[string, string][]>([]);
  const [selectedNodes, setSelectedNodes] = useState<string[]>([]);
  const [progress, setProgress] = useState({ 
    tokensProcessed: 0, 
    estimatedTotal: 100, 
    percentComplete: 0 
  });

  // --- Refs for managing WebSocket and timers ---
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttempts = useRef<number>(0);
  const heartbeatInterval = useRef<NodeJS.Timeout | null>(null);
  const heartbeatTimeout = useRef<NodeJS.Timeout | null>(null);
  const connectionErrorShown = useRef<boolean>(false);

  // --- WebSocket Management ---

  const sendHeartbeat = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'heartbeat' }));
      if (heartbeatTimeout.current) clearTimeout(heartbeatTimeout.current);
      heartbeatTimeout.current = setTimeout(() => {
        console.warn('Heartbeat timeout, closing connection.');
        wsRef.current?.close(); // onclose will handle reconnect
      }, WS_HEARTBEAT_TIMEOUT);
    }
  }, []);

  const handleWebSocketMessage = useCallback((message: WebSocketMessage) => {
    switch (message.type) {
      case 'token':
        setStreamingResponse(prev => prev + message.data.token);
        break;
      case 'token_chunk':
        setStreamingResponse(prev => prev + message.data.chunk);
        setProgress(prev => ({ ...prev, ...message.data }));
        break;
      case 'progress':
        setProgress(message.data);
        break;
      case 'edge_activation':
        setActiveEdges(prev => 
          message.data.active
            ? [...prev, [message.data.source, message.data.target]]
            : prev.filter(edge => !(edge[0] === message.data.source && edge[1] === message.data.target))
        );
        break;
      case 'node_selection':
        setSelectedNodes(prev => 
          message.data.selected
            ? [...prev, message.data.node_id]
            : prev.filter(id => id !== message.data.node_id)
        );
        break;
      case 'complete':
        setIsStreaming(false);
        console.log(`Stream complete. Total tokens: ${message.data.total_tokens}, Time: ${message.data.processing_time_ms}ms`);
        break;
      case 'error':
        setError(`Stream error: ${message.data.message}`);
        setIsStreaming(false);
        break;
      case 'heartbeat':
        if (heartbeatTimeout.current) clearTimeout(heartbeatTimeout.current);
        break;
      case 'pipeline_mode':
        console.log('Pipeline mode activated:', message.data.nodes);
        break;
      case 'pipeline_stage':
        console.log(`Pipeline stage ${message.data.stage + 1}/${message.data.total_stages} started.`);
        break;
      case 'pipeline_stage_complete':
        console.log(`Pipeline stage ${message.data.stage + 1}/${message.data.total_stages} completed.`);
        break;
      case 'pipeline_complete':
        console.log('Pipeline processing complete.');
        break;
      default:
        console.warn('Unknown WebSocket message type:', (message as any).type);
    }
  }, []);

  const initWebSocket = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState !== WebSocket.CLOSED) {
        return; // Connection is already open or connecting
    }

    if (reconnectAttempts.current >= WS_MAX_RECONNECT_ATTEMPTS) {
      if (!connectionErrorShown.current) {
        setError('Backend server not available. Expert nodes will show as offline.');
        connectionErrorShown.current = true;
      }
      return;
    }

    const ws = new WebSocket(`${WS_BASE_URL}/stream`);
    wsRef.current = ws;

    const connectionTimeout = setTimeout(() => {
      if (ws.readyState !== WebSocket.OPEN) {
        ws.close();
      }
    }, WS_CONNECTION_TIMEOUT);

    ws.onopen = () => {
      clearTimeout(connectionTimeout);
      console.log('WebSocket connection established.');
      reconnectAttempts.current = 0;
      connectionErrorShown.current = false;
      if (heartbeatInterval.current) clearInterval(heartbeatInterval.current);
      heartbeatInterval.current = setInterval(sendHeartbeat, WS_HEARTBEAT_INTERVAL);
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data) as WebSocketMessage;
        handleWebSocketMessage(message);
      } catch (err) {
        console.error('Error parsing WebSocket message:', err);
        setError('Error processing server response.');
      }
    };

    ws.onerror = (event) => {
      if (WS_SILENT_MODE) {
        event.preventDefault();
        event.stopPropagation();
      }
      // onclose will handle the logic for reconnection
    };

    ws.onclose = () => {
      clearTimeout(connectionTimeout);
      if (heartbeatInterval.current) clearInterval(heartbeatInterval.current);
      if (heartbeatTimeout.current) clearTimeout(heartbeatTimeout.current);

      if (reconnectAttempts.current < WS_MAX_RECONNECT_ATTEMPTS) {
        reconnectAttempts.current++;
        console.log(`WebSocket disconnected. Attempting to reconnect (${reconnectAttempts.current}/${WS_MAX_RECONNECT_ATTEMPTS})...`);
        setTimeout(initWebSocket, WS_RECONNECT_DELAY);
      } else {
        if (!connectionErrorShown.current) {
          setError('Backend connection lost. Please check the server.');
          connectionErrorShown.current = true;
        }
        setIsStreaming(false);
        setLoading(false);
      }
    };
  }, [sendHeartbeat, handleWebSocketMessage]);

  // --- API Interaction ---

  const fetchNodes = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await axios.get(`${API_BASE_URL}/nodes`);
      setNodes(response.data.nodes);
    } catch (err) {
      const axiosError = err as AxiosError;
      console.error('Error fetching nodes:', axiosError.message);
      setError(`Failed to fetch nodes. Is the backend server running?`);
    } finally {
      setLoading(false);
    }
  }, []);

  const startNode = useCallback(async (nodeId: string): Promise<boolean> => {
    setLoading(true);
    setError(null);
    try {
      await axios.post(`${API_BASE_URL}/nodes/${nodeId}/start`);
      await fetchNodes();
      return true;
    } catch (err) {
      const axiosError = err as AxiosError;
      const errorMsg = (axiosError.response?.data as any)?.error || axiosError.message;
      console.error(`Error starting node ${nodeId}:`, errorMsg);
      setError(`Failed to start node: ${errorMsg}`);
      return false;
    } finally {
      setLoading(false);
    }
  }, [fetchNodes]);

  const submitQuery = useCallback(async (request: QueryRequest) => {
    if (wsRef.current?.readyState !== WebSocket.OPEN) {
        initWebSocket(); // Attempt to reconnect before sending
        setError('Connecting to backend... Please try again shortly.');
        return;
    }

    // Reset state for new query
    setLoading(true);
    setIsStreaming(true);
    setStreamingResponse('');
    setActiveEdges([]);
    setSelectedNodes([]);
    setProgress({ tokensProcessed: 0, estimatedTotal: 100, percentComplete: 0 });
    setError(null);

    wsRef.current.send(JSON.stringify(request));
  }, [initWebSocket]);

  const submitImageQuery = useCallback(async (imageFile: File, queryText: string) => {
    const reader = new FileReader();
    reader.readAsDataURL(imageFile);
    reader.onload = () => {
        const base64Image = (reader.result as string).split(',')[1];
        const request: QueryRequest = {
            query: queryText,
            input_file_contents: {
                [imageFile.name]: base64Image,
            },
        };
        submitQuery(request);
    };
    reader.onerror = (error) => {
        console.error('Error reading file:', error);
        setError('Failed to read image file.');
    };
  }, [submitQuery]);

  const cancelStream = useCallback(() => {
    if (isStreaming) {
        wsRef.current?.send(JSON.stringify({ type: 'cancel' }));
        setIsStreaming(false);
        setLoading(false);
        console.log('Streaming cancelled by user.');
    }
  }, [isStreaming]);

  // --- Effects ---

  useEffect(() => {
    fetchNodes();
    initWebSocket();

    return () => {
      if (wsRef.current) {
        wsRef.current.onclose = null; // Prevent reconnect logic on unmount
        wsRef.current.close();
      }
      if (heartbeatInterval.current) clearInterval(heartbeatInterval.current);
      if (heartbeatTimeout.current) clearTimeout(heartbeatTimeout.current);
    };
  }, [fetchNodes, initWebSocket]);

  // --- Return public interface ---

  return {
    nodes,
    loading,
    error,
    isStreaming,
    streamingResponse,
    activeEdges,
    selectedNodes,
    progress,
    fetchNodes,
    startNode,
    submitQuery,
    submitImageQuery,
    cancelStream,
    clearError: () => setError(null),
  };
}
