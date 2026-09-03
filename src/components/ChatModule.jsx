import React, { useEffect, useRef } from 'react';

const ChatModule = ({
    messages,
    inputValue,
    setInputValue,
    handleSend,
    isModularMode,
    activeDragElement,
    position,
    width = 672,
    height,
    weatherCard,
    googleServiceCard,
    actionPlan,
    onMouseDown
}) => {
    const messagesEndRef = useRef(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    return (
        <div
            id="chat"
            onMouseDown={onMouseDown}
            className={`hud-panel absolute px-6 py-4 pointer-events-auto transition-all duration-200 
            backdrop-blur-xl bg-black/70 border border-cyan-500/40 shadow-2xl rounded-none
            ${isModularMode ? (activeDragElement === 'chat' ? 'ring-2 ring-green-500' : 'ring-1 ring-yellow-500/30') : ''}
        `}
            style={{
                left: position.x,
                top: position.y,
                transform: 'translate(-50%, 0)', // Aligned top-center
                width: width,
                height: height
            }}
        >
            <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-5 pointer-events-none mix-blend-overlay"></div>

            {weatherCard && (
                <div className="weather-card-tab">
                    <div className="weather-card-heading">
                        <span className="weather-card-label">LIVE WEATHER</span>
                        <span className="weather-card-location">{weatherCard.city}{weatherCard.country ? ` / ${weatherCard.country}` : ''}</span>
                    </div>
                    <div className="weather-card-main">
                        <div>
                            <div className="weather-card-condition">{weatherCard.condition}</div>
                            <div className="weather-card-metrics">
                                <span>FEELS {weatherCard.apparent_temperature ?? '--'}°C</span>
                                <span>HUM {weatherCard.humidity ?? '--'}%</span>
                                <span>WIND {weatherCard.wind ?? '--'} km/h</span>
                            </div>
                        </div>
                        <div className="weather-card-temperature">{weatherCard.temperature ?? '--'}°</div>
                    </div>
                    <div className="weather-card-footer">
                        <span>TODAY HIGH {weatherCard.high ?? '--'}°</span>
                        <span>LOW {weatherCard.low ?? '--'}°</span>
                        <span>RAIN {weatherCard.rain_chance ?? '--'}%</span>
                    </div>
                </div>
            )}

            {googleServiceCard && (
                <div className="google-service-tab">
                    <div className="google-service-heading">
                        <span>{googleServiceCard.title}</span>
                        <span>{googleServiceCard.message}</span>
                    </div>
                    <div className="google-service-items">
                        {(googleServiceCard.items || []).slice(0, 4).map((item, index) => (
                            <div key={item.id || item.resource_name || index} className="google-service-item">
                                {googleServiceCard.service === 'gmail' && <><strong>{item.subject || 'No subject'}</strong><span>{item.from || item.snippet || ''}</span></>}
                                {googleServiceCard.service === 'calendar' && <><strong>{item.summary || 'Untitled event'}</strong><span>{item.start?.dateTime || item.start?.date || item.description || ''}</span></>}
                                {googleServiceCard.service === 'contacts' && <><strong>{item.name || 'Unnamed contact'}</strong><span>{item.emails?.[0] || item.phones?.[0] || item.organization || 'No contact details'}</span></>}
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {actionPlan && (
                <div className="action-status-tab">
                    <div className="action-status-heading">
                        <span>FRIDAY ACTION</span>
                        <strong>{actionPlan.title}</strong>
                    </div>
                    <div className="action-status-steps">
                        {(actionPlan.steps || []).map((step, index) => (
                            <div key={`${step.label}-${index}`} className={`action-status-step action-status-${step.status}`}>
                                <span>{String(index + 1).padStart(2, '0')}</span>
                                <span>{step.label}</span>
                                <b>{step.status === 'active' ? 'RUN' : step.status === 'done' ? 'OK' : step.status === 'error' ? 'ERR' : step.status === 'cancelled' ? 'STOP' : '--'}</b>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            <div
                className="flex flex-col gap-3 overflow-y-auto mb-4 scrollbar-hide mask-image-gradient relative z-10"
                style={{ height: height ? `calc(${height}px - 70px)` : '15rem' }}
            >
                {messages.map((msg, i) => (
                    <div key={i} className="text-sm border-l-2 border-cyan-800/50 pl-3 py-1">
                        <span className="text-cyan-600 font-mono text-xs opacity-70">[{msg.time}]</span> <span className="font-bold text-cyan-300 drop-shadow-sm">{msg.sender}</span>
                        <div className="text-gray-300 mt-1 leading-relaxed">{msg.text}</div>
                    </div>
                ))}
                <div ref={messagesEndRef} />
            </div>

            <div className="flex gap-2 relative z-10 absolute bottom-4 left-6 right-6">
                <input
                    type="text"
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    onKeyDown={handleSend}
                    placeholder="INITIALIZE COMMAND..."
                    className="flex-1 bg-black/40 border border-cyan-700/30 rounded-lg p-3 text-cyan-50 focus:outline-none focus:border-cyan-400 focus:ring-1 focus:ring-cyan-400/50 transition-all placeholder-cyan-800/50 backdrop-blur-sm"
                />
            </div>
            {isModularMode && <div className={`absolute -top-6 left-0 text-xs font-bold tracking-widest ${activeDragElement === 'chat' ? 'text-green-500' : 'text-yellow-500/50'}`}>CHAT MODULE</div>}
        </div>
    );
};

export default ChatModule;
