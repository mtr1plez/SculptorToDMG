import time
import logging
import os
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable, InternalServerError

logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self, model_name="gemini-2.5-flash"):
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("❌ GOOGLE_API_KEY not found in env variables!")
            
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)

    def generate_content(self, contents, retries=5, initial_delay=2):
        """
        Обертка над generate_content с автоматическим повтором при ошибке 429.
        """
        delay = initial_delay
        
        for attempt in range(1, retries + 1):
            try:
                # Пробуем отправить запрос
                response = self.model.generate_content(contents)
                return response
            
            except (ResourceExhausted, ServiceUnavailable, InternalServerError) as e:
                logger.warning(f"⚠️ Gemini API Error ({e.code if hasattr(e, 'code') else 'Unknown'}). Retrying in {delay}s... (Attempt {attempt}/{retries})")
                time.sleep(delay)
                delay *= 2  # Экспоненциальная задержка (2, 4, 8, 16...)
            
            except Exception as e:
                # Если ошибка другая (например, плохой промпт), падаем сразу
                logger.error(f"❌ Fatal Gemini Error: {e}")
                raise e
        
        # Если попытки кончились
        raise Exception("❌ Gemini Resource Exhausted after max retries.")

    def parse_json(self, response_text):
        """Очищает ответ от markdown ```json ... ```"""
        text = response_text.replace("```json", "").replace("```", "").strip()
        return text