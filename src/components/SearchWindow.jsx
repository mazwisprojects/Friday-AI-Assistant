import React, { useState, useEffect } from 'react';
import { Search, ExternalLink, X, Clock, Star } from 'lucide-react';

export default function SearchWindow({ position, onClose, onDrag }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [history, setHistory] = useState([]);

  useEffect(() => {
    const socket = window.socket;
    
    socket.on('search_results', (data) => {
      setResults(data.results);
    });
    
    socket.on('search_history', (data) => {
      setHistory(data);
    });
    
    socket.emit('get_search_history');
    
    return () => {
      socket.off('search_results');
      socket.off('search_history');
    };
  }, []);

  const handleSearch = () => {
    if (query.trim()) {
      window.socket.emit('web_search', { query });
    }
  };

  const handleHistoryClick = (item) => {
    setQuery(item.query);
    window.socket.emit('web_search', { query: item.query });
  };

  return (
    <div 
      className="window search-window"
      style={{ 
        transform: `translate(${position.x}px, ${position.y}px)`,
        width: '480px'
      }}
    >
      <div className="window-header" onMouseDown={onDrag}>
        <div className="window-title">
          <Search size={16} />
          <span>Web Search</span>
        </div>
        <button className="window-close" onClick={onClose}>
          <X size={16} />
        </button>
      </div>
      <div className="window-content">
        <div className="search-bar">
          <input
            type="text"
            placeholder="Search the web..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
          />
          <button onClick={handleSearch}>
            <Search size={16} />
          </button>
        </div>

        {history.length > 0 && results.length === 0 && (
          <div className="search-history">
            <h4>Recent Searches</h4>
            {history.slice(-5).map((item, index) => (
              <div 
                key={index} 
                className="history-item"
                onClick={() => handleHistoryClick(item)}
              >
                <Clock size={14} />
                <span>{item.query}</span>
              </div>
            ))}
          </div>
        )}

        <div className="search-results">
          {results.length === 0 ? (
            <p className="no-results">Enter a search query above</p>
          ) : (
            results.map((result, index) => (
              <div key={index} className="result-item">
                <div className="result-header">
                  <span className="result-title">{result.title}</span>
                  <a href={result.url} target="_blank" rel="noopener noreferrer">
                    <ExternalLink size={14} />
                  </a>
                </div>
                <div className="result-url">{result.url}</div>
                <div className="result-snippet">{result.snippet}</div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
