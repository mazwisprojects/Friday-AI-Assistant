import React, { useState, useEffect } from 'react';
import { Gamepad2, Play, Download, X, Star, Clock } from 'lucide-react';

export default function GameWindow({ position, onClose, onDrag }) {
  const [games, setGames] = useState([]);
  const [updates, setUpdates] = useState([]);

  useEffect(() => {
    const socket = window.socket;
    
    socket.on('game_library', (data) => {
      setGames(data);
    });
    
    socket.on('game_updates', (data) => {
      setUpdates(data);
    });
    
    socket.emit('get_game_library');
    socket.emit('check_game_updates');
    
    return () => {
      socket.off('game_library');
      socket.off('game_updates');
    };
  }, []);

  const handleLaunch = (game) => {
    window.socket.emit('launch_game', { gameId: game.id });
  };

  const handleUpdate = (game) => {
    window.socket.emit('update_game', { gameId: game.id });
  };

  return (
    <div 
      className="window game-window"
      style={{ 
        transform: `translate(${position.x}px, ${position.y}px)`,
        width: '500px',
        height: '450px'
      }}
    >
      <div className="window-header" onMouseDown={onDrag}>
        <div className="window-title">
          <Gamepad2 size={16} />
          <span>Game Library</span>
        </div>
        <button className="window-close" onClick={onClose}>
          <X size={16} />
        </button>
      </div>
      <div className="window-content">
        {updates.length > 0 && (
          <div className="game-updates">
            <h4>Updates Available ({updates.length})</h4>
            {updates.map((game, index) => (
              <div key={index} className="update-item">
                <span className="update-name">{game.name}</span>
                <button onClick={() => handleUpdate(game)}>
                  <Download size={14} />
                  Update
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="game-library">
          <h4>Library ({games.length})</h4>
          {games.length === 0 ? (
            <p className="no-games">No games found</p>
          ) : (
            games.map((game, index) => (
              <div key={index} className="game-item">
                <div className="game-icon">
                  <Gamepad2 size={32} />
                </div>
                <div className="game-info">
                  <span className="game-name">{game.name}</span>
                  <span className="game-meta">
                    {game.lastPlayed && (
                      <>
                        <Clock size={12} />
                        {new Date(game.lastPlayed).toLocaleDateString()}
                      </>
                    )}
                  </span>
                  <div className="game-rating">
                    {[...Array(5)].map((_, i) => (
                      <Star 
                        key={i} 
                        size={12} 
                        fill={i < game.rating ? 'currentColor' : 'none'}
                      />
                    ))}
                  </div>
                </div>
                <div className="game-actions">
                  <button onClick={() => handleLaunch(game)}>
                    <Play size={16} />
                    Play
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
