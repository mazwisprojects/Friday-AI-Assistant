const { contextBridge, ipcRenderer } = require('electron');

// Expose only specific IPC methods to the renderer process
contextBridge.exposeInMainWorld('electronAPI', {
    minimize: () => ipcRenderer.send('window-minimize'),
    maximize: () => ipcRenderer.send('window-maximize'),
    close: () => ipcRenderer.send('window-close'),
});
