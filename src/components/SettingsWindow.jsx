import React, { useState, useEffect } from 'react';
import { Activity, Bell, Coffee, Home, Link, Unlink, Volume2, VolumeX, X } from 'lucide-react';

const TOOLS = [
    { id: 'generate_cad', label: 'Generate CAD' },
    { id: 'run_web_agent', label: 'Web Agent' },
    { id: 'create_directory', label: 'Create Folder' },
    { id: 'write_file', label: 'Write File' },
    { id: 'read_directory', label: 'Read Directory' },
    { id: 'read_file', label: 'Read File' },
    { id: 'create_project', label: 'Create Project' },
    { id: 'switch_project', label: 'Switch Project' },
    { id: 'list_projects', label: 'List Projects' },
    { id: 'search_memory', label: 'Search Memory' },
    { id: 'list_smart_devices', label: 'List Devices' },
    { id: 'control_light', label: 'Control Light' },
    { id: 'discover_printers', label: 'Discover Printers' },
    { id: 'print_stl', label: 'Print 3D Model' },
    { id: 'iterate_cad', label: 'Iterate CAD' },
    { id: 'computer_control', label: 'Computer Control' },
    { id: 'computer_settings', label: 'Computer Settings' },
    { id: 'manage_files', label: 'Manage Files' },
    { id: 'open_application', label: 'Open Application' },
    { id: 'get_system_status', label: 'System Status' },
    { id: 'get_weather', label: 'Get Weather' },
    { id: 'set_reminder', label: 'Set Reminder' },
    { id: 'desktop_control', label: 'Desktop Control' },
    { id: 'web_search', label: 'Web Search' },
    { id: 'send_message', label: 'Send Message' },
    { id: 'youtube_video', label: 'YouTube Video' },
    { id: 'browser_control', label: 'Browser Control' },
    { id: 'code_helper', label: 'Code Helper' },
    { id: 'build_project', label: 'Build Project' },
    { id: 'find_flights', label: 'Find Flights' },
    { id: 'game_updater', label: 'Game Updater' },
    { id: 'process_file', label: 'Process File' },
    { id: 'manage_monitors', label: 'Manage Monitors' },
    { id: 'contacts_manager', label: 'Contacts Manager' },
    { id: 'undo_last_action', label: 'Undo Last Action' },
    { id: 'cancel_current_task', label: 'Cancel Current Task' },
    { id: 'self_maintenance', label: 'Self Maintenance' },
];

