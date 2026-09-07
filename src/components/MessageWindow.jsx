import React, { useState, useEffect } from 'react';
import { MessageSquare, Send, X, User, Bot, Search } from 'lucide-react';

export default function MessageWindow({ position, onClose, onDrag }) {
  const [platform, setPlatform] = useState('whatsapp');
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [contacts, setContacts] = useState([]);
  const [selectedContact, setSelectedContact] = useState(null);

  useEffect(() => {
    const socket = window.socket;
    
    socket.on('message_history', (data) => {
      setMessages(data);
    });
    
    socket.on('contacts_list', (data) => {
      const arr = Array.isArray(data) ? data : (data && data.contacts) || [];
      setContacts(arr);
    });
    
    socket.emit('get_contacts', { platform });
    
    return () => {
      socket.off('message_history');
      socket.off('contacts_list');
    };
  }, [platform]);

  const handleSend = () => {
    if (newMessage.trim()) {
      window.socket.emit('send_message', {
        platform,
        message: newMessage,
        receiver: selectedContact?.channels?.[platform] || ''
      });
      setMessages([...messages, { 
        from: 'me', 
        text: newMessage, 
        timestamp: Date.now() 
      }]);
      setNewMessage('');
    }
  };

  return (
    <div 
      className="window message-window"
      style={{ 
        transform: `translate(${position.x}px, ${position.y}px)`,
        width: '450px',
        height: '500px'
      }}
    >
      <div className="window-header" onMouseDown={onDrag}>
        <div className="window-title">
          <MessageSquare size={16} />
          <span>Messaging</span>
        </div>
        <button className="window-close" onClick={onClose}>
          <X size={16} />
        </button>
      </div>
      <div className="window-content">
        <div className="message-toolbar">
          <select 
            value={platform} 
            onChange={(e) => { setPlatform(e.target.value); setSelectedContact(null); }}
          >
            <option value="whatsapp">WhatsApp</option>
            <option value="telegram">Telegram</option>
            <option value="slack">Slack</option>
            <option value="discord">Discord</option>
          </select>
        </div>

        <div className="contacts-list">
          <div className="contacts-header">
            <Search size={14} />
            <span>Contacts</span>
          </div>
          {contacts.map((contact, index) => (
            <div 
              key={index} 
              className={`contact-item ${selectedContact && selectedContact.name === contact.name ? 'selected' : ''}`}
              onClick={() => setSelectedContact(contact)}
              role="button"
              title={`Send via ${platform}`}
            >
              <User size={16} />
              <span>{contact.name}</span>
              {contact.channels && contact.channels[platform] && (
                <span className="contact-handle">{contact.channels[platform]}</span>
              )}
              {contact.online && <span className="online-dot" />}
            </div>
          ))}
        </div>

        <div className="messages-area">
          {messages.map((msg, index) => (
            <div 
              key={index} 
              className={`message ${msg.from === 'me' ? 'sent' : 'received'}`}
            >
              <div className="message-icon">
                {msg.from === 'me' ? <User size={12} /> : <Bot size={12} />}
              </div>
              <div className="message-content">
                <span>{msg.text}</span>
                <span className="message-time">
                  {new Date(msg.timestamp).toLocaleTimeString()}
                </span>
              </div>
            </div>
          ))}
        </div>

        <div className="message-input">
          <input
            type="text"
            placeholder="Type a message..."
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSend()}
          />
          <button onClick={handleSend}>
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
