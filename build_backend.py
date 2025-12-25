#!/usr/bin/env python3
"""
Скрипт сборки бэкенда SculptorPro с помощью PyInstaller
Собирает все зависимости, модели и ассеты в один исполняемый файл
"""

import sys
import os
import shutil
from pathlib import Path
import subprocess

def main():
    print("🚀 Starting SculptorPro Backend Build...")
    
    # Определяем пути
    project_root = Path(__file__).parent
    dist_dir = project_root / "dist"
    build_dir = project_root / "build"
    
    # Очищаем старые сборки
    if dist_dir.exists():
        print("🧹 Cleaning old dist...")
        shutil.rmtree(dist_dir)
    if build_dir.exists():
        print("🧹 Cleaning old build...")
        shutil.rmtree(build_dir)
    
    # Определяем hidden imports для всех AI библиотек
    hidden_imports = [
        # Core
        'yaml', 'json', 'pathlib', 'logging', 'asyncio', 'queue',
        
        # FastAPI & Web
        'fastapi', 'uvicorn', 'starlette', 'pydantic',
        'websockets', 'httpx',
        
        # AI Models - Whisper
        'whisper', 'torch', 'torchvision', 'torchaudio',
        'tiktoken', 'numpy', 'scipy',
        
        # AI Models - CLIP
        'clip', 'ftfy', 'regex', 'PIL',
        
        # AI Models - InsightFace
        'insightface', 'onnxruntime', 'onnx',
        'cv2', 'sklearn', 'skimage',
        
        # Gemini
        'google.generativeai', 'google.ai.generativelanguage',
        
        # Video Processing
        'scenedetect', 'moviepy', 'imageio', 'imageio_ffmpeg',
        
        # Utils
        'tqdm', 'click', 'requests',
    ]
    
    # Data files для моделей (добавляем пути к весам моделей)
    datas = [
        # Config
        ('config.yaml', '.'),
        
        # Whisper models (если предзагружены локально)
        # ('~/.cache/whisper', 'whisper/models'),
        
        # InsightFace models
        # ('~/.insightface', 'insightface/models'),
    ]
    
    # Формируем команду PyInstaller
    cmd = [
        'pyinstaller',
        '--name=SculptorProServer',
        '--onedir',  # Быстрее запускается чем --onefile
        '--windowed',  # Без консоли (на macOS)
        '--clean',
        '--noconfirm',
        
        # Добавляем все скрытые импорты
        *[f'--hidden-import={imp}' for imp in hidden_imports],
        
        # Добавляем data files
        *[f'--add-data={src}{os.pathsep}{dst}' for src, dst in datas],
        
        # Исключаем ненужное для уменьшения размера
        '--exclude-module=matplotlib',
        '--exclude-module=pandas',
        '--exclude-module=jupyter',
        '--exclude-module=notebook',
        
        # Главный файл
        'src/api/server.py'
    ]
    
    print(f"📦 Running PyInstaller...")
    print(f"Command: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, cwd=project_root)
    
    if result.returncode != 0:
        print("❌ Build failed!")
        sys.exit(1)
    
    print("✅ Backend build complete!")
    print(f"📂 Output: {dist_dir / 'SculptorProServer'}")
    
    # Опционально: создаем zip архив
    if sys.platform == 'darwin':
        print("📦 Creating macOS bundle...")
        # Здесь можно добавить создание .app bundle
    
    print("🎉 Build finished successfully!")

if __name__ == '__main__':
    main()