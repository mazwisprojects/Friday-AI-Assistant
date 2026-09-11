import { useState } from 'react';

export const useSystemState = () => {
  const [status, setStatus] = useState('Disconnected');
  const [isConnected, setIsConnected] = useState(true);
  const [isMuted, setIsMuted] = useState(true);
  const [isVideoOn, setIsVideoOn] = useState(false);
  const [socketConnected, setSocketConnected] = useState(false);
  const [currentProject, setCurrentProject] = useState('default');
  const [systemStats, setSystemStats] = useState({
    cpu_percent: 0,
    ram_percent: 0,
    cpu_temp_c: null,
    gpu_percent: null,
    uptime: '0h 0m'
  });
  const [providerRouting, setProviderRouting] = useState({ 
    text_reasoning: 'Gemini', 
    coding: 'OpenClaw', 
    documents: 'OpenClaw' 
  });

  return {
    status,
    setStatus,
    isConnected,
    setIsConnected,
    isMuted,
    setIsMuted,
    isVideoOn,
    setIsVideoOn,
    socketConnected,
    setSocketConnected,
    currentProject,
    setCurrentProject,
    systemStats,
    setSystemStats,
    providerRouting,
    setProviderRouting
  };
};