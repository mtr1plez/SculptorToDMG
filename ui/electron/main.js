import { app, BrowserWindow, ipcMain, dialog, shell } from 'electron';
import path from 'path';
import { fileURLToPath } from 'url';
import { spawn } from 'child_process';
import { existsSync } from 'fs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

let mainWindow;
let serverProcess = null;

// === ОПРЕДЕЛЯЕМ ПУТИ К СЕРВЕРУ ===
function getServerPath() {
  if (app.isPackaged) {
    // В продакшене: бэкенд находится в Resources
    if (process.platform === 'darwin') {
      return path.join(process.resourcesPath, 'server', 'SculptorProServer', 'SculptorProServer');
    } else if (process.platform === 'win32') {
      return path.join(process.resourcesPath, 'server', 'SculptorProServer', 'SculptorProServer.exe');
    }
  } else {
    // В разработке: запускаем Python напрямую
    return null; // Предполагаем, что dev сервер запущен отдельно
  }
}

// === ЗАПУСК БЭКЕНДА ===
function startBackendServer() {
  return new Promise((resolve, reject) => {
    const serverPath = getServerPath();
    
    if (!serverPath) {
      console.log('Development mode: backend should be running separately');
      resolve();
      return;
    }

    if (!existsSync(serverPath)) {
      reject(new Error(`Backend not found at: ${serverPath}`));
      return;
    }

    console.log('Starting backend server...');
    
    serverProcess = spawn(serverPath, [], {
      stdio: 'inherit',
      detached: false
    });

    serverProcess.on('error', (err) => {
      console.error('Failed to start backend:', err);
      reject(err);
    });

    serverProcess.on('exit', (code) => {
      console.log(`Backend exited with code ${code}`);
      serverProcess = null;
    });

    // Даем серверу время на запуск
    setTimeout(() => {
      resolve();
    }, 2000);
  });
}

// === СОЗДАНИЕ ОКНА ===
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 1024,
    minHeight: 768,
    backgroundColor: '#09090b',
    titleBarStyle: 'hiddenInset', // Красивый нативный titlebar на macOS
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      webSecurity: false
    },
    title: "Sculptor Pro",
    icon: path.join(__dirname, '../resources/icon.icns'), // Иконка приложения
    show: false // Не показываем пока не загрузится
  });

  // Показываем окно только когда оно готово (избегаем белого фликера)
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  const startUrl = process.env.ELECTRON_START_URL || 'http://localhost:5173';
  mainWindow.loadURL(startUrl);

  mainWindow.on('closed', function () {
    mainWindow = null;
  });

  // Open DevTools in development
  if (!app.isPackaged) {
    mainWindow.webContents.openDevTools();
  }
}

// === ЖИЗНЕННЫЙ ЦИКЛ ПРИЛОЖЕНИЯ ===
app.on('ready', async () => {
  try {
    // Сначала запускаем бэкенд
    await startBackendServer();
    
    // Потом создаем окно
    createWindow();
  } catch (error) {
    console.error('Failed to initialize app:', error);
    
    dialog.showErrorBox(
      'Startup Error',
      'Failed to start Sculptor Pro backend. Please try again.'
    );
    
    app.quit();
  }
});

app.on('window-all-closed', function () {
  // На macOS приложения обычно остаются активными пока не нажат Cmd+Q
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', function () {
  if (mainWindow === null) {
    createWindow();
  }
});

app.on('before-quit', () => {
  // Убиваем сервер при закрытии приложения
  if (serverProcess) {
    console.log('Shutting down backend server...');
    serverProcess.kill();
  }
});

// === IPC HANDLERS ===
ipcMain.on('open-file-dialog', (event) => {
  dialog.showOpenDialog(mainWindow, {
    properties: ['openFile'],
    filters: [
      { name: 'Movies', extensions: ['mp4', 'mkv', 'mov', 'avi'] }
    ]
  }).then(result => {
    if (!result.canceled && result.filePaths.length > 0) {
      event.reply('selected-file', result.filePaths[0]);
    }
  }).catch(err => {
    console.log(err);
  });
});

ipcMain.on('open-audio-dialog', (event) => {
  dialog.showOpenDialog(mainWindow, {
    properties: ['openFile'],
    filters: [
      { name: 'Audio', extensions: ['mp3', 'wav', 'm4a', 'flac'] }
    ]
  }).then(result => {
    if (!result.canceled && result.filePaths.length > 0) {
      event.reply('selected-audio', result.filePaths[0]);
    }
  }).catch(err => {
    console.log(err);
  });
});

ipcMain.on('open-folder', (event, folderPath) => {
  shell.openPath(folderPath);
});