import whisper
import torch
import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

class AudioProcessor:
    def __init__(self, model_size="medium"):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        if torch.backends.mps.is_available():
             self.device = "cpu" 
        
        logger.info(f"👂 Loading Whisper model ('{model_size}') on {self.device}...")
        self.model = whisper.load_model(model_size, device=self.device)

    def transcribe(self, audio_path):
        logger.info(f"🎙 Transcribing {audio_path} (word-level)...")
        result = self.model.transcribe(str(audio_path), fp16=False, task="transcribe", word_timestamps=True)
        return result['segments']

    def syntax_segmentation(self, raw_segments):
        """
        Режет по знакам препинания (.,!?:;-), но не чаще чем раз в 3 слова.
        Гарантирует GAPLESS (отсутствие дыр).
        """
        logger.info("🔧 Segmenting by Punctuation + Gapless Flow...")
        
        all_words = []
        for seg in raw_segments:
            if 'words' in seg:
                all_words.extend(seg['words'])
        
        if not all_words: return []

        new_segments = []
        current_words = []
        
        # Ищем любые знаки препинания
        punct_pattern = re.compile(r"[.,!?;:-]$")
        
        segment_start = 0.0
        
        for i, word_data in enumerate(all_words):
            current_words.append(word_data)
            word_text = word_data['word'].strip()
            
            has_punct = bool(punct_pattern.search(word_text))
            enough_words = len(current_words) >= 3
            is_last_global = (i == len(all_words) - 1)

            if (has_punct and enough_words) or is_last_global:
                
                # Gapless логика
                if is_last_global:
                    segment_end = word_data['end']
                else:
                    segment_end = all_words[i+1]['start']

                text = "".join([w['word'] for w in current_words]).strip()
                
                new_segments.append({
                    "start": segment_start,
                    "end": segment_end,
                    "duration": segment_end - segment_start,
                    "text": text
                })
                
                segment_start = segment_end
                current_words = []

        # Хвост (на случай сбоя логики)
        if current_words:
            text = "".join([w['word'] for w in current_words]).strip()
            new_segments.append({
                "start": segment_start,
                "end": current_words[-1]['end'],
                "duration": current_words[-1]['end'] - segment_start,
                "text": text
            })

        return new_segments

    def create_batches(self, segments, target_context_words=60):
        """
        Группирует сегменты в батчи.
        ВАЖНО: Закрывает батч ТОЛЬКО если последний сегмент заканчивается точкой/воскл/вопросом.
        """
        batches = []
        current_batch_segments = []
        current_word_count = 0
        batch_id = 0

        # Регулярка для "сильного" конца предложения (Sentence End)
        # Ищем . ! ? в конце строки (возможно перед кавычкой)
        sentence_end_pattern = re.compile(r"[.!?][\"']?$")

        for idx, seg in enumerate(segments):
            # Присваиваем ID сегменту глобально (важно для связки с EDL)
            seg['segment_id'] = idx
            
            # Добавляем в текущий батч
            current_batch_segments.append(seg)
            current_word_count += len(seg['text'].split())
            
            # Проверяем, является ли этот сегмент концом предложения
            text = seg['text'].strip()
            is_sentence_end = bool(sentence_end_pattern.search(text))
            
            # ЛОГИКА ЗАКРЫТИЯ БАТЧА:
            # 1. Набрали достаточно слов (target_context_words)
            # 2. И (ОБЯЗАТЕЛЬНО) текущий сегмент заканчивает предложение
            if current_word_count >= target_context_words and is_sentence_end:
                full_text = " ".join([s['text'] for s in current_batch_segments])
                batches.append({
                    "batch_id": batch_id,
                    "context_text": full_text,
                    "segments": current_batch_segments
                })
                
                batch_id += 1
                current_batch_segments = []
                current_word_count = 0
        
        # Если остались сегменты (хвост, даже если не кончается точкой)
        if current_batch_segments:
            full_text = " ".join([s['text'] for s in current_batch_segments])
            batches.append({
                "batch_id": batch_id,
                "context_text": full_text,
                "segments": current_batch_segments
            })

        return batches

    def process(self, audio_path, output_path):
        # 1. Whisper
        raw = self.transcribe(audio_path)
        
        # 2. Syntax Cut + Gapless
        optimized = self.syntax_segmentation(raw)
        
        # 3. Smart Batching (Sentence Aware)
        batches = self.create_batches(optimized)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(batches, f, indent=2, ensure_ascii=False)
            
        logger.info(f"✅ Transcript ready: {len(optimized)} segments. Syntax-aware batching applied.")
        return batches