import os
import sys
import time
import yaml
import argparse
import json
import shutil
import logging
from pathlib import Path

# Настройка путей проекта
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Импорт утилиты путей
from src.utils.app_paths import (
    get_library_path, 
    get_projects_path, 
    get_config_path, 
    ensure_app_structure,
    get_app_data_dir
)

# Импорты модулей проекта
from src.ingestion.scene_indexer import SceneIndexer
from src.ingestion.flicker_fixer import FlickerFixer
from src.ingestion.face_processor import FaceProcessor
from src.ingestion.clip_encoder import ClipEncoder
from src.ingestion.metadata_manager import MetadataManager
from src.analysis.audio_processor import AudioProcessor
from src.analysis.director_agent import DirectorAgent
from src.matching.smart_matcher import SmartMatcher
from src.matching.premiere_exporter import PremiereExporter

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [MANAGER] - %(message)s'
)
logger = logging.getLogger(__name__)


class ProjectManager:
    """Управляет проектами видео-эссе и библиотекой источников."""
    
    def __init__(self, root_dir=None):
        """
        Инициализация менеджера проектов.
        
        Args:
            root_dir: Корневая директория проекта (опционально, для совместимости)
        """
        # Инициализируем структуру приложения
        app_dir = ensure_app_structure()
        logger.info(f"📂 App Data Directory: {app_dir}")
        
        # Для обратной совместимости с CLI
        self.root_dir = Path(root_dir).resolve() if root_dir else app_dir
        
        # Загружаем конфиг
        self.config = self._load_config()
        
        # Настраиваем директории (используя app_paths)
        self._setup_directories()

    def _load_config(self):
        """Загружает конфигурацию из app_paths location."""
        config_path = get_config_path()
        
        if config_path.exists() and config_path.is_file():
            try:
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                    logger.info(f"✅ Config loaded from: {config_path}")
                    return config
            except Exception as e:
                logger.error(f"Error loading config: {e}")
        
        logger.warning(f"⚠️ Config not found at {config_path}. Using defaults.")
        return {
            "models": {
                "whisper": "small",
                "face_detection": "buffalo_s",
                "gemini": "gemini-2.5-flash",
                "clip": "ViT-B/32"
            },
            "paths": {
                "library": "_library",
                "projects": "projects"
            }
        }

    def _setup_directories(self):
        """Создает необходимые директории проекта."""
        # Используем пути из app_paths (Documents/SculptorPro)
        self.library_path = get_library_path()
        self.projects_path = get_projects_path()
        
        logger.info(f"📚 Library Path: {self.library_path}")
        logger.info(f"📁 Projects Path: {self.projects_path}")
        
        # Убеждаемся что директории существуют
        self._ensure_dir(self.library_path)
        self._ensure_dir(self.projects_path)

    def _ensure_dir(self, path):
        """Создает директорию, если её не существует."""
        if not path.exists():
            os.makedirs(path, exist_ok=True)
            logger.info(f"Created directory: {path}")

    # === КОМАНДА 1: СОЗДАНИЕ ПРОЕКТА ===
    
    def create_project(self, project_name):
        """
        Создает структуру папок для нового видео-эссе.
        
        Args:
            project_name: Название проекта
        """
        project_dir = self.projects_path / project_name
        
        if project_dir.exists():
            logger.warning(f"Project '{project_name}' already exists.")
            return

        structure = ['input', 'artifacts', 'output']
        for folder in structure:
            self._ensure_dir(project_dir / folder)
        
        logger.info(f"✅ Project '{project_name}' initialized successfully.")
        logger.info(f"👉 Put your voiceover audio into: {project_dir}/input/")

    # === КОМАНДА 2: ИНДЕКСАЦИЯ ИСТОЧНИКА ===
    
    def ingest_source(self, file_path, alias, fullname=None, progress_callback=None):
        """
        Индексирует видеофайл и добавляет его в библиотеку.
        
        Args:
            file_path: Путь к видеофайлу
            alias: Короткое имя для библиотеки
            fullname: Полное название фильма (опционально)
            progress_callback: Функция для отчета о прогрессе (percent, text)
        """
        file_path = Path(file_path)
        if not file_path.exists():
            logger.error(f"Source file not found: {file_path}")
            return

        source_name = alias
        movie_real_name = fullname if fullname else alias
        target_dir = self.library_path / source_name
        status_file = target_dir / ".ingest_status.json"

        def save_ingest_state(status, percent=0, text=""):
            """Сохраняет состояние обработки в файл."""
            self._ensure_dir(target_dir)
            status_data = {
                "status": status,
                "percent": percent,
                "progress_text": text,
                "last_updated": time.time()
            }
            with open(status_file, "w") as f:
                json.dump(status_data, f, indent=2)

        def report(percent, text):
            """Отправляет прогресс в callback и сохраняет в файл."""
            if progress_callback:
                progress_callback(percent, text)
            save_ingest_state("processing", percent, text)

        # Начало обработки
        report(0, "Initializing...")
        
        try:
            logger.info(f"🚀 Starting ingestion for '{movie_real_name}'...")

            # STEP 1: Детекция сцен
            report(10, "Detecting Scenes...")
            indexer = SceneIndexer(file_path, target_dir)
            indexer.process()

            # STEP 1.5: Исправление мерцаний
            report(25, "Fixing Flickers...")
            try:
                fixer = FlickerFixer(target_dir)
                fixer.fix(offset=0.2)
            except Exception as e:
                logger.warning(f"Flicker Fixer skipped/failed: {e}")

            # STEP 2: Детекция лиц
            report(30, "Scanning Faces (This takes time)...")
            fp = FaceProcessor(target_dir)
            fp.process_faces()

            # STEP 3: CLIP эмбеддинги
            report(80, "Building Index...")
            try:
                logger.info("🎨 Generating CLIP embeddings...")
                clip_model = self.config.get("models", {}).get("clip", "ViT-B/32")
                clip_encoder = ClipEncoder(target_dir, model_name=clip_model)
                clip_encoder.process_embeddings()
            except Exception as e:
                logger.error(f"Failed during CLIP encoding: {e}")
                save_ingest_state("failed", 0, "Error occurred")
                if progress_callback:
                    progress_callback(0, "Error occurred")
                return

            # STEP 4: Агрегация метаданных
            report(90, "Building Index...")
            try:
                logger.info(f"🧠 Linking everything together for '{movie_real_name}'...")
                meta = MetadataManager(
                    target_dir,
                    movie_name=movie_real_name,
                    source_video_path=file_path
                )
                meta.build_master_index()
            except Exception as e:
                logger.error(f"Failed during metadata aggregation: {e}")
                save_ingest_state("failed", 0, "Error occurred")
                if progress_callback:
                    progress_callback(0, "Error occurred")
                return

            # Завершение
            save_ingest_state("ready", 100, "Ready")
            if progress_callback:
                progress_callback(100, "Ready")
            logger.info(f"🎉 Source '{source_name}' is FULLY INDEXED inside library.")
            
        except Exception as e:
            logger.error(f"❌ INGEST FAILED: {e}")
            save_ingest_state("failed", 0, f"Error: {str(e)}")
            if progress_callback:
                progress_callback(0, f"Error: {str(e)}")

    # === ПОЛУЧЕНИЕ ИНФОРМАЦИИ О ПРОЕКТЕ ===
    
    def get_project_details(self, project_name):
        """
        Возвращает детали проекта.
        
        Args:
            project_name: Название проекта
            
        Returns:
            dict: Информация о проекте или None
        """
        project_dir = self.projects_path / project_name
        if not project_dir.exists():
            return None
            
        input_dir = project_dir / "input"
        meta_path = project_dir / "project_meta.json"
        
        # Проверяем наличие аудио
        audio_exists = False
        if input_dir.exists():
            audio_files = [
                f.name for f in input_dir.glob("*.*")
                if f.suffix.lower() in ['.mp3', '.wav', '.m4a']
            ]
            audio_exists = len(audio_files) > 0

        # Читаем метаданные
        meta = {}
        if meta_path.exists():
            try:
                with open(meta_path, 'r') as f:
                    meta = json.load(f)
            except Exception:
                pass

        return {
            "name": project_name,
            "path": str(project_dir),  # Добавляем путь
            "audio_ready": audio_exists,
            "sources": meta.get("sources", []),
            "status": meta.get("status", "idle"),
            "percent": meta.get("percent", 0),
            "progress_text": meta.get("progress_text", "Initializing...")
        }

    # === КОМАНДА 3: СБОРКА ПРОЕКТА ===
    
    def build_project(self, project_name, sources_list, audio_path=None, progress_callback=None):
        """
        Генерирует монтаж для проекта.
        
        Args:
            project_name: Название проекта
            sources_list: Список источников или строка через запятую
            audio_path: Путь к аудиофайлу (опционально)
            progress_callback: Функция для отчета о прогрессе
        """
        logger.info(f"🔨 Building project '{project_name}'...")

        project_dir = self.projects_path / project_name
        if not project_dir.exists():
            logger.error(f"Project '{project_name}' not found. Run 'create' first.")
            return

        input_dir = project_dir / "input"
        output_dir = project_dir / "output"
        artifacts_dir = project_dir / "artifacts"

        self._ensure_dir(input_dir)
        self._ensure_dir(output_dir)
        self._ensure_dir(artifacts_dir)

        meta_path = project_dir / "project_meta.json"

        def save_state(status, percent=0, text=""):
            """Сохраняет состояние сборки в файл."""
            meta_data = {
                "sources": sources_list,
                "status": status,
                "percent": percent,
                "progress_text": text,
                "last_updated": time.time()
            }
            with open(meta_path, "w") as f:
                json.dump(meta_data, f, indent=2)

        def report(percent, text):
            """Отправляет прогресс в callback и сохраняет в файл."""
            if progress_callback:
                progress_callback(percent, text)
            save_state("building", percent, text)

        # Начало сборки
        report(0, "Initializing workspace...")

        try:
            # Копирование аудио (опционально)
            if audio_path:
                src_audio = Path(audio_path)
                if not src_audio.exists():
                    raise Exception(f"Audio file not found: {audio_path}")

                dest_audio = input_dir / f"reference{src_audio.suffix.lower()}"
                shutil.copy2(src_audio, dest_audio)
                logger.info(f"🎵 Audio copied: {dest_audio.name}")

            # Проверка наличия аудио
            audio_files = [
                f for f in input_dir.iterdir()
                if f.suffix.lower() in [".mp3", ".wav", ".m4a"]
            ]

            if not audio_files:
                raise Exception("No audio file found in project/input")

            audio_path = audio_files[0]
            logger.info(f"✅ Audio verified: {audio_path.name}")
            report(10, "Audio verified")

            # Нормализация списка источников
            if isinstance(sources_list, str):
                source_list = [s.strip() for s in sources_list.split(",") if s.strip()]
            else:
                source_list = sources_list

            if not source_list:
                raise Exception("No sources provided")

            # Проверка источников
            for src in source_list:
                if not (self.library_path / src).exists():
                    raise Exception(f"Source '{src}' not found in library")

            logger.info(f"🎬 Sources verified: {source_list}")
            report(20, "Sources verified")

            # STEP 1: Транскрипция через Whisper
            transcript_path = artifacts_dir / "transcript.json"

            if transcript_path.exists():
                logger.info("⏭ Transcript exists, skipping Whisper")
            else:
                logger.info("🎙 Running Whisper...")
                processor = AudioProcessor(
                    model_size=self.config["models"]["whisper"]
                )
                processor.process(audio_path, transcript_path)

            report(40, "Transcript ready")

            # STEP 2: Генерация скрипта через Director Agent
            script_path = artifacts_dir / "script.json"

            if script_path.exists():
                logger.info("⏭ Script exists, skipping Director")
            else:
                logger.info("🎬 Director Agent running...")
                director = DirectorAgent(self.library_path)
                director.process(transcript_path, script_path, source_list)

            report(60, "Visual script generated")

            # STEP 3: Подбор сцен через Smart Matcher
            edl_path = artifacts_dir / "edl.json"

            logger.info("🎯 Smart Matcher running...")
            matcher = SmartMatcher(self.library_path)
            matcher.match(script_path, edl_path, source_list)

            report(80, "Scenes matched")

            # STEP 4: Экспорт в Premiere XML
            output_xml = output_dir / f"{project_name}_v2.xml"

            logger.info("🎞 Exporting Premiere XML...")
            exporter = PremiereExporter(fps=24)
            exporter.export(edl_path, output_xml, audio_path)

            save_state("ready", 100, "Build complete")
            if progress_callback:
                progress_callback(100, "Build complete")

            logger.info("✨ PROJECT BUILD COMPLETE ✨")
            logger.info(f"📂 Import into Premiere: {output_xml}")

        except Exception as e:
            logger.error(f"❌ BUILD FAILED: {e}")
            save_state("failed", 0, f"Error: {str(e)}")
            if progress_callback:
                progress_callback(0, f"Error: {str(e)}")

    # === УДАЛЕНИЕ ИСТОЧНИКА ===
    
    def delete_source_from_library(self, alias):
        """
        Удаляет источник из библиотеки.
        
        Args:
            alias: Короткое имя источника
            
        Returns:
            bool: True если успешно удалено
        """
        target_dir = self.library_path / alias
        if target_dir.exists():
            shutil.rmtree(target_dir)
            logger.info(f"🗑 Deleted source: {alias}")
            return True
        return False

    # === УДАЛЕНИЕ ПРОЕКТА ===
    
    def delete_project(self, name):
        """
        Удаляет проект.
        
        Args:
            name: Название проекта
            
        Returns:
            bool: True если успешно удалено
        """
        target_dir = self.projects_path / name
        if target_dir.exists():
            shutil.rmtree(target_dir)
            logger.info(f"🗑 Deleted project: {name}")
            return True
        return False


