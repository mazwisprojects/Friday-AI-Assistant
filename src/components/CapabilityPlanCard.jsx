import React, { useEffect, useRef, useState } from 'react';
import { useSocket } from '../contexts/SocketContext';

//: Kinds with a real end-to-end build path on the backend.
const IMPLEMENTABLE_KINDS = ['tool', 'agent'];

export default function CapabilityPlanCard() {
    const socket = useSocket();
    const [record, setRecord] = useState(null);
    const [request, setRequest] = useState('');
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const [notice, setNotice] = useState('');
    const pending = useRef(false);
    const mounted = useRef(true);

    useEffect(() => {
        mounted.current = true;
        const receive = (next) => {
            if (!next?.plan || !next.id) return;
            setRecord((previous) => (
                previous?.id === next.id && (previous?.version ?? 0) > (next.version ?? 0) ? previous : next
            ));
        };
        const disconnected = () => setError('Disconnected. Reconnect before reviewing this plan.');
        socket.on('capability_plan', receive);
        socket.on('disconnect', disconnected);
        return () => {
            mounted.current = false;
            socket.off('capability_plan', receive);
            socket.off('disconnect', disconnected);
        };
    }, [socket]);

    const submit = (event, payload, timeoutMs = 120000, keepRecordOnFailure = false) => {
        if (pending.current) return;
        if (!socket.connected) {
            setError('Friday is disconnected. No request was sent.');
            return;
        }
        pending.current = true;
        setBusy(true);
        setError('');
        setNotice('');
        socket.timeout(timeoutMs).emit(event, payload, (timeout, result) => {
            pending.current = false;
            if (!mounted.current) return;
            setBusy(false);
            // A failed build still returns its record so the card can show the
            // real reason instead of leaving a stale "approved" state on screen.
            if (keepRecordOnFailure && result?.record) setRecord(result.record);
            if (timeout || !result?.ok) {
                setError(timeout ? 'No acknowledgement received. The request may still finish; do not assume it failed.' : result?.error || 'Plan request failed.');
                return;
            }
            setRecord(result.record);
            setRequest('');
            setNotice(result.message || '');
        });
    };
    const draft = () => submit('capability_plan_request', {
        request, ...(record && record.status !== 'cancelled' ? { plan_id: record.id, version: record.version } : {})
    });
    const decide = (action) => submit('capability_plan_decision', {
        action, plan_id: record.id, version: record.version, content_hash: record.content_hash
    });
    // Building generates code and runs isolated tests, so allow a longer ack.
    const implement = () => submit('capability_plan_implement', {
        plan_id: record.id, version: record.version, content_hash: record.content_hash
    }, 300000, true);
    const implementable = !!record?.plan && IMPLEMENTABLE_KINDS.includes(record.plan.kind);
    const implementation = record && record.implementation && record.implementation.version === record.version ? record.implementation : null;
    const plan = record?.plan;

    // The card must stay invisible until Friday actually sends a plan to
    // review — no record means nothing to approve, edit, or build.
    if (!record) return null;

    // A malformed record (missing plan fields) must never take down the chat module.
    if (!plan) {
        return (
            <section aria-label="Capability planning" className="border border-red-700 p-3 text-sm">
                <h3 className="font-bold">CAPABILITY PLAN</h3>
                <p role="alert" className="text-red-300">Received a malformed plan record (missing plan details). Ignored.</p>
            </section>
        );
    }

    return (
        <section aria-label="Capability planning" className="border border-cyan-700 p-3 text-sm space-y-3" onMouseDown={(event) => event.stopPropagation()}>
            <h3 className="font-bold flex items-center justify-between">
                <span>CAPABILITY PLAN {`// v${record.version} — ${record.status}`}</span>
                <button type="button" aria-label="Dismiss plan" title="Hide this card; Friday will show it again when the plan changes"
                    className="text-cyan-300 hover:text-cyan-100 font-normal"
                    onClick={() => { setRecord(null); setError(''); setNotice(''); }}>✕</button>
            </h3>
            <>
                <h4>{record.plan.title} ({record.plan.kind})</h4>
                <p>{record.plan.goal}</p>
                {['steps', 'risks', 'advantages', 'permissions', 'tests'].map((field) => {
                    const items = Array.isArray(plan[field]) ? plan[field] : [];
                    return <div key={field}>
                        <strong className="capitalize">{field}</strong>
                        <ul className="list-disc pl-5">{items.length ? items.map((item, index) => <li key={index}>{item}</li>) : <li>None requested</li>}</ul>
                    </div>;
                })}
                <p><strong>First run:</strong> {record.plan.first_run}</p>
                <p><strong>Rollback:</strong> {record.plan.rollback}</p>
                <p>Model-drafted assessment; human review required. Approval records this version only, and building is bound to that exact approved version.</p>
                <div className="flex flex-wrap gap-3">
                    <button type="button" disabled={busy || record.status !== 'pending'} onClick={() => decide('approve')}>Approve plan v{record.version}</button>
                    <button type="button" disabled={busy || record.status !== 'approved' || !implementable}
                        title={implementable ? 'Build, test and register this exact approved version' : `${record.plan.kind} capabilities have no end-to-end build path yet`}
                        onClick={implement}>
                        {busy ? 'Working…' : `Build and register v${record.version}`}
                    </button>
                    <button type="button"
                        disabled={busy || record.status === 'cancelled' || record.status === 'implemented'}
                        title={record.status === 'implemented' ? 'This capability is live; edit the plan or disable the capability instead' : 'Cancel this plan'}
                        onClick={() => decide('cancel')}>Cancel plan</button>
                </div>
                {implementation && <div aria-label="Implementation result" className="border border-cyan-800 p-2 space-y-1">
                    <p><strong>Build:</strong> {implementation.status}{implementation.artifact ? ` — ${implementation.artifact}` : ''}</p>
                    {implementation.replaced_existing && <p>This replaced the previous version of the same capability.</p>}
                    {implementation.error ? <p role="alert" className="text-red-300">{implementation.error}</p> : null}
                    {record.execution_available && implementation.first_run && <p>
                        First run with no arguments: exit {implementation.first_run.returncode}
                        {implementation.first_run.stdout?.trim() ? ` — ${implementation.first_run.stdout.trim()}` : ''}
                    </p>}
                    {record.execution_available && !implementation.first_run && <p>Smoke test ran in an isolated process.</p>}
                </div>}
            </>}
            <label className="block">
                {record && record.status !== 'cancelled' ? 'Edit plan — describe your changes' : 'Describe a capability to plan'}
                <textarea value={request} maxLength={4000} disabled={busy} onChange={(event) => setRequest(event.target.value)} className="block w-full bg-black border border-cyan-700 p-2" />
            </label>
            <button type="button" disabled={busy || !request.trim()} onClick={draft}>
                {busy ? 'Working…' : record && record.status !== 'cancelled' ? 'Edit and reassess' : 'Draft plan'}
            </button>
            {notice && <p role="status" className="text-cyan-300">{notice}</p>}
            {error && <p role="alert" className="text-red-300">{error}</p>}
        </section>
    );
}
