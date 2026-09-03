import React, { useEffect, useState } from 'react';
import { Archive, Brain, Briefcase, Database, MessageSquare, RefreshCw, RotateCcw, X } from 'lucide-react';

export default function MemoryWindow({ position, onClose, onDrag }) {
    const [summary, setSummary] = useState({ total_facts: 0, recent_conversations: 0, projects_count: 0, storage_used: '0 MB' });
    const [isCompacting, setIsCompacting] = useState(false);

    useEffect(() => {
        const socket = window.socket;
        const handleSummary = (data) => setSummary(data || {});
        const handleCompacted = () => {
            setIsCompacting(false);
            socket.emit('get_memory_summary');
        };

        socket.on('memory_summary_update', handleSummary);
        socket.on('memory_compacted', handleCompacted);
        socket.emit('get_memory_summary');

        return () => {
            socket.off('memory_summary_update', handleSummary);
            socket.off('memory_compacted', handleCompacted);
        };
    }, []);

    const stats = [
        { label: 'Stored Facts', value: summary.total_facts, icon: Brain },
        { label: 'Conversations', value: summary.recent_conversations, icon: MessageSquare },
        { label: 'Projects', value: summary.projects_count, icon: Briefcase },
        { label: 'Storage', value: summary.storage_used, icon: Database }
    ];

    const compactMemory = () => {
        setIsCompacting(true);
        window.socket.emit('compact_memory');
    };

    return (
        <div className="window memory-window" style={{ transform: `translate(${position.x}px, ${position.y}px)`, width: '420px' }}>
            <div className="window-header" onMouseDown={onDrag}>
                <div className="window-title"><Archive size={16} /><span>Memory</span></div>
                <button type="button" className="window-close" onClick={onClose} aria-label="Close memory"><X size={16} /></button>
            </div>
            <div className="window-content space-y-3">
                <div className="flex items-center justify-between text-[10px] uppercase tracking-wider text-cyan-500/70">
                    <span>Long-term memory</span>
                    <button type="button" className="hover:text-cyan-200" onClick={() => window.socket.emit('get_memory_summary')} aria-label="Refresh memory summary"><RefreshCw size={14} /></button>
                </div>
                <div className="grid grid-cols-2 gap-2">
                    {stats.map(({ label, value, icon: Icon }) => (
                        <div key={label} className="border border-cyan-900/50 bg-gray-900/60 p-3">
                            <Icon size={16} className="mb-2 text-cyan-500" />
                            <div className="text-lg text-cyan-100">{value ?? 0}</div>
                            <div className="text-[10px] uppercase tracking-wider text-cyan-500/60">{label}</div>
                        </div>
                    ))}
                </div>
                <button type="button" onClick={compactMemory} disabled={isCompacting} className="flex w-full items-center justify-center gap-2 border border-cyan-500/40 bg-cyan-500/10 px-3 py-2 text-xs text-cyan-200 transition-colors hover:bg-cyan-500/20 disabled:cursor-wait disabled:opacity-50">
                    <RotateCcw size={15} />
                    {isCompacting ? 'Compacting...' : 'Compact Memory'}
                </button>
            </div>
        </div>
    );
}