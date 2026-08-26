import React, { useState, useEffect } from 'react';
import { Monitor, Plus, X, Grid, Image, Settings } from 'lucide-react';

export default function DesktopWindow({ position, onClose, onDrag }) {
  const [desktops, setDesktops] = useState([]);
  const [currentDesktop, setCurrentDesktop] = useState(1);

  useEffect(() => {
    const socket = window.socket;
    
    socket.on('desktop_list', (data) => {
      setDesktops(data);
    });
    
    socket.emit('get_desktops');
    
    return () => socket.off('desktop_list');
  }, []);

  const handleSwitch = (index) => {
    setCurrentDesktop(index + 1);
    window.socket.emit('switch_desktop', { desktop: index + 1 });
  };

  const handleAddDesktop = () => {
    window.socket.emit('add_desktop');
  };

  const handleSetWallpaper = () => {
    window.socket.emit('set_wallpaper');
  };

  return (
    <div 
      className="window desktop-window"
      style={{ 
        transform: `translate(${position.x}px, ${position.y}px)`,
        width: '400px'
      }}
    >
      <div className="window-header" onMouseDown={onDrag}>
        <div className="window-title">
          <Monitor size={16} />
          <span>Desktop Manager</span>
        </div>
        <button className="window-close" onClick={onClose}>
          <X size={16} />
        </button>
      </div>
      <div className="window-content">
        <div className="desktop-grid">
          {desktops.map((desktop, index) => (
            <div 
              key={index}
              className={`desktop-item ${currentDesktop === index + 1 ? 'active' : ''}`}
              onClick={() => handleSwitch(index)}
            >
              <Grid size={24} />
              <span>Desktop {index + 1}</span>
              {desktop.windowCount > 0 && (
                <span className="window-count">{desktop.windowCount}</span>
              )}
            </div>
          ))}
          <div className="desktop-item add" onClick={handleAddDesktop}>
            <Plus size={24} />
            <span>Add</span>
          </div>
        </div>

        <div className="desktop-actions">
          <button onClick={handleSetWallpaper}>
            <Image size={16} />
            Set Wallpaper
          </button>
          <button>
            <Settings size={16} />
            Display Settings
          </button>
        </div>

        <div className="desktop-info">
          <p>Current: Desktop {currentDesktop}</p>
          <p>Total: {desktops.length} desktops</p>
        </div>
      </div>
    </div>
  );
}