const SettingsWindow = ({
    socket,
    micDevices,
    speakerDevices,
    webcamDevices,
    selectedMicId,
    setSelectedMicId,
    selectedSpeakerId,
    setSelectedSpeakerId,
    selectedWebcamId,
    setSelectedWebcamId,
    cursorSensitivity,
    setCursorSensitivity,
    isCameraFlipped,
    setIsCameraFlipped,
    handleFileUpload,
    onClose
}) => {
    const [permissions, setPermissions] = useState({});
    const [faceAuthEnabled, setFaceAuthEnabled] = useState(false);
    const [systemAlertsEnabled, setSystemAlertsEnabled] = useState(true);
    const [quietMode, setQuietMode] = useState(false);
    const [interruptPreferences, setInterruptPreferences] = useState({
        urgent_only: false,
        emergencies_only: false
    });
    const [currentMode, setCurrentMode] = useState('active');
    const [googleAccount, setGoogleAccount] = useState({ connected: false, connecting: false, error: '' });
    const [providerRouting, setProviderRouting] = useState({
        voice_vision: 'Gemini Live', text_reasoning: 'Gemini', coding: 'OpenClaw', documents: 'OpenClaw', background_agents: 'OpenClaw'
    });

    useEffect(() => {
        // Request initial permissions
        socket.emit('get_settings');

        // Listen for updates
        const handleSettings = (settings) => {
            console.log("Received settings:", settings);
            if (settings) {
                if (settings.tool_permissions) setPermissions(settings.tool_permissions);
                if (typeof settings.face_auth_enabled !== 'undefined') {
                    setFaceAuthEnabled(settings.face_auth_enabled);
                    localStorage.setItem('face_auth_enabled', settings.face_auth_enabled);
                }
                if (typeof settings.system_alerts_enabled !== 'undefined') {
                    setSystemAlertsEnabled(settings.system_alerts_enabled);
                }
                if (typeof settings.quiet_mode !== 'undefined') {
                    setQuietMode(settings.quiet_mode);
                }
                if (settings.interrupt_preferences) {
                    setInterruptPreferences(prev => ({ ...prev, ...settings.interrupt_preferences }));
                }
                if (settings.current_mode) {
                    setCurrentMode(settings.current_mode);
                }
                if (settings.provider_routing) {
                    setProviderRouting(prev => ({ ...prev, ...settings.provider_routing }));
                }
            }
        };

        socket.on('settings', handleSettings);
        const handleGoogleStatus = (account) => setGoogleAccount(account || { connected: false });
        socket.on('google_account_status', handleGoogleStatus);
        // Also listen for legacy tool_permissions if needed, but 'settings' covers it
        // socket.on('tool_permissions', handlePermissions); 

        return () => {
            socket.off('settings', handleSettings);
            socket.off('google_account_status', handleGoogleStatus);
        };
    }, [socket]);

    const togglePermission = (toolId) => {
        socket.emit('update_settings', { tool_permissions: { [toolId]: false } });
    };

    const toggleFaceAuth = () => {
        const newVal = !faceAuthEnabled;
        setFaceAuthEnabled(newVal); // Optimistic Update
        localStorage.setItem('face_auth_enabled', newVal);
        socket.emit('update_settings', { face_auth_enabled: newVal });
    };

    const toggleCameraFlip = () => {
        const newVal = !isCameraFlipped;
        setIsCameraFlipped(newVal);
        socket.emit('update_settings', { camera_flipped: newVal });
    };

    const toggleSystemAlerts = () => {
        const newVal = !systemAlertsEnabled;
        setSystemAlertsEnabled(newVal);
        socket.emit('update_settings', { system_alerts_enabled: newVal });
    };

    const toggleQuietMode = () => {
        const newValue = !quietMode;
        setQuietMode(newValue);
        socket.emit('update_settings', { quiet_mode: newValue });
    };

    const updateInterruptPreference = (key, value) => {
        setInterruptPreferences(prev => ({ ...prev, [key]: value }));
        socket.emit('update_settings', { interrupt_preferences: { [key]: value } });
    };

    const selectMode = (mode) => {
        setCurrentMode(mode);
        socket.emit('update_settings', { current_mode: mode });
    };

    const connectGoogleAccount = () => socket.emit('connect_google_account');
    const disconnectGoogleAccount = () => socket.emit('disconnect_google_account');
    const updateProvider = (key, value) => {
        setProviderRouting(prev => ({ ...prev, [key]: value }));
        socket.emit('update_settings', { provider_routing: { [key]: value } });
    };

    return (
        <div className="fixed top-20 right-4 sm:right-10 bg-black/95 border border-cyan-500/50 p-4 rounded-lg z-[1100] w-[calc(100vw-2rem)] max-w-80 max-h-[calc(100vh-5rem)] overflow-hidden backdrop-blur-xl shadow-[0_0_30px_rgba(6,182,212,0.2)]">
            <div className="flex justify-between items-center mb-4 border-b border-cyan-900/50 pb-2">
                <h2 className="text-cyan-400 font-bold text-sm uppercase tracking-wider">Settings</h2>
                <button onClick={onClose} className="text-cyan-600 hover:text-cyan-400">
                    <X size={16} />
                </button>
            </div>

            <div className="max-h-[calc(100vh-9rem)] overflow-y-auto pr-1 custom-scrollbar">

            {/* Authentication Section */}
            <div className="mb-6">
                <h3 className="text-cyan-400 font-bold mb-3 text-xs uppercase tracking-wider opacity-80">Security</h3>
                <div className="flex items-center justify-between text-xs bg-gray-900/50 p-2 rounded border border-cyan-900/30">
                    <span className="text-cyan-100/80">Face Authentication</span>
                    <button
                        onClick={toggleFaceAuth}
                        aria-label={`Face authentication ${faceAuthEnabled ? 'on' : 'off'}`}
                        className={`hud-toggle ${faceAuthEnabled ? 'hud-toggle-on' : ''}`}
                    >
                        <span>{faceAuthEnabled ? 'ON' : 'OFF'}</span>
                        <i />
                    </button>
                </div>
            </div>

            <div className="mb-6">
                <h3 className="text-cyan-400 font-bold mb-3 text-xs uppercase tracking-wider opacity-80">System Alerts</h3>
                <div className="flex items-center justify-between text-xs bg-gray-900/50 p-2 rounded border border-cyan-900/30">
                    <span className="text-cyan-100/80">Proactive Alerts</span>
                    <button
                        onClick={toggleSystemAlerts}
                        aria-label={`System alerts ${systemAlertsEnabled ? 'on' : 'off'}`}
                        className={`hud-toggle ${systemAlertsEnabled ? 'hud-toggle-on' : ''}`}
                    >
                        <span>{systemAlertsEnabled ? 'ON' : 'OFF'}</span>
                        <i />
                    </button>
                </div>
            </div>

            <div className="mb-6">
                <h3 className="text-cyan-400 font-bold mb-3 text-xs uppercase tracking-wider opacity-80">Google Account</h3>
                <div className="space-y-2 bg-gray-900/50 p-3 rounded border border-cyan-900/30">
                    <div className="flex items-center justify-between gap-3 text-xs">
                        <span className={googleAccount.connected ? 'text-green-300' : 'text-cyan-100/80'}>
                            {googleAccount.connected ? 'Connected: Gmail, Calendar, Contacts' : 'Not connected'}
                        </span>
                        {googleAccount.connected ? (
                            <button type="button" onClick={disconnectGoogleAccount} className="flex items-center gap-1 text-red-300 hover:text-red-200">
                                <Unlink size={14} /> Disconnect
                            </button>
                        ) : (
                            <button type="button" onClick={connectGoogleAccount} disabled={googleAccount.connecting} className="flex items-center gap-1 text-cyan-300 hover:text-cyan-100 disabled:opacity-50">
                                <Link size={14} /> {googleAccount.connecting ? 'Connecting...' : 'Connect'}
                            </button>
                        )}
                    </div>
                    <p className="text-[10px] leading-relaxed text-cyan-500/60">Friday requests read access only. Google opens a consent page in your browser; the token stays on this computer.</p>
                    {googleAccount.error && <p className="text-[10px] leading-relaxed text-red-300">{googleAccount.error}</p>}
                </div>
            </div>

            <div className="mb-6">
                <h3 className="text-cyan-400 font-bold mb-3 text-xs uppercase tracking-wider opacity-80">Provider Routing</h3>
                <div className="space-y-2 bg-gray-900/50 p-3 rounded border border-cyan-900/30">
                    {[['voice_vision', 'Voice + vision', ['Gemini Live']], ['text_reasoning', 'Text reasoning', ['Gemini', 'OpenClaw']], ['coding', 'Coding', ['Gemini', 'OpenClaw']], ['documents', 'Documents', ['Gemini', 'OpenClaw']], ['background_agents', 'Background agents', ['OpenClaw']]].map(([key, label, options]) => (
                        <label key={key} className="flex items-center justify-between gap-2 text-[10px] text-cyan-100/80">
                            <span>{label}</span>
                            <select value={providerRouting[key]} onChange={(event) => updateProvider(key, event.target.value)} className="bg-black border border-cyan-700/50 px-1 py-1 text-cyan-200">
                                {options.map(option => <option key={option}>{option}</option>)}
                            </select>
                        </label>
                    ))}
                </div>
            </div>

            <div className="mb-6">
                <h3 className="text-cyan-400 font-bold mb-3 text-xs uppercase tracking-wider opacity-80">Assistant Behavior</h3>
                <div className="space-y-2">
                    <div className="flex items-center justify-between text-xs bg-gray-900/50 p-2 rounded border border-cyan-900/30">
                        <span className="flex items-center gap-2 text-cyan-100/80">
                            {quietMode ? <VolumeX size={14} /> : <Volume2 size={14} />}
                            Quiet Mode
                        </span>
                        <button
                            onClick={toggleQuietMode}
                            aria-label={`Quiet mode ${quietMode ? 'on' : 'off'}`}
                            className={`hud-toggle ${quietMode ? 'hud-toggle-on' : ''}`}
                        >
                            <span>{quietMode ? 'ON' : 'OFF'}</span>
                            <i />
                        </button>
                    </div>
                    <label className="flex items-center gap-2 text-xs bg-gray-900/50 p-2 rounded border border-cyan-900/30 text-cyan-100/80">
                        <input type="checkbox" checked={interruptPreferences.urgent_only} onChange={(event) => updateInterruptPreference('urgent_only', event.target.checked)} />
                        Urgent alerts only
                    </label>
                    <label className="flex items-center gap-2 text-xs bg-gray-900/50 p-2 rounded border border-cyan-900/30 text-cyan-100/80">
                        <input type="checkbox" checked={interruptPreferences.emergencies_only} onChange={(event) => updateInterruptPreference('emergencies_only', event.target.checked)} />
                        Emergencies only
                    </label>
                    <div className="grid grid-cols-3 gap-1">
                        {[
                            { id: 'active', label: 'Active', icon: Activity },
                            { id: 'focus', label: 'Focus', icon: Coffee },
                            { id: 'away', label: 'Away', icon: Home }
                        ].map(({ id, label, icon: Icon }) => (
                            <button
                                key={id}
                                type="button"
                                aria-pressed={currentMode === id}
                                onClick={() => selectMode(id)}
                                className={`flex items-center justify-center gap-1 rounded border px-1 py-2 text-[10px] transition-colors ${currentMode === id ? 'border-cyan-400 bg-cyan-500/20 text-cyan-100' : 'border-cyan-900/50 bg-gray-900/50 text-cyan-500/70 hover:border-cyan-600'}`}
                            >
                                <Icon size={12} />
                                {label}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            {/* Microphone Section */}
            <div className="mb-4">
                <h3 className="text-cyan-400 font-bold mb-2 text-xs uppercase tracking-wider opacity-80">Microphone</h3>
                <select
                    value={selectedMicId}
                    onChange={(e) => setSelectedMicId(e.target.value)}
                    className="w-full bg-gray-900 border border-cyan-800 rounded p-2 text-xs text-cyan-100 focus:border-cyan-400 outline-none"
                >
                    {micDevices.map((device, i) => (
                        <option key={device.deviceId} value={device.deviceId}>
                            {device.label || `Microphone ${i + 1}`}
                        </option>
                    ))}
                </select>
            </div>

            {/* Speaker Section */}
            <div className="mb-4">
                <h3 className="text-cyan-400 font-bold mb-2 text-xs uppercase tracking-wider opacity-80">Speaker</h3>
                <select
                    value={selectedSpeakerId}
                    onChange={(e) => setSelectedSpeakerId(e.target.value)}
                    className="w-full bg-gray-900 border border-cyan-800 rounded p-2 text-xs text-cyan-100 focus:border-cyan-400 outline-none"
                >
                    {speakerDevices.map((device, i) => (
                        <option key={device.deviceId} value={device.deviceId}>
                            {device.label || `Speaker ${i + 1}`}
                        </option>
                    ))}
                </select>
            </div>

            {/* Webcam Section */}
            <div className="mb-6">
                <h3 className="text-cyan-400 font-bold mb-2 text-xs uppercase tracking-wider opacity-80">Webcam</h3>
                <select
                    value={selectedWebcamId}
                    onChange={(e) => setSelectedWebcamId(e.target.value)}
                    className="w-full bg-gray-900 border border-cyan-800 rounded p-2 text-xs text-cyan-100 focus:border-cyan-400 outline-none"
                >
                    {webcamDevices.map((device, i) => (
                        <option key={device.deviceId} value={device.deviceId}>
                            {device.label || `Camera ${i + 1}`}
                        </option>
                    ))}
                </select>
            </div>

            {/* Cursor Section */}
            <div className="mb-6">
                <div className="flex justify-between mb-2">
                    <h3 className="text-cyan-400 font-bold text-xs uppercase tracking-wider opacity-80">Cursor Sensitivity</h3>
                    <span className="text-xs text-cyan-500">{cursorSensitivity}x</span>
                </div>
                <input
                    type="range"
                    min="1.0"
                    max="5.0"
                    step="0.1"
                    value={cursorSensitivity}
                    onChange={(e) => setCursorSensitivity(parseFloat(e.target.value))}
                    className="w-full accent-cyan-400 cursor-pointer h-1 bg-gray-800 rounded-lg appearance-none"
                />
            </div>

            {/* Gesture Control Section */}
            <div className="mb-6">
                <h3 className="text-cyan-400 font-bold mb-3 text-xs uppercase tracking-wider opacity-80">Gesture Control</h3>
                <div className="flex items-center justify-between text-xs bg-gray-900/50 p-2 rounded border border-cyan-900/30">
                    <span className="text-cyan-100/80">Flip Camera Horizontal</span>
                    <button
                        onClick={toggleCameraFlip}
                        aria-label={`Camera flip ${isCameraFlipped ? 'on' : 'off'}`}
                        className={`hud-toggle ${isCameraFlipped ? 'hud-toggle-on' : ''}`}
                    >
                        <span>{isCameraFlipped ? 'ON' : 'OFF'}</span>
                        <i />
                    </button>
                </div>
            </div>

            {/* Tool Permissions Section */}
            <div className="mb-6">
                <h3 className="text-cyan-400 font-bold mb-3 text-xs uppercase tracking-wider opacity-80">Tool Confirmations</h3>
                <div className="space-y-2 max-h-40 overflow-y-auto pr-2 custom-scrollbar">
                    {TOOLS.map(tool => {
                        return (
                            <div key={tool.id} className="flex items-center justify-between text-xs bg-gray-900/50 p-2 rounded border border-cyan-900/30">
                                <span className="text-cyan-100/80">{tool.label}</span>
                                <button
                                    onClick={() => togglePermission(tool.id)}
                                    aria-label={`${tool.label} runs automatically`}
                                    className="hud-toggle hud-toggle-on"
                                >
                                    <span>AUTO</span>
                                    <i />
                                </button>
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* Memory Section */}
            <div>
                <h3 className="text-cyan-400 font-bold mb-2 text-xs uppercase tracking-wider opacity-80">Memory Data</h3>
                <div className="flex flex-col gap-2">
                    <label className="text-[10px] text-cyan-500/60 uppercase">Upload Memory Text</label>
                    <input
                        type="file"
                        accept=".txt"
                        onChange={handleFileUpload}
                        className="text-xs text-cyan-100 bg-gray-900 border border-cyan-800 rounded p-2 file:mr-2 file:py-1 file:px-2 file:rounded-full file:border-0 file:text-[10px] file:font-semibold file:bg-cyan-900 file:text-cyan-400 hover:file:bg-cyan-800 cursor-pointer"
                    />
                </div>
            </div>
            </div>
        </div>
    );
};

export default SettingsWindow;
