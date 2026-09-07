import React, { useEffect, useRef, useState } from 'react';
import { AlertTriangle, Bot, CheckCircle2, Play, RefreshCw, X } from 'lucide-react';

const EMPTY_AUTONOMY = { proposals: [], security_findings: [], phases: {} };
const EMPTY_CONSOLE = { plugins: [], schedules: [], executions: [] };

const asStatus = (data) => ({
    reachable: false, provider: 'gemini', model: '', plugins: 0, agents: 0,
    ...(data && typeof data === 'object' ? data : {}),
});
const asConsole = (data) => {
    const d = data && typeof data === 'object' ? data : {};
    return {
        plugins: Array.isArray(d.plugins) ? d.plugins : [],
        schedules: Array.isArray(d.schedules) ? d.schedules : [],
        executions: Array.isArray(d.executions) ? d.executions : [],
    };
};
const asAutonomy = (data) => {
    const d = data && typeof data === 'object' ? data : {};
    return {
        phases: d.phases && typeof d.phases === 'object' ? d.phases : {},
        proposals: Array.isArray(d.proposals) ? d.proposals : [],
        security_findings: Array.isArray(d.security_findings) ? d.security_findings : [],
    };
};

export default function OpenClawWindow({ position, onClose, onDrag }) {
    const [status, setStatus] = useState(asStatus(null));
    const [lastPlan, setLastPlan] = useState('No routed request yet');
    const [toolCount, setToolCount] = useState(0);
    const [consoleData, setConsoleData] = useState(EMPTY_CONSOLE);
    const [autonomy, setAutonomy] = useState(EMPTY_AUTONOMY);
    const [refreshing, setRefreshing] = useState(false);
    const [lastUpdated, setLastUpdated] = useState(null);
    const pendingRef = useRef(0);
    const timeoutRef = useRef(null);

    const settleRefresh = () => {
        if (pendingRef.current <= 0) return;
        pendingRef.current -= 1;
        if (pendingRef.current === 0) {
            setRefreshing(false);
            setLastUpdated(new Date());
        }
    };

    const refresh = () => {
        pendingRef.current = 4;
        setRefreshing(true);
        window.socket.emit('get_openclaw_status');
        window.socket.emit('get_openclaw_capabilities');
        window.socket.emit('get_agent_console');
        window.socket.emit('get_autonomy_status');
        if (timeoutRef.current) clearTimeout(timeoutRef.current);
        timeoutRef.current = setTimeout(() => {
            pendingRef.current = 0;
            setRefreshing(false);
            setLastUpdated(new Date());
        }, 8000);
    };

    useEffect(() => {
        const handleStatus = (data) => { setStatus(asStatus(data)); settleRefresh(); };
        window.socket.on('openclaw_status', handleStatus);
        const handleCapabilities = (data) => { setToolCount(data?.friday_tools?.length || 0); settleRefresh(); };
        window.socket.on('openclaw_capabilities', handleCapabilities);
        const handleNotification = (notification) => {
            if (notification?.category === 'openclaw') setLastPlan(notification.message);
        };
        window.socket.on('unified_notification', handleNotification);
        const handleConsole = (data) => { setConsoleData(asConsole(data)); settleRefresh(); };
        window.socket.on('agent_console', handleConsole);
        const handleAutonomy = (data) => { setAutonomy(asAutonomy(data)); settleRefresh(); };
        window.socket.on('autonomy_status', handleAutonomy);
        refresh();
        return () => {
            if (timeoutRef.current) clearTimeout(timeoutRef.current);
            window.socket.off('openclaw_status', handleStatus);
            window.socket.off('openclaw_capabilities', handleCapabilities);
            window.socket.off('unified_notification', handleNotification);
            window.socket.off('agent_console', handleConsole);
            window.socket.off('autonomy_status', handleAutonomy);
            if (timeoutRef.current) clearTimeout(timeoutRef.current);
        };
    }, []);

    const agentPlugins = consoleData.plugins.filter(plugin => plugin.kind === 'agent');
    const action = (payload) => window.socket.emit('agent_console_action', payload);
    const approveProposal = (proposalId) => window.socket.emit('approve_autonomy_proposal', { proposal_id: proposalId });
    const resolveFinding = (finding) => window.socket.emit('resolve_security_finding', { finding_path: finding.path, finding_value: finding.value });

    return (
        <div className="window openclaw-window" style={{ transform: `translate(${position.x}px, ${position.y}px)`, width: '420px' }}>
            <div className="window-header" data-drag-handle onMouseDown={onDrag}>
                <div className="window-title"><Bot size={16} /><span>OpenClaw Orchestrator</span></div>
                <button type="button" className="window-close" onClick={onClose} aria-label="Close OpenClaw"><X size={16} /></button>
            </div>
            <div className="window-content space-y-3">
                <div className={`border p-3 ${status.reachable ? 'border-green-500/40 bg-green-500/5' : 'border-amber-500/40 bg-amber-500/5'}`}>
                    <div className="flex items-center justify-between gap-3 text-xs">
                        <span className="flex items-center gap-2 text-cyan-100"><Bot size={15} /> Gateway</span>
                        <span className={status.reachable ? 'text-green-300' : 'text-amber-300'}>{status.reachable ? 'ONLINE' : 'FALLBACK'}</span>
                    </div>
                    <p className="mt-2 text-[10px] leading-relaxed text-cyan-300/60">
                        {status.reachable ? 'Friday can use the installed OpenClaw Gateway.' : 'Friday is using direct Gemini reasoning while the Gateway is unavailable or unpaired.'}
                    </p>
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="border border-cyan-900/50 bg-gray-900/60 p-3"><span className="text-cyan-500/60">PROVIDER</span><div className="mt-1 text-cyan-100 uppercase">{status.provider || 'gemini'}</div></div>
                    <div className="border border-cyan-900/50 bg-gray-900/60 p-3"><span className="text-cyan-500/60">MODEL</span><div className="mt-1 truncate text-cyan-100">{status.model || '--'}</div></div>
                    <div className="border border-cyan-900/50 bg-gray-900/60 p-3"><span className="text-cyan-500/60">PLUGINS</span><div className="mt-1 text-cyan-100">{status.plugins || 0}</div></div>
                    <div className="border border-cyan-900/50 bg-gray-900/60 p-3"><span className="text-cyan-500/60">AGENTS</span><div className="mt-1 text-cyan-100">{status.agents || 0}</div></div>
                    <div className="border border-cyan-900/50 bg-gray-900/60 p-3"><span className="text-cyan-500/60">FRIDAY TOOLS</span><div className="mt-1 text-cyan-100">{toolCount}</div></div>
                </div>
                <div className="border border-cyan-900/50 bg-gray-900/60 p-3 text-[10px] text-cyan-300/70"><span className="text-cyan-500/60">LAST PLAN</span><div className="mt-1 text-cyan-100">{lastPlan}</div></div>
                <div className="border border-cyan-900/50 bg-gray-900/60 p-3">
                    <div className="mb-2 flex items-center justify-between text-[10px] text-cyan-500/60"><span>AGENT LIFECYCLE</span><span>{agentPlugins.length} REGISTERED</span></div>
                    <div className="max-h-48 space-y-1 overflow-y-auto">
                        {agentPlugins.map((agent) => (
                            <div key={agent.name} className="flex items-center justify-between gap-2 border-l border-cyan-700/50 bg-black/30 px-2 py-1 text-[10px]">
                                <span className={agent.enabled ? 'text-cyan-100' : 'text-gray-500'}>{agent.name}</span>
                                <span className="flex items-center gap-1">
                                    <button type="button" title="Test agent" onClick={() => action({ action: 'test', name: agent.name })} className="text-green-300"><CheckCircle2 size={12} /></button>
                                    <button type="button" title="Run agent" onClick={() => action({ action: 'deploy', name: agent.name })} className="text-cyan-300"><Play size={12} /></button>
                                    <button type="button" title={agent.enabled ? 'Disable agent' : 'Enable agent'} onClick={() => action({ action: agent.enabled ? 'disable' : 'enable', name: agent.name })} className={agent.enabled ? 'text-amber-300' : 'text-green-300'}>{agent.enabled ? 'OFF' : 'ON'}</button>
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
                <div className="border border-amber-500/30 bg-amber-500/5 p-3">
                    <div className="mb-2 flex items-center justify-between text-[10px] text-amber-300"><span>APPROVAL QUEUE</span><span>{autonomy.proposals.length + autonomy.security_findings.length} PENDING</span></div>
                    <div className="max-h-40 space-y-1 overflow-y-auto">
                        {autonomy.proposals.map(proposal => <div key={proposal.id} className="flex items-center justify-between gap-2 border-l border-amber-400/50 px-2 py-1 text-[10px]"><span className="min-w-0 truncate text-amber-100">{proposal.name} / {proposal.priority || 'normal'}</span><button type="button" onClick={() => approveProposal(proposal.id)} className="shrink-0 text-green-300">APPROVE</button></div>)}
                        {autonomy.security_findings.map((finding, index) => (
                            <div key={`${finding.path}-${index}`} className="flex items-center justify-between gap-2 border-l border-red-400/50 px-2 py-1 text-[10px]">
                                <span className="min-w-0 truncate text-red-300" title={finding.path}>SECURITY: {finding.value || finding.path}{finding.path ? ` @ ${finding.path.split(/[\\/]/).pop()}` : ''}</span>
                                <button type="button" onClick={() => resolveFinding(finding)} className="shrink-0 text-amber-300" title={`Accept finding in ${finding.path}`}>RESOLVE</button>
                            </div>
                        ))}
                        {!autonomy.proposals.length && !autonomy.security_findings.length && <div className="text-[10px] text-cyan-500/50">No pending proposals</div>}
                    </div>
                </div>
                <div className="border border-cyan-900/50 bg-gray-900/60 p-3 text-[10px]">
                    <div className="mb-2 flex items-center justify-between text-cyan-500/60"><span>SCHEDULES</span><span>{consoleData.schedules.length}</span></div>
                    <div className="max-h-24 space-y-1 overflow-y-auto">{consoleData.schedules.map(schedule => <div key={schedule.id} className="flex justify-between gap-2 text-cyan-200/80"><span className="truncate">{schedule.key || schedule.agent_type}</span><span>{schedule.enabled ? 'ON' : 'OFF'}</span></div>)}</div>
                </div>
                {!status.reachable && <div className="flex items-start gap-2 text-[10px] text-amber-200/75"><AlertTriangle size={14} className="shrink-0" /> OpenClaw must be reachable and paired before Friday can route plans through the external Gateway.</div>}
                <button type="button" onClick={refresh} disabled={refreshing} className="flex w-full items-center justify-center gap-2 border border-cyan-500/40 bg-cyan-500/10 px-3 py-2 text-xs text-cyan-200 hover:bg-cyan-500/20 disabled:cursor-wait disabled:opacity-60"><RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} /> {refreshing ? 'Refreshing…' : 'Refresh status'}</button>
                {lastUpdated && <div className="text-center text-[10px] text-cyan-500/50">{refreshing ? 'Refreshing…' : `Updated ${lastUpdated.toLocaleTimeString()}`}</div>}
            </div>
        </div>
    );
}
