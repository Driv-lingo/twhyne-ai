// Conversation Manager Component for Twhyne AI
import React, { useState, useEffect } from 'react';
import {
  FaPlus,
  FaSave,
  FaTrash,
  FaDownload,
  FaUpload,
  FaComments,
  FaClock,
  FaEdit,
  FaCheck,
  FaTimes,
  FaFileExport
} from 'react-icons/fa';

const ConversationManager = ({
  currentConversation,
  onLoadConversation,
  onNewConversation,
  onDeleteConversation,
  onAutoSaved,
  currentHistory
}) => {
  const [conversations, setConversations] = useState([]);
  const [showManager, setShowManager] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [editingName, setEditingName] = useState('');
  const [searchTerm, setSearchTerm] = useState('');

  // Load conversations from localStorage on mount
  useEffect(() => {
    loadConversations();
  }, []);

  // AUTOSAVE: every conversation persists on its own - locally, in this
  // browser's storage, nothing leaves the machine. The first completed
  // exchange creates the entry (named from the first question); each new
  // message updates it. Manual Save/rename/export remain for curation.
  useEffect(() => {
    if (!currentHistory || currentHistory.length < 2) return;
    if (currentHistory.some(m => m.pending)) return;  // wait for answers
    const t = setTimeout(() => {
      setConversations(prev => {
        let list;
        if (currentConversation && prev.some(c => c.id === currentConversation.id)) {
          list = prev.map(c => c.id === currentConversation.id
            ? { ...c, messages: currentHistory,
                messageCount: currentHistory.length,
                timestamp: new Date().toISOString() }
            : c);
        } else {
          const firstUser = currentHistory.find(m => m.role === 'user');
          const conv = {
            id: Date.now().toString(),
            name: ((firstUser && firstUser.content) || 'Conversation').slice(0, 48),
            messages: currentHistory,
            timestamp: new Date().toISOString(),
            messageCount: currentHistory.length,
          };
          list = [...prev, conv];
          if (onAutoSaved) onAutoSaved(conv);
        }
        // Bound growth: keep the 50 most recent (localStorage is ~5MB).
        if (list.length > 50) {
          list = [...list].sort((a, b) =>
            new Date(b.timestamp) - new Date(a.timestamp)).slice(0, 50);
        }
        try {
          localStorage.setItem('twhyne_conversations', JSON.stringify(list));
        } catch (e) { /* storage full: keep in-memory list */ }
        return list;
      });
    }, 800);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentHistory, currentConversation]);

  const loadConversations = () => {
    const saved = localStorage.getItem('twhyne_conversations');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        setConversations(parsed);
      } catch (e) {
        console.error('Error loading conversations:', e);
        setConversations([]);
      }
    }
  };

  const saveConversation = (name = null) => {
    if (!currentHistory || currentHistory.length === 0) {
      alert('No messages to save');
      return;
    }

    const conversationName = name || prompt('Enter a name for this conversation:');
    if (!conversationName) return;

    const newConversation = {
      id: Date.now().toString(),
      name: conversationName,
      messages: currentHistory,
      timestamp: new Date().toISOString(),
      messageCount: currentHistory.length
    };

    const updated = [...conversations, newConversation];
    setConversations(updated);
    localStorage.setItem('twhyne_conversations', JSON.stringify(updated));
    
    alert(`Conversation "${conversationName}" saved successfully!`);
  };

  const updateConversation = () => {
    if (!currentConversation) {
      saveConversation();
      return;
    }

    const updated = conversations.map(conv => 
      conv.id === currentConversation.id 
        ? { ...conv, messages: currentHistory, messageCount: currentHistory.length, timestamp: new Date().toISOString() }
        : conv
    );
    
    setConversations(updated);
    localStorage.setItem('twhyne_conversations', JSON.stringify(updated));
  };

  const deleteConversation = (id) => {
    if (!window.confirm('Are you sure you want to delete this conversation?')) return;

    const updated = conversations.filter(conv => conv.id !== id);
    setConversations(updated);
    localStorage.setItem('twhyne_conversations', JSON.stringify(updated));
    
    if (currentConversation?.id === id) {
      onNewConversation();
    }
  };

  const renameConversation = (id) => {
    const conv = conversations.find(c => c.id === id);
    if (conv && editingName.trim()) {
      const updated = conversations.map(c => 
        c.id === id ? { ...c, name: editingName.trim() } : c
      );
      setConversations(updated);
      localStorage.setItem('twhyne_conversations', JSON.stringify(updated));
    }
    setEditingId(null);
    setEditingName('');
  };

  const exportConversation = (conv, format = 'json') => {
    const timestamp = new Date().toISOString().split('T')[0];
    const filename = `twhyne_${conv.name.replace(/[^a-z0-9]/gi, '_')}_${timestamp}`;

    if (format === 'json') {
      const dataStr = JSON.stringify(conv, null, 2);
      const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
      
      const link = document.createElement('a');
      link.setAttribute('href', dataUri);
      link.setAttribute('download', `${filename}.json`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } else if (format === 'markdown') {
      let markdown = `# Twhyne Conversation: ${conv.name}\n\n`;
      markdown += `**Date:** ${new Date(conv.timestamp).toLocaleString()}\n\n`;
      markdown += `---\n\n`;
      
      conv.messages.forEach(msg => {
        const role = msg.role === 'user' ? '**You**' : msg.role === 'assistant' ? '**Twhyne**' : '**System**';
        markdown += `${role}${msg.node ? ` (${msg.node})` : ''}:\n\n${msg.content}\n\n---\n\n`;
      });

      const dataUri = 'data:text/markdown;charset=utf-8,'+ encodeURIComponent(markdown);
      const link = document.createElement('a');
      link.setAttribute('href', dataUri);
      link.setAttribute('download', `${filename}.md`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  };

  const exportAll = () => {
    const timestamp = new Date().toISOString().split('T')[0];
    const dataStr = JSON.stringify(conversations, null, 2);
    const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
    
    const link = document.createElement('a');
    link.setAttribute('href', dataUri);
    link.setAttribute('download', `twhyne_all_conversations_${timestamp}.json`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const importConversations = (event) => {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const imported = JSON.parse(e.target.result);
        
        // Handle single conversation or array
        const toImport = Array.isArray(imported) ? imported : [imported];
        
        // Add unique IDs if missing
        const processed = toImport.map(conv => ({
          ...conv,
          id: conv.id || Date.now().toString() + Math.random().toString(36).substr(2, 9),
          timestamp: conv.timestamp || new Date().toISOString()
        }));

        const updated = [...conversations, ...processed];
        setConversations(updated);
        localStorage.setItem('twhyne_conversations', JSON.stringify(updated));
        
        alert(`Successfully imported ${processed.length} conversation(s)`);
      } catch (error) {
        alert('Error importing conversations: Invalid file format');
        console.error(error);
      }
    };
    reader.readAsText(file);
    
    // Reset file input
    event.target.value = '';
  };

  const filteredConversations = conversations.filter(conv =>
    conv.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const formatDate = (timestamp) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    
    if (days === 0) return 'Today';
    if (days === 1) return 'Yesterday';
    if (days < 7) return `${days} days ago`;
    return date.toLocaleDateString();
  };

  return (
    <>
      {/* Toggle Button */}
      <button
        className="conversation-toggle"
        onClick={() => setShowManager(!showManager)}
        title="Manage Conversations"
      >
        <FaComments />
        {conversations.length > 0 && (
          <span className="conversation-count">{conversations.length}</span>
        )}
      </button>

      {/* Manager Panel */}
      <div className={`conversation-manager ${showManager ? 'open' : ''}`}>
        <div className="manager-header">
          <h3>Conversations</h3>
          <button className="close-btn" onClick={() => setShowManager(false)}>
            <FaTimes />
          </button>
        </div>

        {/* Actions Bar */}
        <div className="manager-actions">
          <button onClick={onNewConversation} title="New Conversation">
            <FaPlus /> New
          </button>
          <button onClick={() => saveConversation()} title="Save Current">
            <FaSave /> Save
          </button>
          {currentConversation && (
            <button onClick={updateConversation} title="Update Current">
              <FaEdit /> Update
            </button>
          )}
          <button onClick={exportAll} title="Export All">
            <FaDownload /> Export All
          </button>
          <label className="import-btn" title="Import Conversations">
            <FaUpload /> Import
            <input
              type="file"
              accept=".json"
              onChange={importConversations}
              style={{ display: 'none' }}
            />
          </label>
        </div>

        {/* Search */}
        <div className="manager-search">
          <input
            type="text"
            placeholder="Search conversations..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>

        {/* Conversation List */}
        <div className="conversation-list">
          {filteredConversations.length === 0 ? (
            <div className="empty-state">
              {searchTerm ? 'No conversations found' : 'No saved conversations yet'}
            </div>
          ) : (
            filteredConversations
              .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
              .map(conv => (
                <div
                  key={conv.id}
                  className={`conversation-item ${currentConversation?.id === conv.id ? 'active' : ''}`}
                >
                  <div className="conversation-info" onClick={() => onLoadConversation(conv)}>
                    {editingId === conv.id ? (
                      <input
                        type="text"
                        value={editingName}
                        onChange={(e) => setEditingName(e.target.value)}
                        onKeyPress={(e) => e.key === 'Enter' && renameConversation(conv.id)}
                        onClick={(e) => e.stopPropagation()}
                        autoFocus
                      />
                    ) : (
                      <div className="conversation-name">{conv.name}</div>
                    )}
                    <div className="conversation-meta">
                      <FaClock /> {formatDate(conv.timestamp)} • {conv.messageCount} messages
                    </div>
                  </div>
                  
                  <div className="conversation-actions">
                    {editingId === conv.id ? (
                      <>
                        <button onClick={() => renameConversation(conv.id)} title="Save">
                          <FaCheck />
                        </button>
                        <button onClick={() => { setEditingId(null); setEditingName(''); }} title="Cancel">
                          <FaTimes />
                        </button>
                      </>
                    ) : (
                      <>
                        <button 
                          onClick={(e) => { 
                            e.stopPropagation(); 
                            setEditingId(conv.id); 
                            setEditingName(conv.name); 
                          }} 
                          title="Rename"
                        >
                          <FaEdit />
                        </button>
                        <button 
                          onClick={(e) => { 
                            e.stopPropagation(); 
                            exportConversation(conv, 'json'); 
                          }} 
                          title="Export JSON"
                        >
                          <FaDownload />
                        </button>
                        <button 
                          onClick={(e) => { 
                            e.stopPropagation(); 
                            exportConversation(conv, 'markdown'); 
                          }} 
                          title="Export Markdown"
                        >
                          <FaFileExport />
                        </button>
                        <button 
                          onClick={(e) => { 
                            e.stopPropagation(); 
                            deleteConversation(conv.id); 
                          }} 
                          title="Delete"
                        >
                          <FaTrash />
                        </button>
                      </>
                    )}
                  </div>
                </div>
              ))
          )}
        </div>
      </div>
    </>
  );
};

export default ConversationManager;
