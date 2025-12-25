import json
import logging
import torch
import clip
import numpy as np
from pathlib import Path
from tqdm import tqdm

logger = logging.getLogger(__name__)

class SmartMatcher:
    def __init__(self, library_path, model_name="ViT-B/32"):
        self.library_path = Path(library_path)
        # CLIP для текста очень легкий, CPU справляется мгновенно
        self.device = "cpu" 
        
        logger.info(f"🧠 Loading CLIP model for matching...")
        self.model, _ = clip.load(model_name, device=self.device)
        
        # Кэш для загруженных данных фильмов
        self.loaded_sources = {}

    def _load_source(self, source_name):
        """Загружает индекс и эмбеддинги фильма в память."""
        if source_name in self.loaded_sources:
            return self.loaded_sources[source_name]

        source_dir = self.library_path / source_name
        index_path = source_dir / "master_index.json"
        emb_path = source_dir / "embeddings.npy"

        if not index_path.exists() or not emb_path.exists():
            logger.error(f"❌ Missing index/embeddings for {source_name}")
            return None

        logger.info(f"📂 Loading source data: {source_name}")
        with open(index_path, 'r') as f:
            index_data = json.load(f)
        
        # === ПОДДЕРЖКА НОВОГО И СТАРОГО ФОРМАТА ===
        # Новый формат: {"movie_name": "...", "source_video_path": "...", "scenes": [...]}
        # Старый формат: просто список сцен [...]
        if isinstance(index_data, dict) and "scenes" in index_data:
            # Новый формат
            master_index = index_data["scenes"]
            source_video_path = index_data.get("source_video_path")
        else:
            # Старый формат (обратная совместимость)
            master_index = index_data
            source_video_path = None
            logger.warning(f"⚠️ {source_name} uses old index format (no video path). Consider re-indexing.")
        
        # Загружаем словарь эмбеддингов
        embeddings = np.load(emb_path, allow_pickle=True).item() 
        
        ordered_vectors = []
        valid_scenes = []
        
        # Синхронизируем список сцен с матрицей векторов
        for scene in master_index:
            s_id = scene['id']
            if s_id in embeddings:
                ordered_vectors.append(embeddings[s_id])
                valid_scenes.append(scene)
        
        if not ordered_vectors:
            return None
            
        # Создаем матрицу поиска
        matrix = np.array(ordered_vectors) 
        
        # Нормализация для NumPy (здесь keepdims во множественном числе - верно)
        norm = np.linalg.norm(matrix, axis=1, keepdims=True)
        matrix = matrix / (norm + 1e-8)

        # Переводим в PyTorch Tensor для быстрого умножения
        data = {
            "scenes": valid_scenes,
            "matrix": torch.from_numpy(matrix).float().to(self.device),
            "source_name": source_name,
            "source_video_path": source_video_path  # <--- ДОБАВИЛИ ПУТЬ К ВИДЕО
        }
        self.loaded_sources[source_name] = data
        return data

    def match(self, script_path, output_path, source_names):
        script_path = Path(script_path)
        with open(script_path, 'r') as f:
            script = json.load(f)

        # 1. Загрузка источников
        active_sources = []
        for src in source_names:
            data = self._load_source(src)
            if data: active_sources.append(data)
            
        if not active_sources:
            logger.error("No valid sources loaded!")
            return

        final_edl = [] 
        used_scene_ids = set() # Сет использованных сцен для защиты от повторов

        logger.info(f"🎯 Matching {len(script)} segments...")

        for segment in tqdm(script, desc="Matching"):
            query_text = segment.get("visual_query", "")
            target_char = segment.get("character")
            target_shot = segment.get("shot_type")
            
            # 2. Токенизация и энкодинг текста
            text_token = clip.tokenize([query_text], truncate=True).to(self.device)
            
            with torch.no_grad():
                text_emb = self.model.encode_text(text_token).float()
                
                # !!! ИСПРАВЛЕНИЕ: В PyTorch аргумент называется keepdim (единственное число) !!!
                text_emb /= text_emb.norm(dim=-1, keepdim=True)

            best_score = -10000
            best_match = None
            best_source = None

            # 3. Поиск по всем фильмам
            for src_data in active_sources:
                # Матричное умножение (Cosine Similarity)
                # Результат: массив схожести для всех сцен сразу
                sim_scores = (text_emb @ src_data["matrix"].T).squeeze(0).cpu().numpy()

                for idx, scene in enumerate(src_data["scenes"]):
                    s_id = scene['id']
                    
                    # Базовый скор от CLIP (обычно от 15 до 35)
                    score = sim_scores[idx] * 100.0 

                    # --- СИСТЕМА ФИЛЬТРОВ И ШТРАФОВ ---

                    # A. Фильтр Персонажа (Самый важный)
                    scene_chars = scene["content"].get("characters", [])
                    
                    if target_char:
                        # Если ищем конкретного героя
                        if target_char in scene_chars:
                            score += 500 # Огромный бонус, если нашли
                        else:
                            score -= 500 # Огромный штраф, если героя нет
                    else:
                        # Если ищем B-Roll (пейзаж, деталь), а в кадре герои
                        if scene_chars: 
                            score -= 50 # Небольшой штраф, лучше найти пустой кадр

                    # B. Фильтр Типа Кадра (Close-Up, Wide...)
                    scene_shot = scene["visual"].get("shot_type", "Unknown")
                    if target_shot and scene_shot == target_shot:
                        score += 50 # Бонус за правильную крупность плана
                    
                    # C. Защита от повторов
                    if s_id in used_scene_ids:
                        score -= 10000 # Запрещаем использовать сцену повторно

                    # Запоминаем лидера
                    if score > best_score:
                        best_score = score
                        best_match = scene
                        best_source = src_data["source_name"]

            # 4. Сохранение результата
            if best_match:
                used_scene_ids.add(best_match['id'])
                best_source_data = next((s for s in active_sources if s["source_name"] == best_source), None)
                video_path = best_source_data["source_video_path"] if best_source_data else None
                
                edit_entry = {
                    "segment_id": segment.get("segment_id", 0),
                    "text": segment.get("text"),
                    # Путь к картинке (для дебага)
                    "source_file": best_match["visual"]["path"], 
                    "source_project_alias": best_source,
                    "source_video_path": video_path,
                    "scene_id": best_match['id'],
                    # Таймкоды
                    "in_point": best_match['time']['start'],
                    "out_point": best_match['time']['end'],
                    "duration": best_match['time']['end'] - best_match['time']['start'],
                    "target_duration": segment.get('target_duration', segment['end'] - segment['start']),
                    # Метаданные
                    "match_score": float(best_score),
                    "shot_type": best_match["visual"]["shot_type"],
                    "characters": best_match["content"]["characters"]
                }
                final_edl.append(edit_entry)
            else:
                logger.warning(f"⚠️ No match found for segment: {segment.get('text', '')[:20]}...")

        # Сохраняем в JSON
        with open(output_path, 'w') as f:
            json.dump(final_edl, f, indent=2)
            
        logger.info(f"✅ Created Edit Decision List with {len(final_edl)} cuts: {output_path}")