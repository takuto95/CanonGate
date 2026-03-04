const electron = require('electron');
console.log('[Electron Debug] Keys:', Object.keys(electron));
console.log('[Electron Debug] Process Type:', process.type);

const { app, BrowserWindow } = electron;
console.log('[Electron Debug] App exists:', !!app);

if (app) {
    app.whenReady().then(() => {
        console.log('[Electron Debug] App Ready');
        const win = new BrowserWindow({ width: 800, height: 600 });
        win.loadURL('data:text/html,<h1>Electron Debug Mode</h1>');
    });
} else {
    console.error('[Electron Debug] FATAL: app is undefined');
    process.exit(1);
}
