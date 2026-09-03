import React, { useEffect, useState } from 'react';
import { Calendar, Play, RefreshCw, X } from 'lucide-react';

export default function RoutinesWindow({ position, onClose, onDrag }) {
    const [routines, setRoutines] = useState([]);
    const [runningRoutine, setRunningRoutine] = useState(null);

    useEffect(() => {
        const socket = window.socket;
        const handleQueue = (data) => setRoutines(data?.routines || []);
        const handleResult = (data) => {
            setRunningRoutine(null);
            if (data?.success === false) return;
            socket.emit('get_routine_queue');
        };

        socket.on('routine_queue_update', handleQueue);
        socket.on('routine_execution_result', handleResult);
        socket.emit('get_routine_queue');

        return () => {
            socket.off('routine_queue_update', handleQueue);
            socket.off('routine_execution_result', handleResult);
        };
    }, []);

    const runRoutine = (name) => {
        setRunningRoutine(name);
        window.socket.emit('run_routine', { name });
    };

    return (
        <div
            className="window routines-window"
            style={{ transform: `translate(${position.x}px, ${position.y}px)`, width: '420px' }}
        >
            <div className="window-header" onMouseDown={onDrag}>
                <div className="window-title">
                    <Calendar size={16} />
                    <span>Routines</span>
                </div>
                <button type="button" className="window-close" onClick={onClose} aria-label="Close routines">
                    <X size={16} />
                </button>
            </div>
            <div className="window-content space-y-2">
                <div className="flex items-center justify-between text-[10px] uppercase tracking-wider text-cyan-500/70">
                    <span>Automation library</span>
                    <button type="button" className="hover:text-cyan-200" onClick={() => window.socket.emit('get_routine_queue')} aria-label="Refresh routines">
                        <RefreshCw size={14} />
                    </button>
                </div>
                {routines.length === 0 ? (
                    <div className="py-8 text-center text-xs text-cyan-500/60">No routines are available while Friday is offline.</div>
                ) : routines.map((routine) => (
                    <div key={routine.id} className="flex items-center justify-between gap-3 border border-cyan-900/50 bg-gray-900/60 p-3">
                        <div className="min-w-0">
                            <div className="text-xs text-cyan-100 capitalize">{routine.name}</div>
                            <div className="mt-1 text-[10px] text-cyan-500/60">{routine.description}</div>
                        </div>
                        <button
                            type="button"
                            onClick={() => runRoutine(routine.id)}
                            disabled={runningRoutine !== null}
                            className="shrink-0 border border-cyan-500/40 bg-cyan-500/10 p-2 text-cyan-300 transition-colors hover:bg-cyan-500/20 disabled:cursor-wait disabled:opacity-50"
                            aria-label={`Run ${routine.name}`}
                        >
                            <Play size={15} />
                        </button>
                    </div>
                ))}
            </div>
        </div>
    );
}