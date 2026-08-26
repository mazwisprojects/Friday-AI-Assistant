import React, { useState, useEffect } from 'react';
import { Cpu, HardDrive, Thermometer, Activity, Clock, X } from 'lucide-react';

export default function SystemMonitorWindow({ position, onClose, onDrag }) {
  const [metrics, setMetrics] = useState({
    cpu_percent: 0,
    ram_percent: 0,
    ram_used_gb: 0,
    ram_total_gb: 0,
    cpu_temp_c: null,
    gpu_percent: null,
    uptime: '0h 0m',
    process_count: 0
  });

  useEffect(() => {
    const socket = window.socket;
    
    socket.on('system_monitor_data', (data) => {
      setMetrics(data);
    });
    
    // Request initial data
    socket.emit('get_system_monitor');
    
    // Poll for updates every 2 seconds
    const interval = setInterval(() => {
      socket.emit('get_system_monitor');
    }, 2000);

    return () => {
      socket.off('system_monitor_data');
      clearInterval(interval);
    };
  }, []);

  const MetricBar = ({ icon: Icon, label, value, max = 100, unit = '%', color }) => (
    <div className="metric-item">
      <div className="metric-header">
        <Icon size={18} />
        <span>{label}</span>
        <span className="metric-value">{value}{unit}</span>
      </div>
      <div className="metric-bar">
        <div 
          className="metric-fill" 
          style={{ 
            width: `${Math.min(value, max)}%`,
            background: color 
          }} 
        />
      </div>
    </div>
  );

  return (
    <div 
      className="window system-monitor-window"
      style={{ 
        transform: `translate(${position.x}px, ${position.y}px)`,
        width: '380px'
      }}
    >
      <div className="window-header" onMouseDown={onDrag}>
        <div className="window-title">
          <Activity size={16} />
          <span>System Monitor</span>
        </div>
        <button className="window-close" onClick={onClose}>
          <X size={16} />
        </button>
      </div>
      <div className="window-content">
        <div className="metrics-grid">
          <MetricBar 
            icon={Cpu} 
            label="CPU" 
            value={metrics.cpu_percent} 
            color="#3b82f6"
          />
          <MetricBar 
            icon={HardDrive} 
            label="RAM" 
            value={metrics.ram_percent} 
            color="#8b5cf6"
          />
          {metrics.gpu_percent !== null && (
            <MetricBar 
              icon={Activity} 
              label="GPU" 
              value={metrics.gpu_percent} 
              color="#10b981"
            />
          )}
          {metrics.cpu_temp_c !== null && (
            <MetricBar 
              icon={Thermometer} 
              label="CPU Temp" 
              value={metrics.cpu_temp_c} 
              max={100}
              unit="°C"
              color={metrics.cpu_temp_c > 80 ? '#ef4444' : '#f59e0b'}
            />
          )}
        </div>
        
        <div className="system-info">
          <div className="info-item">
            <HardDrive size={16} />
            <span>RAM: {metrics.ram_used_gb} / {metrics.ram_total_gb} GB</span>
          </div>
          <div className="info-item">
            <Clock size={16} />
            <span>Uptime: {metrics.uptime}</span>
          </div>
          <div className="info-item">
            <Activity size={16} />
            <span>Processes: {metrics.process_count}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
