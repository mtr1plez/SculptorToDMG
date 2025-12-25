import asyncio
import logging
import json
import queue # Синхронная очередь
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
import yaml

from src.project_manager import ProjectManager
from src.api.models import IngestRequest, BuildRequest, ProjectCreateRequest
from src.utils.tmdb_client import TMDBClient

# === ГЛОБАЛЬНАЯ ОЧЕРЕДЬ ===
msg_queue = queue.Queue()

# === ЛОГИРОВАНИЕ ===
class QueueHandler(logging.Handler):
    def emit(self, record):
        try:
            entry = json.dumps({
                "type": "log",
                "message": self.format(record),
                "level": record.levelname
            })
            msg_queue.put(entry)
        except:
            pass

logger = logging.getLogger()
logger.setLevel(logging.INFO)
queue_handler = QueueHandler()
formatter = logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s')
queue_handler.setFormatter(formatter)
logger.addHandler(queue_handler)

# === ИНИЦИАЛИЗАЦИЯ ===
BASE_DIR = Path(__file__).resolve().parent.parent.parent
logger.info(f"📂 Root Directory: {BASE_DIR}")
manager = ProjectManager(BASE_DIR)

tmdb_key = manager.config.get("api_keys", {}).get("tmdb")
tmdb_client = TMDBClient(tmdb_key) if tmdb_key else None

app = FastAPI(title="Sculptor AI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/images", StaticFiles(directory=manager.library_path), name="images")

# === ENDPOINTS ===

@app.get("/status")
def health_check():
    lib_path = manager.library_path
    lib_count = len(list(lib_path.glob("*"))) if lib_path.exists() else 0
    return {"status": "running", "library_count": lib_count}

@app.get("/library")
def get_library():
    movies = []
    lib_path = manager.library_path
    
    if lib_path.exists():
        for folder in lib_path.iterdir():
            if folder.is_dir() and not folder.name.startswith('.'):
                master_index_path = folder / "master_index.json"
                status_file = folder / ".ingest_status.json"  # <--- НОВОЕ
                has_index = master_index_path.exists()
                
                # === ЧИТАЕМ СТАТУС ОБРАБОТКИ ===
                ingest_status = None
                if status_file.exists():
                    try:
                        with open(status_file, 'r') as f:
                            ingest_status = json.load(f)
                    except: pass
                
                # TMDB Logic (оставляем как было)
                thumbnail_url = None
                cache_file = folder / ".tmdb_cache"
                
                if cache_file.exists():
                    try:
                        with open(cache_file, 'r') as f:
                            thumbnail_url = f.read().strip()
                    except: pass
                
                if not thumbnail_url and tmdb_client:
                    search_query = folder.name
                    if has_index:
                        try:
                            with open(master_index_path, 'r') as f:
                                meta = json.load(f)
                                search_query = meta.get("movie_name", folder.name)
                        except: pass
                    
                    try:
                        found_poster = tmdb_client.get_poster_url(search_query)
                        if found_poster:
                            thumbnail_url = found_poster
                            with open(cache_file, 'w') as f:
                                f.write(thumbnail_url)
                    except: pass
                
                if not thumbnail_url:
                    faces_dir = folder / "faces"
                    if faces_dir.exists():
                        images = list(faces_dir.glob("*.jpg"))
                        if images:
                            target_img = images[min(5, len(images)-1)]
                            thumbnail_url = f"http://localhost:8000/images/{folder.name}/faces/{target_img.name}"

                # === ФОРМИРУЕМ ОТВЕТ ===
                movie_data = {
                    "alias": folder.name,
                    "ready": has_index,
                    "path": str(folder.absolute()),
                    "thumbnail": thumbnail_url
                }
                
                # Добавляем статус обработки, если он есть
                if ingest_status:
                    movie_data["ingest_status"] = ingest_status.get("status", "unknown")
                    movie_data["percent"] = ingest_status.get("percent", 0)
                    movie_data["progress_text"] = ingest_status.get("progress_text", "")
                
                movies.append(movie_data)
    
    return movies

# === ВОТ ЭТИ ЭНДПОИНТЫ БЫЛИ ПОТЕРЯНЫ ===
@app.get("/projects")
def get_projects():
    projs = []
    proj_path = manager.projects_path
    
    # Создаем папку projects если её нет
    if not proj_path.exists():
        proj_path.mkdir(parents=True, exist_ok=True)

    if proj_path.exists():
        for folder in proj_path.iterdir():
            if folder.is_dir() and not folder.name.startswith('.'):
                projs.append({"name": folder.name, "path": str(folder.absolute())})
    return projs

@app.get("/projects/{name}")
def get_project_details(name: str):
    details = manager.get_project_details(name)
    if not details:
        return {"error": "Project not found"}
    return details

@app.post("/projects/create")
def create_project(req: ProjectCreateRequest):
    manager.create_project(req.name)
    return {"status": "created", "name": req.name}
# ========================================

@app.post("/ingest")
async def run_ingest(req: IngestRequest, background_tasks: BackgroundTasks):
    logger.info(f"🚀 API Request: Ingesting {req.alias}...")
    
    def progress_report(percent, status):
        msg = json.dumps({
            "type": "progress",
            "alias": req.alias,
            "percent": percent,
            "status": status
        })
        msg_queue.put(msg)

    background_tasks.add_task(
        manager.ingest_source, 
        req.file_path, 
        req.alias, 
        req.fullname,
        progress_report
    )
    return {"status": "started", "task": f"Ingest {req.alias}"}

@app.post("/build")
async def run_build(req: BuildRequest, background_tasks: BackgroundTasks):
    logger.info(f"🚀 API Request: Building {req.project_name}...")
    
    # Создаем колбэк для WebSocket (так же, как в /ingest)
    def progress_report(percent, status):
        msg = json.dumps({
            "type": "progress",
            "alias": req.project_name, # Важно: используем имя проекта как alias
            "percent": percent,
            "status": status
        })
        msg_queue.put(msg)

    # Запускаем задачу
    background_tasks.add_task(
        manager.build_project, 
        req.project_name, 
        req.sources, 
        req.audio_path,
        progress_report # <--- Передаем колбэк
    )
    return {"status": "started", "task": f"Build {req.project_name}"}

@app.websocket("/ws/logs")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            while not msg_queue.empty():
                msg = msg_queue.get_nowait()
                await websocket.send_text(msg)
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")

@app.delete("/library/{alias}")
def delete_library_item(alias: str):
    success = manager.delete_source_from_library(alias)
    if not success:
        return {"error": "Not found"}, 404
    return {"status": "deleted"}

@app.delete("/projects/{name}")
def delete_project_item(name: str):
    success = manager.delete_project(name)
    if not success:
        return {"error": "Not found"}, 404
    return {"status": "deleted"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)