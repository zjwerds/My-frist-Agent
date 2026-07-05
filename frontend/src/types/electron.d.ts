interface ElectronAPI {
  getAppVersion: () => Promise<string>
  isElectron: boolean
  openFloatingWidget: () => void
  closeFloatingWidget: () => void
  onFloatingWidgetClosed: (callback: () => void) => () => void
  // Window controls
  minimize: () => void
  maximize: () => void
  close: () => void
  isMaximized: () => Promise<boolean>
  onMaximizeChange: (callback: (maximized: boolean) => void) => () => void
  // File dialog
  openDirectory: () => Promise<string | null>
}

interface Window {
  electronAPI?: ElectronAPI
}
