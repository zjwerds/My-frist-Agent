// Universal entry point — auto-detects Electron API availability.
//   Electron mode: full desktop (BrowserWindow, tray, etc.)
//   Browser mode: starts backend, opens browser, manages lifecycle.

const path = require('path')
const { spawn } = require('child_process')
const http = require('http')

const PORT = 8000
const isDev = process.env.NODE_ENV === 'development'
let pythonProcess = null

// ── Detect Electron API ────────────────────────────────────────────────────────

let electron
try { electron = require('electron') } catch (_) { electron = null }

const hasElectron =
  electron &&
  typeof electron === 'object' &&
  typeof electron.app === 'object' &&
  typeof electron.app.whenReady === 'function'

// ── Shared: Python backend management ──────────────────────────────────────────

function getPythonPath() {
  if (isDev || !electron || !electron.app) {
    return process.platform === 'win32' ? 'python' : 'python3'
  }
  const ext = process.platform === 'win32' ? '.exe' : ''
  // Preferred: resourcesPath from Electron API
  if (electron.app.resourcesPath) {
    return path.join(electron.app.resourcesPath, 'backend', `deepseek-agent-backend${ext}`)
  }
  // Fallback: resourcesPath unavailable (partial Electron init)
  // In the packaged app, main.cjs is at <resources>/app.asar/electron/main.cjs
  if (electron.app.isPackaged) {
    return path.resolve(__dirname, '..', '..', 'backend', `deepseek-agent-backend${ext}`)
  }
  return process.platform === 'win32' ? 'python' : 'python3'
}

function getBackendDir() {
  if (isDev || !electron || !electron.app) {
    return path.join(__dirname, '..', '..', 'backend')
  }
  if (electron.app.resourcesPath) {
    return electron.app.resourcesPath
  }
  if (electron.app.isPackaged) {
    return path.resolve(__dirname, '..', '..')
  }
  return path.join(__dirname, '..', '..', 'backend')
}

function startPython() {
  return new Promise((resolve, reject) => {
    const pythonPath = getPythonPath()
    const backendDir = getBackendDir()
    const isBundled = !isDev && !!electron?.app?.isPackaged

    console.log(`[main] Starting Python backend: ${pythonPath}`)
    console.log(`[main] Backend dir: ${backendDir}`)

    if (isBundled) {
      pythonProcess = spawn(pythonPath, [], {
        cwd: backendDir,
        env: { ...process.env },
        stdio: ['pipe', 'pipe', 'pipe'],
      })
    } else {
      pythonProcess = spawn(pythonPath, [
        '-m', 'uvicorn', 'app.main:app',
        '--host', '127.0.0.1', '--port', String(PORT),
      ], {
        cwd: backendDir,
        env: { ...process.env },
        stdio: ['pipe', 'pipe', 'pipe'],
      })
    }

    pythonProcess.stdout.on('data', (data) => {
      const text = data.toString()
      console.log(`[Python] ${text}`)
      if (
        text.includes('Uvicorn running') ||
        text.includes('Application startup complete') ||
        text.includes('Listening at')
      ) resolve()
    })

    pythonProcess.stderr.on('data', (data) => {
      const text = data.toString()
      console.log(`[Python stderr] ${text}`)
      if (
        text.includes('Uvicorn running') ||
        text.includes('Application startup complete') ||
        text.includes('Listening at')
      ) resolve()
    })

    pythonProcess.on('error', (err) => {
      console.error('[main] Failed to start Python:', err)
      reject(err)
    })

    pythonProcess.on('exit', (code) => {
      console.log(`[main] Python process exited with code ${code}`)
      pythonProcess = null
    })

    // Safety timeout: resolve anyway after 8 s
    setTimeout(() => resolve(), 8000)
  })
}

function waitForBackend(retries = 20) {
  return new Promise((resolve, reject) => {
    const attempt = () => {
      http.get(`http://127.0.0.1:${PORT}/api/health`, (res) => {
        if (res.statusCode === 200) {
          console.log('[main] Backend is ready!')
          resolve()
        } else if (retries > 0) {
          setTimeout(() => waitForBackend(retries - 1).then(resolve, reject), 500)
        } else {
          reject(new Error('Backend did not become ready'))
        }
      }).on('error', () => {
        if (retries > 0) {
          setTimeout(() => waitForBackend(retries - 1).then(resolve, reject), 500)
        } else {
          reject(new Error('Backend did not become ready'))
        }
      })
    }
    attempt()
  })
}

function cleanupPython() {
  if (pythonProcess) {
    console.log('[main] Stopping Python backend...')
    if (process.platform === 'win32') {
      spawn('taskkill', ['/pid', String(pythonProcess.pid), '/f', '/t'])
    } else {
      pythonProcess.kill('SIGTERM')
    }
    pythonProcess = null
  }
}

// ── Browser Mode ───────────────────────────────────────────────────────────────

