const { app, BrowserWindow, globalShortcut, ipcMain } = require('electron');

function createWindow() {
  const win = new BrowserWindow({
    width: 1200,
    height: 800,
    title: "JARVIS - MARK XLIX",
    autoHideMenuBar: true,
    backgroundColor: '#030612',
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false
    }
  });

  win.loadURL('http://localhost:5173');

  // F11 Fullscreen Toggle
  globalShortcut.register('F11', () => {
    win.setFullScreen(!win.isFullScreen());
  });

  // Native window minimize via IPC
  ipcMain.on('minimize-window', () => {
    win.minimize();
  });
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
