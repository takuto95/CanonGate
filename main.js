const { app, BrowserWindow, screen, ipcMain } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const { pathToFileURL } = require('url');

function getDomainFromArgv() {
    const i = process.argv.indexOf('--domain');
    return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : '';
}

// Fix for transparent window issues on Windows
app.disableHardwareAcceleration();
// Additional GPU fix for some Windows configs
app.commandLine.appendSwitch('disable-gpu');

let pythonProcess = null;
let brainProcess = null;
let mainWin = null;
// Simplified load logic (Simple Mode only)
function loadSimpleMode() {
    if (!mainWin) return;
    const domain = getDomainFromArgv();
    const filePath = path.join(__dirname, 'simple-mode-desktop', 'index.html');
    const fileUrl = pathToFileURL(filePath).href;
    mainWin.loadURL(domain ? `${fileUrl}?domain=${encodeURIComponent(domain)}` : fileUrl);
}

function createWindow() {
    const { width, height } = screen.getPrimaryDisplay().workAreaSize;

    mainWin = new BrowserWindow({
        width: 1200,
        height: 850,
        x: Math.round((width - 1200) / 2),
        y: Math.round((height - 850) / 2),
        frame: false,
        transparent: true,
        alwaysOnTop: true,
        resizable: true,
        hasShadow: false,
        backgroundColor: '#00000000',
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false
        },
        show: false
    });

    mainWin.once('ready-to-show', () => {
        console.log('[Electron] Window ready-to-show fired.');
        mainWin.show();
        mainWin.focus();
    });

    ipcMain.on('minimize-window', () => {
        if (mainWin) mainWin.minimize();
    });

    ipcMain.on('maximize-window', () => {
        if (mainWin) {
            if (mainWin.isMaximized()) {
                mainWin.unmaximize();
            } else {
                mainWin.maximize();
            }
        }
    });

    // Start Simple Mode UI
    loadSimpleMode();

    // Start Python Backend (The Brain)
    console.log('[Electron] Starting Python Backend...');

    // Parse domain from Electron arguments (e.g. npm start -- --domain tech)
    const args = ['simple_chat.py'];
    const domainIdx = process.argv.indexOf('--domain');
    if (domainIdx !== -1 && process.argv[domainIdx + 1]) {
        args.push('--domain', process.argv[domainIdx + 1]);
    }

    // Resolve Python: prefer sibling .venv, then bare 'python'
    const fs = require('fs');
    const venvPython = path.join(__dirname, '..', '.venv', 'Scripts', 'python.exe');
    const pythonCmd = fs.existsSync(venvPython) ? venvPython : 'python';

    pythonProcess = spawn(pythonCmd, args, {
        cwd: __dirname,
        stdio: 'inherit',
        env: { ...process.env, PYTHONIOENCODING: 'utf-8', PYTHONUTF8: '1' }
    });

    pythonProcess.on('error', (err) => {
        console.error('Failed to start Python process:', err);
    });

    pythonProcess.on('close', (code) => {
        console.log(`Python process exited with code ${code}`);
    });

    setTimeout(() => {
        const brainArgs = ['canon_brain.py'];
        const domainIdx2 = process.argv.indexOf('--domain');
        if (domainIdx2 !== -1 && process.argv[domainIdx2 + 1]) {
            brainArgs.push('--domain', process.argv[domainIdx2 + 1]);
        }
        console.log('[Electron] Starting Canon Brain...');
        brainProcess = spawn(pythonCmd, brainArgs, {
            cwd: __dirname,
            stdio: 'inherit',
            env: { ...process.env, PYTHONIOENCODING: 'utf-8', PYTHONUTF8: '1' }
        });
        brainProcess.on('error', (err) => console.error('[Brain] Failed to spawn:', err));
        brainProcess.on('close', (code) => console.log(`[Brain] exited with code ${code}`));
    }, 3000);
}

app.whenReady().then(createWindow);

app.on('will-quit', () => {
    if (brainProcess) {
        brainProcess.kill();
        brainProcess = null;
    }
    if (pythonProcess) {
        pythonProcess.kill();
        pythonProcess = null;
    }
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit();
    }
});
