import React from 'react';
import { Mic, MicOff, Settings, Power, Video, VideoOff, Hand, Lightbulb, Printer, Globe, Box, Layout } from 'lucide-react';

const ToolsModule = ({
    isConnected,
    isMuted,
    isVideoOn,
    isHandTrackingEnabled,
    showSettings,
    onTogglePower,
    onToggleMute,
    onToggleVideo,
    onToggleSettings,

    onToggleHand,
    onToggleKasa,
    showKasaWindow,
    onTogglePrinter,
    showPrinterWindow,
    onToggleCad,
    showCadWindow,
    onToggleBrowser,
    showBrowserWindow,
    onToggleActions,
    showActionMenu,
    activeDragElement,

    position,
    width,
    onMouseDown
}) => {
    return (
        <div
            id="tools"
            onMouseDown={onMouseDown}
            className={`hud-panel absolute px-6 py-3 transition-all duration-200 
                        backdrop-blur-xl bg-black/75 border border-cyan-500/40 shadow-2xl rounded-none`}
            style={{
                left: position.x,
                top: position.y,
                transform: 'translate(-50%, -50%)',
                width,
                pointerEvents: 'auto'
            }}
        >
            <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-5 pointer-events-none mix-blend-overlay rounded-full"></div>

            <div className="flex justify-center gap-6 relative z-10">
                {/* Power Button */}
                <button
                    onClick={onTogglePower}
                    className={`p-3 rounded-full border-2 transition-all duration-300 ${isConnected
                        ? 'border-green-500 bg-green-500/10 text-green-500 hover:bg-green-500/20 shadow-[0_0_15px_rgba(34,197,94,0.3)]'
                        : 'border-gray-600 bg-gray-600/10 text-gray-500 hover:bg-gray-600/20'
                        } `}
                >
                    <Power size={24} />
                </button>

                <button
                    onClick={onToggleActions}
                    className={`p-3 rounded-full border-2 transition-all duration-300 ${showActionMenu
                        ? 'border-cyan-400 bg-cyan-400/10 text-cyan-400'
                        : 'border-cyan-900 text-cyan-700 hover:border-cyan-500 hover:text-cyan-500'
                        } `}
                    title="Open action windows"
                >
                    <Layout size={24} />
                </button>
            </div>
        </div>
    );
};

export default ToolsModule;
