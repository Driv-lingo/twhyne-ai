// RAG Manager Component for Twhyne AI
import React, { useState, useEffect } from 'react';
import {
  FaDatabase,
  FaUpload,
  FaPlus,
  FaTrash,
  FaEdit,
  FaSearch,
  FaFileAlt,
  FaFilePdf,
  FaFileCsv,
  FaFileCode,
  FaCheck,
  FaTimes,
  FaRobot,
  FaDownload
} from 'react-icons/fa';
import axios from 'axios';

const RAGManager = ({ onNodeCreated }) => {
  const [showManager, setShowManager] = useState(false);
  const [datasets, setDatasets] = useState([]);
  const [selectedDataset, setSelectedDataset] = useState(null);
  const [isCreating, setIsCreating] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [datasetName, setDatasetName] = useState('');
  const [datasetDescription, setDatasetDescription] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [ragStatus, setRagStatus] = useState(null);
  const [ingestProgress, setIngestProgress] = useState('');

  useEffect(() => {
    if (showManager) {
      loadDatasets();
      checkRAGStatus();
    }
  }, [showManager]);

  // While an ingest runs, poll the backend's progress line so the user sees
  // "section 41/230" instead of a frozen button (embedding is CPU-bound and
  // large documents take minutes).
  useEffect(() => {
    if (!isLoading) { setIngestProgress(''); return; }
    const iv = setInterval(async () => {
      try {
        const r = await axios.get('http://localhost:5002/progress');
        const { state, detail } = r.data || {};
        if (state === 'indexing') setIngestProgress(detail || 'indexing…');
      } catch (e) { /* keep last text */ }
    }, 1200);
    return () => clearInterval(iv);
  }, [isLoading]);

  const checkRAGStatus = async (retries = 5) => {
    try {
      const response = await axios.get('http://localhost:5002/api/rag/status');
      setRagStatus(response.data);
    } catch (error) {
      if (retries > 0) {
        // Backend may still be starting up (loading the model). Retry a few
        // times before showing a warning, so a startup race doesn't leave a
        // stale "not available" banner on screen.
        setTimeout(() => checkRAGStatus(retries - 1), 3000);
        return;
      }
      console.error('Error checking RAG status:', error);
      setRagStatus({ available: false });
    }
  };

  const loadDatasets = async () => {
    try {
      const response = await axios.get('http://localhost:5002/api/rag/datasets');
      setDatasets(response.data.datasets || []);
    } catch (error) {
      console.error('Error loading datasets:', error);
      setDatasets([]);
    }
  };

  const handleFileUpload = (event) => {
    const files = Array.from(event.target.files);
    const readers = [];

    files.forEach(file => {
      const reader = new FileReader();
      readers.push(
        new Promise((resolve) => {
          reader.onload = (e) => {
            const content = e.target.result;
            const isBase64 = file.type === 'application/pdf';
            
            resolve({
              filename: file.name,
              type: getFileType(file.name),
              content: isBase64 ? btoa(content) : content,
              encoding: isBase64 ? 'base64' : 'utf-8',
              size: file.size
            });
          };

          if (file.type === 'application/pdf') {
            reader.readAsBinaryString(file);
          } else {
            reader.readAsText(file);
          }
        })
      );
    });

    Promise.all(readers).then(fileData => {
      setUploadedFiles(prev => [...prev, ...fileData]);
    });
  };

  const getFileType = (filename) => {
    const ext = filename.split('.').pop().toLowerCase();
    switch (ext) {
      case 'pdf': return 'pdf';
      case 'csv': return 'csv';
      case 'json': return 'json';
      case 'md': return 'markdown';
      case 'txt': return 'text';
      default: return 'text';
    }
  };

  const getFileIcon = (type) => {
    switch (type) {
      case 'pdf': return <FaFilePdf className="file-icon pdf" />;
      case 'csv': return <FaFileCsv className="file-icon csv" />;
      case 'json': return <FaFileCode className="file-icon json" />;
      default: return <FaFileAlt className="file-icon text" />;
    }
  };

  const createDataset = async () => {
    if (!datasetName || uploadedFiles.length === 0) {
      alert('Please provide a name and upload at least one file');
      return;
    }

    setIsLoading(true);
    try {
      const response = await axios.post('http://localhost:5002/api/rag/datasets', {
        name: datasetName,
        description: datasetDescription,
        files: uploadedFiles
      });

      if (response.data.success) {
        const n = response.data.dataset && response.data.dataset.document_count;
        if (!n) {
          alert(`"${datasetName}" was created but NO text could be extracted from the file(s) — answers cannot cite it. Scanned/image-only PDFs are not supported yet; try a text-based PDF or a txt/md/csv file.`);
        } else {
          alert(`Knowledge base "${datasetName}" created — ${n} sections indexed and citable.`);
        }
        loadDatasets();
        resetCreateForm();
        
        // Notify parent component about new node
        if (onNodeCreated) {
          onNodeCreated(response.data.dataset);
        }
      }
    } catch (error) {
      console.error('Error creating dataset:', error);
      alert('Failed to create dataset: ' + (error.response?.data?.error || error.message));
    } finally {
      setIsLoading(false);
    }
  };

  const deleteDataset = async (datasetId) => {
    if (!window.confirm('Are you sure you want to delete this dataset?')) return;

    try {
      await axios.delete(`http://localhost:5002/api/rag/datasets/${datasetId}`);
      loadDatasets();
      if (selectedDataset?.id === datasetId) {
        setSelectedDataset(null);
      }
    } catch (error) {
      console.error('Error deleting dataset:', error);
      // Say WHY: "backend unreachable" and "dataset not found" need
      // opposite user actions (restart the app vs refresh the list).
      const why = error.response
        ? (error.response.data?.error || `server error ${error.response.status}`)
        : 'backend unreachable — is Twhyne still running? Restart the launcher and try again';
      alert('Could not delete the knowledge base: ' + why);
    }
  };

  const searchDataset = async () => {
    if (!selectedDataset || !searchQuery) return;

    setIsLoading(true);
    try {
      const response = await axios.post(
        `http://localhost:5002/api/rag/datasets/${selectedDataset.id}/search`,
        { query: searchQuery, top_k: 5 }
      );
      setSearchResults(response.data.results || []);
    } catch (error) {
      console.error('Error searching dataset:', error);
      setSearchResults([]);
    } finally {
      setIsLoading(false);
    }
  };

  const resetCreateForm = () => {
    setIsCreating(false);
    setDatasetName('');
    setDatasetDescription('');
    setUploadedFiles([]);
  };

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  return (
    <>
      {/* Toggle Button */}
      <button
        className="rag-toggle"
        onClick={() => setShowManager(!showManager)}
        title="RAG Knowledge Manager"
      >
        <FaDatabase />
        {datasets.length > 0 && (
          <span className="rag-count">{datasets.length}</span>
        )}
      </button>

      {/* Manager Panel */}
      <div className={`rag-manager ${showManager ? 'open' : ''}`}>
        <div className="rag-header">
          <h3>
            <FaDatabase /> Knowledge Bases
          </h3>
          <button className="close-btn" onClick={() => setShowManager(false)}>
            <FaTimes />
          </button>
        </div>

        {/* RAG Status */}
        {ragStatus && !ragStatus.available && (
          <div className="rag-warning">
            ⚠️ Can't reach the backend yet — it may still be starting up. Loading the
            model can take a minute on first launch; this notice clears itself once
            it's ready.
          </div>
        )}
        {ragStatus && ragStatus.available && ragStatus.backend === 'keyword_fallback' && (
          <div className="rag-warning">
            ℹ️ Semantic search is off (embedding model not found) — using keyword
            matching instead. Retrieval still works, results are just less precise.
          </div>
        )}

        {/* Main Content */}
        <div className="rag-content">
          {!isCreating && !selectedDataset ? (
            // Dataset List View
            <>
              <div className="rag-actions">
                <button onClick={() => setIsCreating(true)} className="create-btn">
                  <FaPlus /> Create New Knowledge Base
                </button>
              </div>

              <div className="dataset-list">
                {datasets.length === 0 ? (
                  <div className="empty-state">
                    <FaDatabase />
                    <p>No knowledge bases yet</p>
                    <small>Create one to enable custom RAG nodes</small>
                  </div>
                ) : (
                  datasets.map(dataset => (
                    <div key={dataset.id} className="dataset-item">
                      <div className="dataset-info" onClick={() => setSelectedDataset(dataset)}>
                        <div className="dataset-header">
                          <FaRobot className="dataset-icon" />
                          <div>
                            <div className="dataset-name">{dataset.name}</div>
                            <div className="dataset-meta">
                              {dataset.document_count} documents
                              {dataset.is_available && (
                                <span className="status-badge online">Active</span>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                      <div className="dataset-actions">
                        <button onClick={() => deleteDataset(dataset.id)} title="Delete">
                          <FaTrash />
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </>
          ) : isCreating ? (
            // Create Dataset View
            <div className="create-dataset">
              <div className="create-header">
                <button onClick={resetCreateForm} className="back-btn">
                  ← Back
                </button>
                <h4>Create Knowledge Base</h4>
              </div>

              <div className="create-form">
                <div className="form-group">
                  <label>Name *</label>
                  <input
                    type="text"
                    value={datasetName}
                    onChange={(e) => setDatasetName(e.target.value)}
                    placeholder="e.g., Product Documentation"
                  />
                </div>

                <div className="form-group">
                  <label>Description</label>
                  <textarea
                    value={datasetDescription}
                    onChange={(e) => setDatasetDescription(e.target.value)}
                    placeholder="Describe the knowledge base..."
                    rows="3"
                  />
                </div>

                <div className="form-group">
                  <label>Upload Files *</label>
                  <div className="file-upload-area">
                    <input
                      type="file"
                      id="rag-file-upload"
                      multiple
                      accept=".txt,.pdf,.json,.csv,.md,.docx,.html,.xml"
                      onChange={handleFileUpload}
                      style={{ display: 'none' }}
                    />
                    <label htmlFor="rag-file-upload" className="upload-label">
                      <FaUpload />
                      <span>Click to upload files</span>
                      <small>Supported: TXT, PDF, JSON, CSV, MD</small>
                    </label>
                  </div>

                  {uploadedFiles.length > 0 && (
                    <div className="uploaded-files">
                      {uploadedFiles.map((file, index) => (
                        <div key={index} className="uploaded-file">
                          {getFileIcon(file.type)}
                          <span className="file-name">{file.filename}</span>
                          <span className="file-size">{formatFileSize(file.size)}</span>
                          <button
                            onClick={() => setUploadedFiles(prev => 
                              prev.filter((_, i) => i !== index)
                            )}
                          >
                            <FaTimes />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="form-actions">
                  <button 
                    onClick={createDataset} 
                    disabled={isLoading || !datasetName || uploadedFiles.length === 0}
                    className="primary-btn"
                  >
                    {isLoading ? (ingestProgress || 'Creating…') : 'Create Knowledge Base'}
                  </button>
                  <button onClick={resetCreateForm} className="secondary-btn">
                    Cancel
                  </button>
                </div>
                {isLoading && (
                  <p className="hint" style={{marginTop: 8, fontSize: 12, opacity: 0.75}}>
                    Indexing runs on your CPU — large documents take a few minutes.
                    Progress updates live above.
                  </p>
                )}
              </div>
            </div>
          ) : selectedDataset ? (
            // Dataset Detail View
            <div className="dataset-detail">
              <div className="detail-header">
                <button onClick={() => setSelectedDataset(null)} className="back-btn">
                  ← Back
                </button>
                <h4>{selectedDataset.name}</h4>
              </div>

              <div className="dataset-stats">
                <div className="stat">
                  <span className="stat-label">Documents</span>
                  <span className="stat-value">{selectedDataset.document_count}</span>
                </div>
                <div className="stat">
                  <span className="stat-label">Status</span>
                  <span className={`status-badge ${selectedDataset.is_available ? 'online' : 'offline'}`}>
                    {selectedDataset.is_available ? 'Active' : 'Inactive'}
                  </span>
                </div>
              </div>

              {selectedDataset.description && (
                <div className="dataset-description">
                  {selectedDataset.description}
                </div>
              )}

              <div className="search-section">
                <h5>Search Knowledge Base</h5>
                <div className="search-bar">
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Enter search query..."
                    onKeyPress={(e) => e.key === 'Enter' && searchDataset()}
                  />
                  <button onClick={searchDataset} disabled={isLoading}>
                    <FaSearch />
                  </button>
                </div>

                {searchResults.length > 0 && (
                  <div className="search-results">
                    <h5>Results</h5>
                    {searchResults.map((result, index) => (
                      <div key={index} className="search-result">
                        <div className="result-title">{result.title}</div>
                        <div className="result-content">{result.content.substring(0, 200)}...</div>
                        <div className="result-score">Score: {result.score.toFixed(2)}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="dataset-actions-bottom">
                <button onClick={() => deleteDataset(selectedDataset.id)} className="danger-btn">
                  <FaTrash /> Delete Knowledge Base
                </button>
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </>
  );
};

export default RAGManager;
