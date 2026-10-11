const { app, BrowserWindow, ipcMain, shell, dialog } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');
const http = require('http');

let mainWindow = null;
let pythonProcess = null;
const BACKEND_PORT = 8000;
const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`;

// Check if Python backend server is responding
function checkBackendAlive(callback) {
  const req = http.get(`${BACKEND_URL}/api/health`, (res) => {
    callback(res.statusCode === 200);
  });
  req.on('error', () => {
    callback(false);
  });
  req.setTimeout(1500, () => {
    req.destroy();
    callback(false);
  });
}

let backendReady = false;
let lastBackendError = '';

// Locate backend executable or Python interpreter
function resolveBackendExecution() {
  const isWindows = process.platform === 'win32';
  const exeName = isWindows ? 'backend_server.exe' : 'backend_server';

  // 1. Packaged production app: check for bundled binary in resources
  if (app.isPackaged) {
    const packagedCandidates = [
      path.join(process.resourcesPath, 'backend_server', exeName),
      path.join(process.resourcesPath, exeName),
    ];
    for (const candidate of packagedCandidates) {
      if (fs.existsSync(candidate)) {
        console.log(`[DESKTOP] Found packaged backend binary: ${candidate}`);
        return {
          type: 'executable',
          path: candidate,
          args: [],
          cwd: path.dirname(candidate),
        };
      }
    }
  }

  // 2. Development mode: prefer local virtual environment Python
  const venvPythonRel = isWindows
    ? path.join('venv', 'Scripts', 'python.exe')
    : path.join('venv', 'bin', 'python');

  const pythonCandidates = [
    path.join(app.getAppPath(), venvPythonRel),
    path.join(__dirname, venvPythonRel),
    path.join(process.resourcesPath, venvPythonRel),
  ];

  for (const candidate of pythonCandidates) {
    if (fs.existsSync(candidate)) {
      console.log(`[DESKTOP] Found virtual environment Python: ${candidate}`);
      return {
        type: 'python',
        path: candidate,
        args: ['-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', String(BACKEND_PORT)],
        cwd: app.getAppPath(),
      };
    }
  }

  // 3. Fallback to compiled backend binary in dev if venv is missing
  const binaryCandidates = [
    path.join(app.getAppPath(), 'backend_dist', 'backend_server', exeName),
    path.join(__dirname, 'backend_dist', 'backend_server', exeName),
    path.join(__dirname, 'dist', 'backend_server', exeName),
  ];

  for (const candidate of binaryCandidates) {
    if (fs.existsSync(candidate)) {
      console.log(`[DESKTOP] Found compiled backend binary: ${candidate}`);
      return {
        type: 'executable',
        path: candidate,
        args: [],
        cwd: path.dirname(candidate),
      };
    }
  }

  // 4. Fallback to system Python in PATH
  const sysPython = isWindows ? 'python.exe' : 'python3';
  return {
    type: 'python',
    path: sysPython,
    args: ['-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', String(BACKEND_PORT)],
    cwd: app.isPackaged ? process.resourcesPath : app.getAppPath(),
  };
}

// Start local FastAPI server in background
function startPythonBackend() {
  const backendConfig = resolveBackendExecution();
  console.log(`[DESKTOP] Spawning backend using ${backendConfig.type}: ${backendConfig.path}`);

  // Setup user data paths
  let dataDir = null;
  let envFile = null;

  try {
    const userData = app.getPath('userData');
    dataDir = path.join(userData, 'data');
    envFile = path.join(userData, '.env');

    if (!fs.existsSync(dataDir)) {
      fs.mkdirSync(dataDir, { recursive: true });
    }

    if (!fs.existsSync(envFile)) {
      const defaultEnv = path.join(__dirname, '.env');
      const exampleEnv = path.join(__dirname, '.env.example');
      if (fs.existsSync(defaultEnv)) {
        fs.copyFileSync(defaultEnv, envFile);
      } else if (fs.existsSync(exampleEnv)) {
        fs.copyFileSync(exampleEnv, envFile);
      }
    }

    // Auto-sync existing Blogger token if present in project or userData
    const localTokenFile = path.join(__dirname, 'data', 'blogger_token.json');
    const userDataTokenFile = path.join(dataDir, 'blogger_token.json');
    if (!fs.existsSync(userDataTokenFile) && fs.existsSync(localTokenFile)) {
      fs.copyFileSync(localTokenFile, userDataTokenFile);
    } else if (fs.existsSync(userDataTokenFile) && !fs.existsSync(localTokenFile)) {
      try { fs.copyFileSync(userDataTokenFile, localTokenFile); } catch (_) {}
    }
  } catch (err) {
    console.warn('[DESKTOP] Note on user data directory setup:', err.message);
  }

  const env = {
    ...process.env,
    PYTHONUNBUFFERED: '1',
    PORT: String(BACKEND_PORT),
    HOST: '127.0.0.1',
  };

  if (dataDir) env.BLOGGER_DATA_DIR = dataDir;
  if (envFile && fs.existsSync(envFile)) env.BLOGGER_ENV_FILE = envFile;

  try {
    pythonProcess = spawn(
      backendConfig.path,
      backendConfig.args,
      {
        cwd: backendConfig.cwd,
        env: env,
        stdio: 'pipe',
        windowsHide: true,
      }
    );

    pythonProcess.on('error', (err) => {
      console.error('[DESKTOP ERROR] Backend process spawn error:', err);
      dialog.showErrorBox(
        'Blogger AI Backend Notice',
        `Could not automatically launch the backend server:\n\n${err.message}\n\nPlease verify that Python and required dependencies are available.`
      );
    });

    pythonProcess.stdout.on('data', (data) => {
      console.log(`[BACKEND]: ${data}`);
    });

    pythonProcess.stderr.on('data', (data) => {
      const msg = data.toString();
      console.error(`[BACKEND ERR]: ${msg}`);
      if (msg.includes('Error') || msg.includes('Traceback') || msg.includes('ERROR')) {
        lastBackendError += msg;
      }
    });

    pythonProcess.on('close', (code) => {
      console.log(`[DESKTOP] Backend process exited with code ${code}`);
      if (code !== 0 && !backendReady) {
        dialog.showErrorBox(
          'Backend Initialization Error',
          `The backend service exited unexpectedly (code ${code}).\n\n${lastBackendError || 'Please check your configuration or logs.'}`
        );
      }
    });
  } catch (spawnError) {
    console.error('[DESKTOP ERROR] Failed to spawn backend process:', spawnError);
    dialog.showErrorBox(
      'Blogger AI Startup Error',
      `Failed to launch backend service:\n\n${spawnError.message}`
    );
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    title: 'Bloggers',
    width: 1380,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    icon: path.join(__dirname, 'frontend', 'icon.ico'),
    backgroundColor: '#0b1120',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
    autoHideMenuBar: true,
    show: false,
  });

  // Safe navigation handler
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http:') || url.startsWith('https:')) {
      shell.openExternal(url);
    }
    return { action: 'deny' };
  });

  // Prevent blank screen if connection fails
  mainWindow.webContents.on('did-fail-load', (event, errorCode, errorDescription, validatedURL) => {
    console.warn(`[DESKTOP] Failed to load URL: ${validatedURL} (${errorCode}: ${errorDescription})`);
    if (errorCode === -102 || errorCode === -105 || errorCode === -106 || errorCode === -118) {
      mainWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(`
        <!DOCTYPE html>
        <html>
        <head>
          <title>Bloggers - Connection Notice</title>
          <style>
            body { background: #0b1120; color: #f1f5f9; font-family: system-ui, -apple-system, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; text-align: center; }
            .card { background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 36px; max-width: 480px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
            h2 { margin-top: 0; color: #38bdf8; font-size: 20px; }
            p { color: #94a3b8; font-size: 14px; line-height: 1.6; margin: 16px 0; }
            .btn { background: #0284c7; color: white; border: none; padding: 10px 24px; border-radius: 8px; font-weight: 600; cursor: pointer; text-decoration: none; display: inline-block; }
            .btn:hover { background: #0369a1; }
          </style>
        </head>
        <body>
          <div class="card">
            <h2>Backend Connecting...</h2>
            <p>The Blogger AI Agent backend is starting up or temporarily unreachable.</p>
            <a class="btn" href="${BACKEND_URL}">Retry Connection</a>
          </div>
        </body>
        </html>
      `)}`);
      mainWindow.show();
    }
  });

  // Wait for backend to be ready, then load
  let attempts = 0;
  const maxAttempts = 60;
  const pollInterval = setInterval(() => {
    attempts++;
    checkBackendAlive((isAlive) => {
      if (isAlive) {
        backendReady = true;
        clearInterval(pollInterval);
        mainWindow.loadURL(BACKEND_URL);
        mainWindow.once('ready-to-show', () => {
          mainWindow.show();
        });
      } else if (attempts >= maxAttempts) {
        clearInterval(pollInterval);
        console.warn('[DESKTOP] Backend readiness check timed out. Attempting load...');
        mainWindow.loadURL(BACKEND_URL);
        mainWindow.show();
      }
    });
  }, 400);

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// IPC Handlers
ipcMain.handle('get-app-version', () => app.getVersion());
ipcMain.handle('check-backend-health', async () => {
  return new Promise((resolve) => checkBackendAlive(resolve));
});
ipcMain.handle('restart-backend', async () => {
  console.log('[DESKTOP] Explicit restart-backend invoked from frontend.');
  if (pythonProcess) {
    try {
      pythonProcess.kill();
    } catch (_) {}
    pythonProcess = null;
  }
  startPythonBackend();
  return new Promise((resolve) => {
    let attempts = 0;
    const interval = setInterval(() => {
      attempts++;
      checkBackendAlive((alive) => {
        if (alive) {
          clearInterval(interval);
          resolve({ success: true, message: 'Backend restarted successfully.' });
        } else if (attempts >= 40) {
          clearInterval(interval);
          resolve({ success: false, message: `Backend restart timed out: ${lastBackendError || 'check logs'}` });
        }
      });
    }, 400);
  });
});

ipcMain.on('window-minimize', () => {
  if (mainWindow) mainWindow.minimize();
});

ipcMain.on('window-maximize', () => {
  if (mainWindow) {
    if (mainWindow.isMaximized()) mainWindow.unmaximize();
    else mainWindow.maximize();
  }
});

ipcMain.on('window-close', () => {
  if (mainWindow) mainWindow.close();
});

// App Lifecycle
app.whenReady().then(() => {
  // If backend is not already running, spawn it
  checkBackendAlive((alreadyRunning) => {
    if (!alreadyRunning) {
      startPythonBackend();
    } else {
      console.log('[DESKTOP] Detected active backend server.');
    }
    createWindow();
  });

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('will-quit', () => {
  if (pythonProcess) {
    console.log('[DESKTOP] Shutting down backend process.');
    pythonProcess.kill();
  }
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
