import os
from pathlib import Path
import sys

def get_app_data_dir():
    """
    Возвращает путь к директории приложения в зависимости от платформы.
    macOS: ~/Documents/SculptorPro/
    Windows: ~/Documents/SculptorPro/
    Linux: ~/.sculptorpro/
    """
    if sys.platform == 'darwin':  # macOS
        base = Path.home() / "Documents" / "SculptorPro"
    elif sys.platform == 'win32':  # Windows
        base = Path.home() / "Documents" / "SculptorPro"
    else:  # Linux
        base = Path.home() / ".sculptorpro"
    
    base.mkdir(parents=True, exist_ok=True)
    return base

def get_library_path():
    """Путь к библиотеке фильмов"""
    path = get_app_data_dir() / "_library"
    path.mkdir(exist_ok=True)
    return path

def get_projects_path():
    """Путь к проектам"""
    path = get_app_data_dir() / "projects"
    path.mkdir(exist_ok=True)
    return path

def get_config_path():
    """Путь к конфигурации"""
    return get_app_data_dir() / "config.yaml"

def ensure_app_structure():
    """
    Создает структуру папок при первом запуске.
    Вызывается при старте сервера.
    """
    app_dir = get_app_data_dir()
    
    # Создаем основные директории
    get_library_path()
    get_projects_path()
    
    # Создаем placeholder файлы
    lib_placeholder = get_library_path() / "placeholder.txt"
    if not lib_placeholder.exists():
        lib_placeholder.write_text("Here you will see all the films you indexed.")
    
    proj_placeholder = get_projects_path() / "placeholder.txt"
    if not proj_placeholder.exists():
        proj_placeholder.write_text("Here you will see all the projects.")
    
    # Копируем config.yaml если его нет
    config_path = get_config_path()
    if not config_path.exists():
        default_config = """# SculptorPro Configuration
paths:
  library: "_library"
  projects: "projects"

models:
  whisper: "small"
  gemini: "gemini-2.5-flash"
  clip: "ViT-B/32"
  face_detection: "buffalo_s"

api_keys:
  tmdb: "6c4e1849b92d6a813f34cda134db66a8"
"""
        config_path.write_text(default_config)
    
    return app_dir