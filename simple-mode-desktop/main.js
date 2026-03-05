const { app, BrowserWindow } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const { pathToFileURL } = require('url');

function getDomainFromArgv() {
  const i = process.argv.indexOf('--domain');
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : '';
}

// 音声をユーザー操作なしでも再生できるようにする（app.ready より前に必須）
app.commandLine.appendSwitch('autoplay-policy', 'no-user-gesture-required');

// GLES3/GPU コンテキスト失敗・0xC0000005 対策（Windows）
// disable-software-rasterizer は付けない（ソフトウェア描画のフォールバックを残す）
app.disableHardwareAcceleration();
app.commandLine.appendSwitch('disable-gpu');
app.commandLine.appendSwitch('disable-gpu-sandbox');
// GPU を別プロセスではなくメインプロセスで動かし「Failed to create shared context for virtualization」を避ける
app.commandLine.appendSwitch('in-process-gpu');

const SIMPLE_CHAT_PY = path.join(__dirname, '..', 'simple_chat.py');
const ROOT_DIR = path.join(__dirname, '..');

let pythonProcess = null;
/** @type {Electron.BrowserWindow | null} 窓がGCで閉じないよう参照を保持 */
let mainWindow = null;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 320,
    height: 380,
    resizable: true,
    title: 'LiveTalk Simple Mode',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true
    },
    show: false
  });

  mainWindow.once('ready-to-show', () => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.show();
      mainWindow.focus();
    }
  });

  const domain = getDomainFromArgv();
  const fileUrl = pathToFileURL(path.join(__dirname, 'index.html')).href;
  mainWindow.loadURL(domain ? `${fileUrl}?domain=${encodeURIComponent(domain)}` : fileUrl);

  mainWindow.on('closed', () => {
    mainWindow = null;
    if (pythonProcess) {
      pythonProcess.kill();
      pythonProcess = null;
    }
  });

  mainWindow.webContents.on('render-process-gone', (_, details) => {
    console.error('[Simple Mode] レンダラーが落ちました:', details.reason, details.exitCode);
  });
  mainWindow.webContents.on('unresponsive', () => {
    console.warn('[Simple Mode] レンダラーが応答しません');
  });
}

function startSimpleChat() {
  pythonProcess = spawn('python', [SIMPLE_CHAT_PY], {
    cwd: ROOT_DIR,
    stdio: 'inherit',
    env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
  });
  pythonProcess.on('error', (err) => {
    console.error('simple_chat.py の起動に失敗しました:', err.message);
  });
  pythonProcess.on('close', (code) => {
    if (code !== null && code !== 0) {
      console.log('simple_chat.py 終了 code:', code);
    }
  });
}

app.whenReady().then(() => {
  startSimpleChat();
  setTimeout(createWindow, 2000);
});

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
