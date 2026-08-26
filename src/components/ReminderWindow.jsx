import React, { useState, useEffect } from 'react';
import { Bell, Plus, Trash2, Clock, X } from 'lucide-react';

export default function ReminderWindow({ position, onClose, onDrag }) {
  const [reminders, setReminders] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [newReminder, setNewReminder] = useState({
    message: '',
    date: '',
    time: ''
  });

  useEffect(() => {
    const socket = window.socket;
    
    socket.on('reminders_list', (data) => {
      setReminders(data);
    });
    
    socket.emit('get_reminders');
    
    return () => socket.off('reminders_list');
  }, []);

  const handleAdd = () => {
    if (newReminder.message && newReminder.date && newReminder.time) {
      window.socket.emit('add_reminder', newReminder);
      setNewReminder({ message: '', date: '', time: '' });
      setShowAdd(false);
    }
  };

  const handleDelete = (id) => {
    window.socket.emit('delete_reminder', { id });
  };

  const formatDateTime = (date, time) => {
    const d = new Date(`${date}T${time}`);
    return d.toLocaleDateString('en-US', { 
      weekday: 'short', 
      month: 'short', 
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit'
    });
  };

  const getTimeRemaining = (date, time) => {
    const target = new Date(`${date}T${time}`);
    const now = new Date();
    const diff = target - now;
    
    if (diff < 0) return 'Expired';
    
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
    
    if (days > 0) return `${days}d ${hours}h`;
    if (hours > 0) return `${hours}h ${minutes}m`;
    return `${minutes}m`;
  };

  return (
    <div 
      className="window reminder-window"
      style={{ 
        transform: `translate(${position.x}px, ${position.y}px)`,
        width: '420px'
      }}
    >
      <div className="window-header" onMouseDown={onDrag}>
        <div className="window-title">
          <Bell size={16} />
          <span>Reminders</span>
        </div>
        <button className="window-close" onClick={onClose}>
          <X size={16} />
        </button>
      </div>
      <div className="window-content">
        <button 
          className="add-reminder-btn"
          onClick={() => setShowAdd(!showAdd)}
        >
          <Plus size={16} />
          Add Reminder
        </button>

        {showAdd && (
          <div className="reminder-form">
            <input
              type="text"
              placeholder="Reminder message..."
              value={newReminder.message}
              onChange={(e) => setNewReminder({...newReminder, message: e.target.value})}
            />
            <input
              type="date"
              value={newReminder.date}
              onChange={(e) => setNewReminder({...newReminder, date: e.target.value})}
            />
            <input
              type="time"
              value={newReminder.time}
              onChange={(e) => setNewReminder({...newReminder, time: e.target.value})}
            />
            <button onClick={handleAdd}>Set Reminder</button>
          </div>
        )}

        <div className="reminders-list">
          {reminders.length === 0 ? (
            <p className="no-reminders">No active reminders</p>
          ) : (
            reminders.map((reminder) => (
              <div key={reminder.id} className="reminder-item">
                <div className="reminder-content">
                  <Clock size={16} />
                  <div className="reminder-text">
                    <span className="reminder-message">{reminder.message}</span>
                    <span className="reminder-time">
                      {formatDateTime(reminder.date, reminder.time)}
                    </span>
                  </div>
                </div>
                <div className="reminder-meta">
                  <span className="time-remaining">
                    {getTimeRemaining(reminder.date, reminder.time)}
                  </span>
                  <button 
                    className="delete-btn"
                    onClick={() => handleDelete(reminder.id)}
                  >
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
