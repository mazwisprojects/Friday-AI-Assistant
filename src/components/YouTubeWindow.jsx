import React, { useState, useEffect } from 'react';
import { Youtube, Search, Play, Plus, List, X, Clock } from 'lucide-react';

export default function YouTubeWindow({ position, onClose, onDrag }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [playlist, setPlaylist] = useState([]);
  const [currentVideo, setCurrentVideo] = useState(null);

  useEffect(() => {
    const socket = window.socket;
    
    socket.on('youtube_results', (data) => {
      setResults(data);
    });
    
    socket.on('playlist_updated', (data) => {
      setPlaylist(data);
    });
    
    socket.emit('get_playlist');
    
    return () => {
      socket.off('youtube_results');
      socket.off('playlist_updated');
    };
  }, []);

  const handleSearch = () => {
    if (query.trim()) {
      window.socket.emit('youtube_search', { query });
    }
  };

  const handlePlay = (video) => {
    setCurrentVideo(video);
    window.socket.emit('play_youtube', { videoId: video.id });
  };

  const handleAddToPlaylist = (video) => {
    window.socket.emit('add_to_playlist', { video });
  };

  const handleRemoveFromPlaylist = (index) => {
    window.socket.emit('remove_from_playlist', { index });
  };

  return (
    <div 
      className="window youtube-window"
      style={{ 
        transform: `translate(${position.x}px, ${position.y}px)`,
        width: '500px'
      }}
    >
      <div className="window-header" onMouseDown={onDrag}>
        <div className="window-title">
          <Youtube size={16} />
          <span>YouTube</span>
        </div>
        <button className="window-close" onClick={onClose}>
          <X size={16} />
        </button>
      </div>
      <div className="window-content">
        <div className="youtube-search">
          <input
            type="text"
            placeholder="Search YouTube..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
          />
          <button onClick={handleSearch}>
            <Search size={16} />
          </button>
        </div>

        {currentVideo && (
          <div className="video-player">
            <div className="video-placeholder">
              <Play size={32} />
              <span>{currentVideo.title}</span>
            </div>
          </div>
        )}

        <div className="youtube-results">
          <h4>Results</h4>
          {results.length === 0 ? (
            <p className="no-results">Search for videos above</p>
          ) : (
            results.map((video, index) => (
              <div key={index} className="video-item">
                <div className="video-thumbnail">
                  <img src={video.thumbnail} alt={video.title} />
                </div>
                <div className="video-info">
                  <span className="video-title">{video.title}</span>
                  <span className="video-meta">
                    {video.duration} • {video.views} views
                  </span>
                </div>
                <div className="video-actions">
                  <button onClick={() => handlePlay(video)}>
                    <Play size={14} />
                  </button>
                  <button onClick={() => handleAddToPlaylist(video)}>
                    <Plus size={14} />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>

        {playlist.length > 0 && (
          <div className="youtube-playlist">
            <div className="playlist-header">
              <List size={16} />
              <span>Playlist ({playlist.length})</span>
            </div>
            {playlist.map((video, index) => (
              <div key={index} className="playlist-item">
                <span className="playlist-title">{video.title}</span>
                <button onClick={() => handleRemoveFromPlaylist(index)}>
                  <X size={14} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
