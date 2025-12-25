import json
import logging
from pathlib import Path
from src.utils.gemini_client import GeminiClient

logger = logging.getLogger(__name__)

class DirectorAgent:
    def __init__(self, library_path):
        self.library_path = Path(library_path)
        # Инициализируем нашего клиента с Retry-логикой
        try:
            self.client = GeminiClient(model_name="gemini-2.0-flash")
            self.ready = True
        except Exception as e:
            logger.error(f"❌ Director Agent failed to init Gemini: {e}")
            self.ready = False

    def get_available_characters(self, source_movies):
        """
        Собирает список всех доступных персонажей из указанных фильмов.
        """
        all_chars = set()
        for movie in source_movies:
            map_path = self.library_path / movie / "character_map.json"
            if map_path.exists():
                with open(map_path, 'r') as f:
                    data = json.load(f)
                    # data = {"person_0": "Mikael", ...}
                    names = [n for n in data.values() if n != "Unknown"]
                    all_chars.update(names)
        
        return list(all_chars)

    def process(self, transcript_path, output_path, sources):
        if not self.ready:
            return

        transcript_path = Path(transcript_path)
        with open(transcript_path, 'r') as f:
            batches = json.load(f)

        # 1. Узнаем, кто у нас есть в касте
        available_chars = self.get_available_characters(sources)
        logger.info(f"🎭 Director knows these actors: {available_chars}")

        visual_script = []
        
        logger.info(f"🎬 Director is visualizing {len(batches)} batches...")

        for batch in batches:
            batch_id = batch['batch_id']
            segments = batch['segments'] # Список фраз в этом батче
            context_text = batch['context_text']

            # 2. Формируем Промпт
            prompt = f"""
            Role: Expert Film Editor & Director.
            Task: Create a visual shot list for a video essay based on the provided text segments.
            
            Context: The video is about the movie(s) containing these characters: {available_chars}.
            
            Input Text Block: "{context_text}"
            
            Segments to visualize:
            {json.dumps(segments, indent=2)}
            
            Instructions:
            1. For EACH segment, define the best visual shot.
            2. **Visual Query**: Describe the visual content for CLIP search (e.g., "man typing on laptop", "dark snowy street").
            3. **Shot Type**: Choose one [Close-Up, Medium Shot, Wide Angle, Extreme Close-Up]. VARY THEM! Don't use the same type 3 times in a row.
            4. **Character**: Choose a character from the list provided above IF relevant. If the text is abstract or about atmosphere, set "character": null (for B-Roll).
            5. **Mood**: One word (e.g., Tense, Calm, Dark, Happy).
            
            Output Format: Return ONLY a JSON list of objects matching the segments count.
            Example:
            [
              {{
                "segment_id": 0,
                "visual_query": "Mikael Blomkvist smoking cigarette",
                "shot_type": "Close-Up",
                "character": "Mikael Blomkvist",
                "mood": "Tense"
              }},
              ...
            ]
            """

            try:
                # Отправляем в Gemini
                response = self.client.generate_content(prompt)
                json_str = self.client.parse_json(response.text)
                shot_list = json.loads(json_str)
                
                # Валидация: проверим, что кол-во шотов совпадает с кол-вом сегментов
                # Если Gemini ошибся и вернул меньше/больше, мы просто привяжем по порядку
                for i, shot in enumerate(shot_list):
                    if i < len(segments):
                        # Сохраняем оригинальные данные сегмента (таймкоды) + визуал
                        merged = segments[i].copy()
                        merged.update(shot)
                        visual_script.append(merged)
                
                logger.info(f"✅ Batch {batch_id} visualized.")

            except Exception as e:
                logger.error(f"❌ Error directing batch {batch_id}: {e}")
                # Fallback: Если ИИ сломался, добавляем сегмент без визуала (Матчер разберется)
                for seg in segments:
                    seg["visual_query"] = "scene form movie"
                    seg["shot_type"] = "Medium Shot"
                    visual_script.append(seg)

        # 3. Сохраняем результат
        with open(output_path, 'w') as f:
            json.dump(visual_script, f, indent=2)
            
        logger.info(f"📜 Visual Script saved to {output_path}")