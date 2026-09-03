import React, { useState, useEffect } from 'react';
import { 
  Activity, Cpu, HardDrive, Thermometer, Clock, Bell, Zap, 
  CheckCircle, AlertTriangle, X, ChevronDown, ChevronUp,
  Play, Pause, RotateCcw, Calendar, MessageSquare, FileText, Brain,
  Shield, Volume2, VolumeX, Eye, EyeOff, Coffee, Briefcase, Home
} from 'lucide-react';

export default function Dashboard({ position, onClose, onDrag }) {
  const [isExpanded, setIsExpanded] = useState(true);
  const [activeSection, setActiveSection] = useState('overview');
  
  // Dashboard state
  const [systemHealth, setSystemHealth] = useState({
    cpu_percent: 0,
    ram_percent: 0,
    cpu_temp_c: null,
    gpu_percent: null,
    uptime: '0h 0m',
    status: 'healthy'
  });
  
  const [activeTasks, setActiveTasks] = useState([]);
  const [pendingApprovals, setPendingApprovals] = useState([]);
  const [memorySummary, setMemorySummary] = useState({
    total_facts: 0,
    recent_conversations: 0,
    projects_count: 0,
    storage_used: '0 MB'
  });
  const [proactiveSuggestions, setProactiveSuggestions] = useState([]);
  const [routineQueue, setRoutineQueue] = useState([]);
  const [quietMode, setQuietMode] = useState(false);
  const [interruptPreferences, setInterruptPreferences] = useState({
    urgent_only: false,
    emergencies_only: false,
    custom_categories: []
  });
  const [currentMode, setCurrentMode] = useState('active');
  const [alerts, setAlerts] = useState([]);

  useEffect(() => {
    const socket = window.socket;
    
    // System health updates
    socket.on('system_monitor_data', (data) => {
      setSystemHealth(prev => ({
        ...prev,
        cpu_percent: data.cpu_percent,
        ram_percent: data.ram_percent,
        cpu_temp_c: data.cpu_temp_c,
        gpu_percent: data.gpu_percent,
        uptime: data.uptime,
        status: determineSystemStatus(data)
      }));
    });
    
    socket.on('dashboard_system_update', (data) => {
      setSystemHealth(prev => ({
        ...prev,
        cpu_percent: data.cpu_percent,
        ram_percent: data.ram_percent,
        cpu_temp_c: data.cpu_temp_c,
        gpu_percent: data.gpu_percent,
        uptime: data.uptime,
        status: determineSystemStatus(data)
      }));
    });
    
    // Active tasks updates
    socket.on('active_tasks_update', (data) => {
      setActiveTasks(data.tasks || []);
    });
    
    socket.on('dashboard_data', (data) => {
      if (data.active_tasks) setActiveTasks(data.active_tasks);
      if (data.pending_approvals) setPendingApprovals(data.pending_approvals);
      if (data.memory_summary) setMemorySummary(data.memory_summary);
      if (data.proactive_suggestions) setProactiveSuggestions(data.proactive_suggestions);
      if (data.routine_queue) setRoutineQueue(data.routine_queue);
      if (data.quiet_mode !== undefined) setQuietMode(data.quiet_mode);
      if (data.interrupt_preferences) setInterruptPreferences(data.interrupt_preferences);
      if (data.current_mode) setCurrentMode(data.current_mode);
    });
    
    // Pending approvals
    socket.on('pending_approvals_update', (data) => {
      setPendingApprovals(data.approvals || []);
    });
    
    // Memory summary
    socket.on('memory_summary_update', (data) => {
      setMemorySummary(data);
    });
    
    // Proactive suggestions
    socket.on('proactive_suggestions', (data) => {
      setProactiveSuggestions(data.suggestions || []);
    });
    
    // Routine queue
    socket.on('routine_queue_update', (data) => {
      setRoutineQueue(data.routines || []);
    });
    
    // Tool confirmation requests (for dashboard)
    socket.on('tool_confirmation_request', (data) => {
      setPendingApprovals(prev => [...prev, {
        id: data.id,
        tool: data.tool,
        description: `${data.tool} with args: ${data.args}`
      }]);
    });
    
    // Handle confirmation removal
    socket.on('confirmation_expired', (data) => {
      setPendingApprovals(prev => prev.filter(a => a.id !== data.id));
    });
    
    socket.on('approval_response_ack', (data) => {
      setPendingApprovals(prev => prev.filter(a => a.id !== data.approval_id));
    });
    
    // System alerts
    socket.on('system_alert', (data) => {
      setAlerts(prev => [...prev, {
        id: Date.now(),
        ...data,
        timestamp: new Date()
      }]);
    });
    
    // Get initial data
    socket.emit('get_system_monitor');
    socket.emit('get_dashboard_data');
    
    // Poll for updates
    const interval = setInterval(() => {
      socket.emit('get_system_monitor');
      socket.emit('get_dashboard_data');
    }, 3000);

    return () => {
      socket.off('system_monitor_data');
      socket.off('dashboard_system_update');
      socket.off('active_tasks_update');
      socket.off('dashboard_data');
      socket.off('pending_approvals_update');
      socket.off('memory_summary_update');
      socket.off('proactive_suggestions');
      socket.off('routine_queue_update');
      socket.off('system_alert');
      socket.off('tool_confirmation_request');
      socket.off('confirmation_expired');
      socket.off('approval_response_ack');
      clearInterval(interval);
    };
  }, []);

  const determineSystemStatus = (data) => {
    if (data.cpu_percent > 90 || data.ram_percent > 90 || (data.cpu_temp_c && data.cpu_temp_c > 85)) {
      return 'critical';
    } else if (data.cpu_percent > 70 || data.ram_percent > 70 || (data.cpu_temp_c && data.cpu_temp_c > 75)) {
      return 'warning';
    }
    return 'healthy';
  };

  const handleTaskAction = (taskId, action) => {
    const socket = window.socket;
    socket.emit('task_action', { task_id: taskId, action });
  };

  const handleApproval = (approvalId, approved) => {
    const socket = window.socket;
    socket.emit('approval_response', { approval_id: approvalId, approved });
  };

  const handleQuietModeToggle = () => {
    const newMode = !quietMode;
    setQuietMode(newMode);
    const socket = window.socket;
    socket.emit('set_quiet_mode', { enabled: newMode });
  };

  const handleInterruptPreferenceChange = (preference) => {
    setInterruptPreferences(prev => ({
      ...prev,
      ...preference
    }));
    const socket = window.socket;
    socket.emit('set_interrupt_preferences', preference);
  };

  const dismissAlert = (alertId) => {
    setAlerts(prev => prev.filter(a => a.id !== alertId));
  };

  const handleQuickAction = (action) => {
    if (action === 'restart_friday') {
      window.location.reload();
      return;
    }

    if (action === 'clear_alerts') {
      setAlerts([]);
      return;
    }
  };

  const renderOverview = () => (
    <div className="dashboard-overview">
      {/* Active Tasks */}
      {activeTasks.length > 0 && (
        <div className="dashboard-section">
          <div className="section-header">
            <Play size={18} />
            <h3>Active Tasks ({activeTasks.length})</h3>
          </div>
          <div className="tasks-list">
            {activeTasks.map(task => (
              <div key={task.id} className="task-item">
                <div className="task-info">
                  <div className="task-name">{task.name}</div>
                  <div className={`task-status status-${task.status}`}>{task.status}</div>
                </div>
                <div className="task-actions">
                  {task.status === 'running' && (
                    <button 
                      type="button"
                      className="task-btn pause"
                      onClick={() => handleTaskAction(task.id, 'pause')}
                    >
                      <Pause size={16} />
                    </button>
                  )}
                  <button 
                    type="button"
                    className="task-btn cancel"
                    onClick={() => handleTaskAction(task.id, 'cancel')}
                  >
                    <X size={16} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Pending Approvals */}
      {pendingApprovals.length > 0 && (
        <div className="dashboard-section urgent">
          <div className="section-header">
            <Shield size={18} />
            <h3>Pending Approvals ({pendingApprovals.length})</h3>
          </div>
          <div className="approvals-list">
            {pendingApprovals.map(approval => (
              <div key={approval.id} className="approval-item">
                <div className="approval-info">
                  <div className="approval-tool">{approval.tool}</div>
                  <div className="approval-description">{approval.description}</div>
                </div>
                <div className="approval-actions">
                  <button 
                    type="button"
                    className="approval-btn approve"
                    onClick={() => handleApproval(approval.id, true)}
                  >
                    <CheckCircle size={16} />
                  </button>
                  <button 
                    type="button"
                    className="approval-btn reject"
                    onClick={() => handleApproval(approval.id, false)}
                  >
                    <X size={16} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent Alerts */}
      {alerts.length > 0 && (
        <div className="dashboard-section alerts">
          <div className="section-header">
            <Bell size={18} />
            <h3>Recent Alerts ({alerts.length})</h3>
          </div>
          <div className="alerts-list">
            {alerts.slice(0, 5).map(alert => (
              <div key={alert.id} className={`alert-item severity-${alert.severity}`}>
                <AlertTriangle size={16} />
                <div className="alert-content">
                  <div className="alert-message">{alert.message}</div>
                  <div className="alert-time">{alert.timestamp?.toLocaleTimeString()}</div>
                </div>
                <button 
                  type="button"
                  className="alert-dismiss"
                  onClick={() => dismissAlert(alert.id)}
                >
                  <X size={14} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );

  return (
    <div 
      className="dashboard-permanent"
      style={{ 
        width: '100%',
        height: '100%',
        minHeight: 0,
        maxHeight: '100%',
        transition: 'transform 180ms ease-out, opacity 180ms ease-out, box-shadow 180ms ease-out',
        willChange: 'transform, opacity',
        backfaceVisibility: 'hidden',
      }}
    >
      <div className="dashboard-header">
        <div className="dashboard-title">
          <Activity size={16} />
          <span>Friday Dashboard</span>
        </div>
        <button 
          type="button"
          aria-pressed={isExpanded}
          className="dashboard-expand"
          onClick={() => setIsExpanded(!isExpanded)}
        >
          {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>
      </div>
      
      {isExpanded && (
        <>
          <div className="dashboard-nav">
            <button 
              type="button"
              aria-pressed={activeSection === 'overview'}
              className={`nav-btn ${activeSection === 'overview' ? 'active' : ''}`}
              onClick={() => setActiveSection('overview')}
            >
              <Activity size={16} />
              Overview
            </button>
          </div>
          
          <div className="dashboard-content">
            {activeSection === 'overview' && renderOverview()}
          </div>
        </>
      )}
    </div>
  );
}
