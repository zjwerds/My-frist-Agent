const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
  getAppVersion: () => ipcRenderer.invoke('get-app-version'),
  isElectron: true,
  openFloatingWidget: () => ipcRenderer.send('open-floating-widget'),
  closeFloatingWidget: () => ipcRenderer.send('close-floating-widget'),
  onFloatingWidgetClosed: (callback) => {
    const handler = () => callback()
    ipcRenderer.on('floating-widget-closed', handler)
    return () => ipcRenderer.removeListener('floating-widget-closed', handler)
  },
  // Frameless window controls
  minimize: () => ipcRenderer.send('window-minimize'),
  maximize: () => ipcRenderer.send('window-maximize'),
  close: () => ipcRenderer.send('window-close'),
  isMaximized: () => ipcRenderer.invoke('window-is-maximized'),
  onMaximizeChange: (callback) => {
    const handler = (_event, isMaximized) => callback(isMaximized)
    ipcRenderer.on('window-maximize-changed', handler)
    return () => ipcRenderer.removeListener('window-maximize-changed', handler)
  },
  // File dialog
  openDirectory: () => ipcRenderer.invoke('open-directory'),
})
