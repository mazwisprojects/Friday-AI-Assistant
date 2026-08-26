import React, { useState, useEffect } from 'react';
import { Folder, File, Search, Home, ArrowUp, X, Trash2, Download } from 'lucide-react';

export default function FileManagerWindow({ position, onClose, onDrag }) {
  const [currentPath, setCurrentPath] = useState('');
  const [items, setItems] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const [processingAction, setProcessingAction] = useState('summarize');
  const [processingResult, setProcessingResult] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);

  useEffect(() => {
    const socket = window.socket;
    
    socket.on('directory_contents', (data) => {
      setItems(data.items);
      setCurrentPath(data.path);
    });

    socket.on('file_processing_result', (data) => {
      setIsProcessing(false);
      const result = data.error || data.result || 'Processing completed.';
      setProcessingResult(data.file_awareness
        ? `${result}\n\nYou can now tell Friday what to do with this file.`
        : data.wallpaper_ready
          ? `${result}\n\nWallpaper ready: ask Friday to set this image as your wallpaper.`
          : result);
    });
    
    // Load home directory
    socket.emit('read_directory', { path: '~' });
    
    return () => {
      socket.off('directory_contents');
      socket.off('file_processing_result');
    };
  }, []);

  const handleNavigate = (path) => {
    window.socket.emit('read_directory', { path });
  };

  const handleGoUp = () => {
    const parentPath = currentPath.split('/').slice(0, -1).join('/') || '~';
    handleNavigate(parentPath);
  };

  const handleSearch = () => {
    if (searchQuery.trim()) {
      window.socket.emit('search_files', { query: searchQuery, path: currentPath });
    }
  };

  const handleFileSelect = (event) => {
    const file = event.target.files?.[0] || null;
    setSelectedFile(file);
    setProcessingResult('');

    if (!file) return;
    if (file.size > 25 * 1024 * 1024) {
      setProcessingResult('File is too large. Maximum size is 25 MB.');
      return;
    }

    setIsProcessing(true);
    setProcessingResult('Uploading file so Friday can inspect it...');
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = String(reader.result || '');
      const encoded = dataUrl.includes(',') ? dataUrl.split(',')[1] : dataUrl;
      window.socket.emit('upload_file_for_awareness', {
        filename: file.name,
        mime_type: file.type || 'application/octet-stream',
        data: encoded
      });
    };
    reader.onerror = () => {
      setIsProcessing(false);
      setProcessingResult('Could not read the selected file.');
    };
    reader.readAsDataURL(file);
  };

  const handleProcessFile = () => {
    if (!selectedFile) return;

    setIsProcessing(true);
    setProcessingResult('Uploading and processing...');
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = String(reader.result || '');
      const encoded = dataUrl.includes(',') ? dataUrl.split(',')[1] : dataUrl;
      window.socket.emit('process_uploaded_file', {
        filename: selectedFile.name,
        data: encoded,
        action: processingAction,
        instruction: ''
      });
    };
    reader.onerror = () => {
      setIsProcessing(false);
      setProcessingResult('Could not read the selected file.');
    };
    reader.readAsDataURL(selectedFile);
  };

  const handleItemClick = (item) => {
    if (item.type === 'directory') {
      handleNavigate(item.path);
    } else {
      // Could open file preview
      window.socket.emit('read_file', { path: item.path });
    }
  };

  const filteredItems = items.filter(item => 
    item.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div 
      className="window file-manager-window"
      style={{ 
        transform: `translate(${position.x}px, ${position.y}px)`,
        width: '500px',
        height: '400px'
      }}
    >
      <div className="window-header" onMouseDown={onDrag}>
        <div className="window-title">
          <Folder size={16} />
          <span>File Manager</span>
        </div>
        <button className="window-close" onClick={onClose}>
          <X size={16} />
        </button>
      </div>
      <div className="window-content">
        <div className="file-processor-panel">
          <div className="file-toolbar">
            <input type="file" onChange={handleFileSelect} />
            <select value={processingAction} onChange={(e) => setProcessingAction(e.target.value)}>
              <option value="summarize">Summarize</option>
              <option value="extract_text">Extract text</option>
              <option value="describe">Describe</option>
              <option value="ocr">OCR</option>
              <option value="analyze">Analyze</option>
              <option value="explain">Explain code</option>
              <option value="review">Review code</option>
              <option value="word_count">Word count</option>
            </select>
            <button onClick={handleProcessFile} disabled={!selectedFile || isProcessing}>
              {isProcessing ? 'Processing...' : 'Process file'}
            </button>
          </div>
          {selectedFile && <div className="path-display">Selected: {selectedFile.name}</div>}
          {processingResult && <pre className="file-processing-result">{processingResult}</pre>}
        </div>

        <div className="file-toolbar">
          <button onClick={() => handleNavigate('~')}>
            <Home size={16} />
          </button>
          <button onClick={handleGoUp}>
            <ArrowUp size={16} />
          </button>
          <div className="path-display">{currentPath}</div>
          <div className="search-box">
            <Search size={14} />
            <input
              type="text"
              placeholder="Search..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
            />
          </div>
        </div>

        <div className="file-list">
          {filteredItems.length === 0 ? (
            <p className="no-files">No files found</p>
          ) : (
            filteredItems.map((item, index) => (
              <div 
                key={index} 
                className="file-item"
                onClick={() => handleItemClick(item)}
              >
                <div className="file-icon">
                  {item.type === 'directory' ? <Folder size={20} /> : <File size={20} />}
                </div>
                <div className="file-info">
                  <span className="file-name">{item.name}</span>
                  <span className="file-meta">
                    {item.size && `${item.size} • `}
                    {item.modified}
                  </span>
                </div>
                <div className="file-actions">
                  {item.type !== 'directory' && (
                    <button className="action-btn">
                      <Download size={14} />
                    </button>
                  )}
                  <button className="action-btn">
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
