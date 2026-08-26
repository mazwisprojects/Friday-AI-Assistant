import React, { useEffect, useState } from 'react';
import { Contact, Plus, RefreshCw, Trash2, X } from 'lucide-react';

export default function ContactsWindow({ position, onClose, onDrag }) {
  const [contacts, setContacts] = useState([]);
  const [name, setName] = useState('');
  const [recipient, setRecipient] = useState('');
  const [platform, setPlatform] = useState('whatsapp');
  const [status, setStatus] = useState('');

  const refresh = () => window.socket.emit('get_contacts');

  useEffect(() => {
    const socket = window.socket;
    const handleContacts = (data) => setContacts(data.contacts || []);
    const handleContactStatus = (data) => {
      setStatus(data.msg || data.error || '');
      if (!data.error) refresh();
    };

    socket.on('contacts_list', handleContacts);
    socket.on('contacts_status', handleContactStatus);
    refresh();
    return () => {
      socket.off('contacts_list', handleContacts);
      socket.off('contacts_status', handleContactStatus);
    };
  }, []);

  const saveContact = (event) => {
    event.preventDefault();
    if (!name.trim() || !recipient.trim()) return;
    window.socket.emit('save_contact', { name, recipient, platform });
    setName('');
    setRecipient('');
  };

  const removeContact = (contactName) => {
    window.socket.emit('delete_contact', { name: contactName });
  };

  return (
    <div className="window contacts-window" style={{ transform: `translate(${position.x}px, ${position.y}px)`, width: '420px', height: '420px' }}>
      <div className="window-header" onMouseDown={onDrag}>
        <div className="window-title"><Contact size={16} /><span>Contacts HUD</span></div>
        <button className="window-close" onClick={onClose}><X size={16} /></button>
      </div>
      <div className="window-content">
        <form className="contact-form" onSubmit={saveContact}>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Contact name" />
          <input value={recipient} onChange={(e) => setRecipient(e.target.value)} placeholder="Username or number" />
          <select value={platform} onChange={(e) => setPlatform(e.target.value)}>
            <option value="whatsapp">WhatsApp</option>
            <option value="telegram">Telegram</option>
            <option value="discord">Discord</option>
            <option value="signal">Signal</option>
            <option value="instagram">Instagram</option>
            <option value="messenger">Messenger</option>
          </select>
          <button type="submit"><Plus size={14} /> Save contact</button>
        </form>

        <div className="contacts-toolbar">
          <span>{contacts.length} saved</span>
          <button onClick={refresh} title="Refresh contacts"><RefreshCw size={14} /></button>
        </div>

        <div className="contacts-list">
          {contacts.length === 0 ? <p className="no-files">No contacts saved.</p> : contacts.map((contact) => (
            <div className="contact-row" key={contact.name}>
              <div>
                <strong>{contact.name}</strong>
                <div className="contact-channels">
                  {Object.entries(contact.channels || {}).map(([key, value]) => <span key={key}>{key}: {value}</span>)}
                </div>
              </div>
              <button onClick={() => removeContact(contact.name)} title={`Remove ${contact.name}`}><Trash2 size={14} /></button>
            </div>
          ))}
        </div>
        {status && <p className="contact-status">{status}</p>}
      </div>
    </div>
  );
}
