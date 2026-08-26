import React, { useState, useEffect } from 'react';
import { Activity, Cpu, HardDrive, X, Trash2, RefreshCw } from 'lucide-react';

export default function ProcessWindow({ position, onClose, onDrag }) {
  const [processes, setProcesses] = useState([]);
  const [sortBy, setSortBy] = useState('cpu');

  useEffect(() => {
    const socket = window.socket;
    
    socket.on('process_list', (data) => {
      setProcesses(data);
    });
    
    socket.emit('get_process_list');
    
    const interval = setInterval(() => {
      socket.emit('get_process_list');
    }, 3000);

    return () => {
      socket.off('process_list');
      clearInterval(interval);
    };
  }, []);

  const handleKill = (pid) => {
    window.socket.emit('kill_process', { pid });
  };

  const handleRefresh = () => {
    window.socket.emit('get_process_list');
  };

  const sortedProcesses = [...processes].sort((a, b) => {
    return b[sortBy] - a[sortBy];
  });

  return (
    <div 
      className="window process-window"
      style={{ 
        transform: `translate(${position.x}px, ${position.y}px)`,
        width: '550px',
        height: '400px'
      }}
    >
      <div className="window-header" onMouseDown={onDrag}>
        <div className="window-title">
          <Activity size={16} />
          <span>Process Monitor</span>
        </div>
        <button className="window-close" onClick={onClose}>
          <X size={16} />
        </button>
      </div>
      <div className="window-content">
        <div className="process-toolbar">
          <select 
            value={sortBy} 
            onChange={(e) => setSortBy(e.target.value)}
          >
            <option value="cpu">Sort by CPU</option>
            <option value="memory">Sort by Memory</option>
            <option value="name">Sort by Name</option>
          </select>
          <button onClick={handleRefresh}>
            <RefreshCw size={14} />
            Refresh
          </button>
        </div>

        <div className="process-list">
          <div className="process-header">
            <span>PID</span>
            <span>Name</span>
            <span onClick={() => setSortBy('cpu')} className="sortable">
              CPU <Cpu size={12} />
            </span>
              <span onClick={() => setSortBy('memory')} className="sortable">
              Memory <HardDrive size={12} />
            </span>
            <span>Action</span>
          </div>
          {sortedProcesses.map((proc) => (
            <div key={proc.pid} className="process-item">
              <span className="pid">{proc.pid}</span>
              <span className="name">{proc.name}</span>
              <span className="cpu">{proc.cpu.toFixed(1)}%</span>
              <span className="memory">{(proc.memory / 1024 / 1024).toFixed(1)} MB</span>
              <button 
                className="kill-btn"
                onClick={() => handleKill(proc.pid)}
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