function runBrowser() {
  console.log('[main] ▸ Running in browser mode (Electron API unavailable)')
  console.log('[main]   The backend will start and the app will open in your browser.')

  startPython()
    .then(() => waitForBackend())
    .then(() => {
      const url = 'http://localhost:5173'
      console.log(`[main] Opening ${url} ...`)
      const { exec } = require('child_process')
      exec(`start "" "${url}"`)
      console.log('[main] ✓ App started. Press Ctrl+C to stop.')
    })
    .catch((err) => {
      console.error('[main] Failed to start:', err)
      cleanupPython()
      process.exit(1)
    })

  process.on('SIGINT', () => { cleanupPython(); process.exit(0) })
  process.on('SIGTERM', () => { cleanupPython(); process.exit(0) })
}

// ── Electron Mode ──────────────────────────────────────────────────────────────

function runElectron(electron) {
  console.log('[main] ▸ Running in Electron mode')

  const { app, BrowserWindow, dialog, ipcMain } = electron

  let mainWindow = null
  let floatingWindow = null

  function createWindow() {
    mainWindow = new BrowserWindow({
      width: 1280,
      height: 800,
      minWidth: 900,
      minHeight: 600,
      title: '煎蛋Agent',
      frame: false,
      icon: path.join(__dirname, '..', 'public', 'favicon.svg'),
      webPreferences: {
        preload: path.join(__dirname, 'preload.cjs'),
        contextIsolation: true,
        nodeIntegration: false,
      },
      backgroundColor: '#1a1a2e',
      show: false,
    })

    // Intercept window.open for the floating stats widget
    // This works regardless of whether contextBridge/IPC is functional,
    // and gives us full control over the popup BrowserWindow options.
    mainWindow.webContents.setWindowOpenHandler(({ url }) => {
      if (url.includes('/api/stats/widget')) {
        return {
          action: 'allow',
          overrideBrowserWindowOptions: {
            width: 320,
            height: 420,
            alwaysOnTop: true,
            frame: false,
            resizable: false,
            skipTaskbar: true,
            transparent: true,
            backgroundColor: '#00000000',
            title: '煎蛋状态',
          },
        }
      }
      return { action: 'allow' }
    })

    if (isDev || !app.isPackaged) {
      mainWindow.loadURL('http://localhost:5173')
      mainWindow.webContents.openDevTools()
    } else {
      mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'))
    }

    mainWindow.once('ready-to-show', () => mainWindow.show())

    mainWindow.on('maximize', () => mainWindow.webContents.send('window-maximize-changed', true))
    mainWindow.on('unmaximize', () => mainWindow.webContents.send('window-maximize-changed', false))

    mainWindow.on('close', () => closeFloatingWindow())
    mainWindow.on('closed', () => { mainWindow = null })
  }

  // ── Floating Widget ────────────────────────────────────────────────────────

  function createFloatingWindow() {
    if (floatingWindow && !floatingWindow.isDestroyed()) {
      floatingWindow.focus()
      return
    }

    floatingWindow = new BrowserWindow({
      width: 320,
      height: 420,
      alwaysOnTop: true,
      frame: false,
      resizable: false,
      skipTaskbar: true,
      transparent: true,
      backgroundColor: '#00000000',
      title: '煎蛋状态',
      webPreferences: {
        contextIsolation: true,
        nodeIntegration: false,
      },
    })

    floatingWindow.loadURL(`http://127.0.0.1:${PORT}/api/stats/widget`)

    floatingWindow.on('closed', () => {
      floatingWindow = null
      try {
        if (mainWindow && !mainWindow.isDestroyed() && !mainWindow.webContents.isDestroyed()) {
          mainWindow.webContents.send('floating-widget-closed')
        }
      } catch (_) {}
    })
  }

  function closeFloatingWindow() {
    if (floatingWindow && !floatingWindow.isDestroyed()) {
      floatingWindow.close()
    }
    floatingWindow = null
  }

  ipcMain.on('open-floating-widget', () => createFloatingWindow())
  ipcMain.on('close-floating-widget', () => closeFloatingWindow())

  // ── Frameless window controls ───────────────────────────────────────

  ipcMain.on('window-minimize', () => mainWindow?.minimize())
  ipcMain.on('window-maximize', () => {
    if (mainWindow?.isMaximized()) mainWindow.unmaximize()
    else mainWindow?.maximize()
  })
  ipcMain.on('window-close', () => mainWindow?.close())
  ipcMain.handle('window-is-maximized', () => mainWindow?.isMaximized())

  // ── File dialog ───────────────────────────────────────────────────────

  ipcMain.handle('open-directory', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
      properties: ['openDirectory'],
    })
    return result.canceled ? null : result.filePaths[0]
  })

  // ── App lifecycle ──────────────────────────────────────────────────────────

  app.whenReady().then(async () => {
    try {
      await startPython()
      await waitForBackend()
      createWindow()
    } catch (err) {
      console.error('[main] Failed to start:', err)
      dialog.showErrorBox('启动失败', `无法启动后端服务:\n${err.message}`)
      app.quit()
    }

    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0) createWindow()
    })
  })

  app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit()
  })

  app.on('before-quit', cleanupPython)

  // Single instance lock
  if (!app.requestSingleInstanceLock()) {
    app.quit()
  } else {
    app.on('second-instance', () => {
      if (mainWindow) {
        if (mainWindow.isMinimized()) mainWindow.restore()
        mainWindow.focus()
      }
    })
  }
}

// ── Entry point ────────────────────────────────────────────────────────────────

if (hasElectron) {
  runElectron(electron)
} else {
  runBrowser()
}
