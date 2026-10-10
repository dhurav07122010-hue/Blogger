const { contextBridge, ipcRenderer } = require('electron');

// Expose safe, controlled desktop APIs to renderer
contextBridge.exposeInMainWorld('electronAPI', {
  platform: process.platform,
  isDesktop: true,
  getVersion: () => ipcRenderer.invoke('get-app-version'),
  minimizeWindow: () => ipcRenderer.send('window-minimize'),
  maximizeWindow: () => ipcRenderer.send('window-maximize'),
  closeWindow: () => ipcRenderer.send('window-close'),
  checkBackendHealth: () => ipcRenderer.invoke('check-backend-health'),
});
