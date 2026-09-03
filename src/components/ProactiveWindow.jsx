import React, { useEffect, useState } from 'react';
import { Bell, Check, Clock, RefreshCw, X, Zap } from 'lucide-react';

export default function ProactiveWindow({ position, onClose, onDrag }) {
    const [suggestions, setSuggestions] = useState([]);
    const [busySuggestion, setBusySuggestion] = useState(null);

    useEffect(() => {
        const socket = window.socket;
        const handleSuggestions = (data) => setSuggestions(data?.suggestions || []);
        const handleAction = () => {
            setBusySuggestion(null);
            socket.emit('get_proactive_suggestions');
        };

        socket.on('proactive_suggestions', handleSuggestions);
        socket.on('suggestion_action_result', handleAction);
        socket.emit('get_proactive_suggestions');

        return () => {
            socket.off('proactive_suggestions', handleSuggestions);
            socket.off('suggestion_action_result', handleAction);
        };
    }, []);

    const actOnSuggestion = (id, action) => {
        setBusySuggestion(id);
        window.socket.emit('suggestion_action', { id, action });
    };

    return (
        <div className="window proactive-window" style={{ transform: `translate(${position.x}px, ${position.y}px)`, width: '440px' }}>
            <div className="window-header" onMouseDown={onDrag}>
                <div className="window-title"><Zap size={16} /><span>Proactive</span></div>
                <button type="button" className="window-close" onClick={onClose} aria-label="Close proactive suggestions"><X size={16} /></button>
            </div>
            <div className="window-content space-y-2">
                <div className="flex items-center justify-between text-[10px] uppercase tracking-wider text-cyan-500/70">
                    <span>Live recommendations</span>
                    <button type="button" onClick={() => window.socket.emit('get_proactive_suggestions')} className="hover:text-cyan-200" aria-label="Refresh suggestions"><RefreshCw size={14} /></button>
                </div>
                {suggestions.length === 0 ? (
                    <div className="flex flex-col items-center gap-2 py-9 text-xs text-cyan-500/60"><Bell size={22} />No proactive suggestions</div>
                ) : suggestions.map((suggestion) => (
                    <div key={suggestion.id} className="border border-cyan-900/50 bg-gray-900/60 p-3">
                        <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                                <div className="text-[10px] uppercase tracking-wider text-cyan-400/80">{suggestion.type}</div>
                                <div className="mt-1 text-xs text-cyan-100">{suggestion.message}</div>
                                <div className="mt-1 text-[10px] text-cyan-500/60">{suggestion.reason}</div>
                            </div>
                        </div>
                        <div className="mt-3 flex justify-end gap-2">
                            <button type="button" onClick={() => actOnSuggestion(suggestion.id, 'remind_later')} disabled={busySuggestion !== null} className="flex items-center gap-1 border border-cyan-900/60 px-2 py-1 text-[10px] text-cyan-300/80 hover:border-cyan-500 disabled:opacity-50"><Clock size={12} />Later</button>
                            <button type="button" onClick={() => actOnSuggestion(suggestion.id, 'accept')} disabled={busySuggestion !== null} className="flex items-center gap-1 border border-cyan-500/40 bg-cyan-500/10 px-2 py-1 text-[10px] text-cyan-100 hover:bg-cyan-500/20 disabled:opacity-50"><Check size={12} />Accept</button>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}