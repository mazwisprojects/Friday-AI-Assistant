import React, { useState, useEffect } from 'react';
import { Folder, File, Search, Home, ArrowUp, X, Trash2, Download } from 'lucide-react';

export default function FileManagerWindow({ position, onClose, onDrag }) {
  const [currentPath, setCurrentPath] = useState('');
  const [items, setItems] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    const socket = window.socket;
    
    socket.on('directory_contents', (data) => {
      setItems(data.items);
      setCurrentPath(data.path);
    });
    
    // Load home directory
    socket.emit('read_directory', { path: '~' });
    
    return () => socket.off('directory_contents');
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
      socket.emit('search_files', { query: searchQuery, path: currentPath });
    }
  };

  const handleItemClick = (item) => {
    if (item.type === 'directory') {
      handleNavigate(item.path);
    } else {
      // Could open file preview
      socket.emit('read_file', { path: item.path });
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
