import { useState } from 'react';

export const useUIState = () => {
  const [showSettings, setShowSettings] = useState(false);
  const [showKasaWindow, setShowKasaWindow] = useState(false);
  const [showPrinterWindow, setShowPrinterWindow] = useState(false);
  const [showCadWindow, setShowCadWindow] = useState(false);
  const [showBrowserWindow, setShowBrowserWindow] = useState(false);
  const [showActionMenu, setShowActionMenu] = useState(false);
  const [actionWindows, setActionWindows] = useState({
    code: false,
    control: false,
    desktop: false,
    files: false,
    flights: false,
    games: false,
    messages: false,
    memory: false,
    openclaw: false,
    processes: false,
    proactive: false,
    reminders: false,
    routines: false,
    search: false,
    system: false,
    weather: false,
    youtube: false,
    contacts: false
  });

  const toggleActionWindow = (id) => {
    setActionWindows(prev => ({ ...prev, [id]: !prev[id] }));
  };

  return {
    showSettings,
    setShowSettings,
    showKasaWindow,
    setShowKasaWindow,
    showPrinterWindow,
    setShowPrinterWindow,
    showCadWindow,
    setShowCadWindow,
    showBrowserWindow,
    setShowBrowserWindow,
    showActionMenu,
    setShowActionMenu,
    actionWindows,
    setActionWindows,
    toggleActionWindow
  };
};