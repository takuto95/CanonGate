const { app, BrowserWindow, screen, ipcMain } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

// Fix for transparent window issues on Windows
app.disableHardwareAcceleration();
// Additional GPU fix for some Windows configs
app.commandLine.appendSwitch('disable-gpu');

let pythonProcess = null;
let mainWin = null;
let currentMode = 'simple'; // 'mascot' or 'simple'

function setWindowMode(mode) {
    if (!mainWin) return;
    currentMode = mode;

    if (mode === 'mascot') {
        mainWin.setSize(400, 600);
        mainWin.setResizable(true);
        // Mascot mode is usually centered or bottom right
        mainWin.loadFile(path.join(__dirname, 'mascot-web', 'index.html'));
    } else {
        // Simple Mode (Cockpit) is wider and taller
        mainWin.setSize(900, 850);
        mainWin.setResizable(true);
        mainWin.loadFile(path.join(__dirname, 'simple-mode-desktop', 'index.html'));
    }
}

function createWindow() {
    const { width, height } = screen.getPrimaryDisplay().workAreaSize;

    mainWin = new BrowserWindow({
        width: 900,
        height: 850,
        x: Math.round((width - 900) / 2),
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

    ipcMain.on('change-mode', (event, mode) => {
        setWindowMode(mode);
    });

    // Start with default mode
    setWindowMode('simple');

    // Start Python Backend (The Brain)
    console.log('[Electron] Starting Python Backend...');

    // Parse domain from Electron arguments (e.g. npm start -- --domain tech)
    const args = ['simple_chat.py'];
    const domainIdx = process.argv.indexOf('--domain');
    if (domainIdx !== -1 && process.argv[domainIdx + 1]) {
        args.push('--domain', process.argv[domainIdx + 1]);
    }

    pythonProcess = spawn('python', args, {
        cwd: __dirname,
        stdio: 'inherit'
    });

    pythonProcess.on('error', (err) => {
        console.error('Failed to start Python process:', err);
    });

    pythonProcess.on('close', (code) => {
        console.log(`Python process exited with code ${code}`);
    });
}

app.whenReady().then(createWindow);

app.on('will-quit', () => {
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