def main():
    """CLI интерфейс для управления проектами."""
    parser = argparse.ArgumentParser(description="Sculptor Pro CLI Manager")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Команда: create
    create_parser = subparsers.add_parser(
        "create",
        help="Create a new project workspace"
    )
    create_parser.add_argument(
        "--name",
        required=True,
        help="Name of the project (e.g. matrix_essay)"
    )

    # Команда: ingest
    ingest_parser = subparsers.add_parser(
        "ingest",
        help="Add a movie to the library"
    )
    ingest_parser.add_argument(
        "--file",
        required=True,
        help="Path to video file"
    )
    ingest_parser.add_argument(
        "--alias",
        required=True,
        help="Short name for the library (e.g. matrix)"
    )
    ingest_parser.add_argument(
        "--fullname",
        help="Full movie title for Gemini (e.g. 'The Matrix 1999')"
    )

    # Команда: build
    build_parser = subparsers.add_parser(
        "build",
        help="Generate XML from audio"
    )
    build_parser.add_argument(
        "--project",
        required=True,
        help="Project name"
    )
    build_parser.add_argument(
        "--sources",
        required=True,
        help="Comma-separated list of sources (e.g. matrix,fight_club)"
    )

    args = parser.parse_args()
    
    # Инициализация менеджера (теперь без обязательного root_dir)
    manager = ProjectManager()

    # Выполнение команд
    if args.command == "create":
        manager.create_project(args.name)
    elif args.command == "ingest":
        manager.ingest_source(args.file, args.alias, args.fullname)
    elif args.command == "build":
        manager.build_project(args.project, args.sources)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()