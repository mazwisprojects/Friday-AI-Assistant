import React, { useState, useEffect } from 'react';
import { Mouse, Keyboard, Play, Square, RotateCcw, X, Activity } from 'lucide-react';

export default function ControlWindow({ position, onClose, onDrag }) {
  const [isRecording, setIsRecording] = useState(false);
  const [actions, setActions] = useState([]);
  const [isPlaying, setIsPlaying] = useState(false);

  useEffect(() => {
    const socket = window.socket;
    
    socket.on('control_action', (data) => {
      setActions(prev => [...prev, { ...data, timestamp: Date.now() }]);
    });
    
    socket.on('recording_status', (data) => {
      setIsRecording(data.recording);
    });
    
    return () => {
      socket.off('control_action');
      socket.off('recording_status');
    };
  }, []);

  const handleStartRecording = () => {
    window.socket.emit('start_recording');
  };

  const handleStopRecording = () => {
    window.socket.emit('stop_recording');
  };

  const handlePlay = () => {
    setIsPlaying(true);
    window.socket.emit('play_recording');
    setTimeout(() => setIsPlaying(false), 2000);
  };

  const handleClear = () => {
    setActions([]);
    window.socket.emit('clear_recording');
  };

  return (
    <div 
      className="window control-window"
      style={{ 
        transform: `translate(${position.x}px, ${position.y}px)`,
        width: '450px'
      }}
    >
      <div className="window-header" onMouseDown={onDrag}>
        <div className="window-title">
          <Mouse size={16} />
          <span>Computer Control</span>
        </div>
        <button className="window-close" onClick={onClose}>
          <X size={16} />
        </button>
      </div>
      <div className="window-content">
        <div className="control-toolbar">
          <button 
            className={isRecording ? 'recording' : ''}
            onClick={isRecording ? handleStopRecording : handleStartRecording}
          >
            {isRecording ? <Square size={16} /> : <Play size={16} />}
            {isRecording ? 'Stop' : 'Record'}
          </button>
          <button onClick={handlePlay} disabled={actions.length === 0}>
            <Play size={16} />
            Replay
          </button>
          <button onClick={handleClear} disabled={actions.length === 0}>
            <RotateCcw size={16} />
            Clear
          </button>
        </div>

        <div className="actions-log">
          <div className="log-header">
            <Activity size={14} />
            <span>Action Log ({actions.length})</span>
          </div>
          <div className="log-content">
            {actions.length === 0 ? (
              <p className="no-actions">No actions recorded</p>
            ) : (
              actions.slice(-10).map((action, index) => (
                <div key={index} className="action-item">
                  <span className="action-type">{action.type}</span>
                  <span className="action-details">{action.details}</span>
                  <span className="action-time">
                    {new Date(action.timestamp).toLocaleTimeString()}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="control-info">
          <p>Record mouse/keyboard actions for automation</p>
        </div>
      </div>
    </div>
  );
}
