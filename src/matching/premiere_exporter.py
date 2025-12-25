import json
import logging
import uuid
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

logger = logging.getLogger(__name__)

class PremiereExporter:
    def __init__(self, width=1920, height=1080, fps=24):
        self.width = width
        self.height = height
        self.fps = int(fps)
        self.timebase = int(fps)

    def _frames(self, seconds):
        return int(round(seconds * self.fps))

    def _indent(self, elem, level=0):
        i = "\n" + level * "\t"
        if len(elem):
            if not elem.text or not elem.text.strip(): elem.text = i + "\t"
            if not elem.tail or not elem.tail.strip(): elem.tail = i
            for elem in elem: self._indent(elem, level + 1)
            if not elem.tail or not elem.tail.strip(): elem.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()): elem.tail = i

    def export(self, edl_path, output_xml_path, audio_file_path):
        edl_path = Path(edl_path)
        audio_path = Path(audio_file_path).absolute()
        
        with open(edl_path, 'r') as f:
            edl = json.load(f)

        logger.info(f"🎞 Generating Safe XML (v3)...")

        # Root
        xmeml = ET.Element("xmeml", version="4")
        
        # --- SEQUENCE ---
        sequence = ET.SubElement(xmeml, "sequence")
        sequence.set("id", "sequence-1")
        ET.SubElement(sequence, "uuid").text = str(uuid.uuid4())
        ET.SubElement(sequence, "name").text = "Sculptor Pro Cut"
        
        # Рассчитываем длительность (берем максимум из видео или аудио)
        video_dur = sum(c['target_duration'] for c in edl)
        # Получаем длительность аудио (очень грубо, если librosa нет, считаем с запасом)
        # Для XML главное, чтобы duration секвенции была достаточной
        total_frames = self._frames(video_dur) + 5000 
        ET.SubElement(sequence, "duration").text = str(total_frames)

        rate = ET.SubElement(sequence, "rate")
        ET.SubElement(rate, "timebase").text = str(self.timebase)
        ET.SubElement(rate, "ntsc").text = "FALSE"

        media = ET.SubElement(sequence, "media")
        
        # ================= VIDEO TRACK =================
        video_media = ET.SubElement(media, "video")
        
        # Format Specs
        fmt = ET.SubElement(video_media, "format")
        sc = ET.SubElement(fmt, "samplecharacteristics")
        ET.SubElement(sc, "width").text = str(self.width)
        ET.SubElement(sc, "height").text = str(self.height)
        ET.SubElement(sc, "pixelaspectratio").text = "square"
        r = ET.SubElement(sc, "rate")
        ET.SubElement(r, "timebase").text = str(self.timebase)
        ET.SubElement(r, "ntsc").text = "FALSE"

        track_video = ET.SubElement(video_media, "track")

        timeline_cursor = 0
        
        for i, cut in enumerate(edl):
            clipitem = ET.SubElement(track_video, "clipitem", id=f"clipitem-video-{i}")
            ET.SubElement(clipitem, "name").text = cut['text'][:50]
            ET.SubElement(clipitem, "enabled").text = "TRUE"
            
            dur_frames = self._frames(cut['target_duration'])
            if dur_frames < 1: dur_frames = 1 # Защита от нулевых клипов
            
            ET.SubElement(clipitem, "duration").text = str(dur_frames)
            
            rate_node = ET.SubElement(clipitem, "rate")
            ET.SubElement(rate_node, "timebase").text = str(self.timebase)
            ET.SubElement(rate_node, "ntsc").text = "FALSE"

            ET.SubElement(clipitem, "start").text = str(timeline_cursor)
            ET.SubElement(clipitem, "end").text = str(timeline_cursor + dur_frames)
            
            source_in = self._frames(cut['in_point'])
            source_out = source_in + dur_frames
            ET.SubElement(clipitem, "in").text = str(source_in)
            ET.SubElement(clipitem, "out").text = str(source_out)

            # File Reference
            file_node = ET.SubElement(clipitem, "file", id=f"file-{cut['source_project_alias']}")
            
            video_path = cut.get('source_video_path')
            
            if video_path and Path(video_path).exists():
                # Преобразуем путь в file:// URL с правильным кодированием
                abs_path = Path(video_path).absolute()
                # Для Windows нужно заменить \ на /, для Unix оставляем как есть
                path_str = str(abs_path).replace('\\', '/')
                file_path_url = f"file://localhost/{urllib.parse.quote(path_str)}"
                clean_name = abs_path.name
            else:
                # Fallback: заглушка (если путь потерялся)
                clean_name = f"{cut['source_project_alias']}.mp4"
                file_path_url = f"file://localhost/PLACEHOLDER/{urllib.parse.quote(clean_name)}"
            # --- ВАЖНО: Правильное кодирование пути ---
            # Premiere падает, если в пути есть пробелы, а в pathurl их нет как %20
            # Мы ставим заглушку. Ты нажмешь Locate.
            
            ET.SubElement(file_node, "name").text = clean_name
            ET.SubElement(file_node, "pathurl").text = file_path_url

            # Tech specs video
            tc = ET.SubElement(file_node, "timecode")
            ET.SubElement(tc, "string").text = "00:00:00:00"
            ET.SubElement(tc, "frame").text = "0"
            ET.SubElement(tc, "displayformat").text = "NDF"
            rt = ET.SubElement(tc, "rate")
            ET.SubElement(rt, "timebase").text = str(self.timebase)
            ET.SubElement(rt, "ntsc").text = "FALSE"

            mf = ET.SubElement(file_node, "media")
            vf = ET.SubElement(mf, "video")
            # Premiere требует samplecharacteristics даже внутри file node
            vsc = ET.SubElement(vf, "samplecharacteristics")
            ET.SubElement(vsc, "width").text = str(self.width)
            ET.SubElement(vsc, "height").text = str(self.height)

            timeline_cursor += dur_frames

        # ================= AUDIO TRACK =================
        audio_media = ET.SubElement(media, "audio")
        track_audio = ET.SubElement(audio_media, "track")
        
        clip_audio = ET.SubElement(track_audio, "clipitem", id="clipitem-audio-main")
        ET.SubElement(clip_audio, "name").text = "VOICEOVER"
        ET.SubElement(clip_audio, "enabled").text = "TRUE"
        ET.SubElement(clip_audio, "duration").text = str(total_frames)
        
        ar = ET.SubElement(clip_audio, "rate")
        ET.SubElement(ar, "timebase").text = str(self.timebase)
        ET.SubElement(ar, "ntsc").text = "FALSE"
        
        ET.SubElement(clip_audio, "start").text = "0"
        ET.SubElement(clip_audio, "end").text = str(total_frames)
        ET.SubElement(clip_audio, "in").text = "0"
        ET.SubElement(clip_audio, "out").text = str(total_frames)

        # Audio File
        af_node = ET.SubElement(clip_audio, "file", id="file-audio-source")
        ET.SubElement(af_node, "name").text = audio_path.name
        
        # URL ENCODE ПУТИ АУДИО (Критически важно!)
        audio_url = f"file://localhost{urllib.parse.quote(str(audio_path))}"
        ET.SubElement(af_node, "pathurl").text = audio_url

        amf = ET.SubElement(af_node, "media")
        amf_a = ET.SubElement(amf, "audio")
        
        # --- ВАЖНО: Audio Tech Specs ---
        # Без depth и samplerate Premiere часто крашится при импорте
        asc = ET.SubElement(amf_a, "samplecharacteristics")
        ET.SubElement(asc, "depth").text = "16" 
        ET.SubElement(asc, "samplerate").text = "48000"
        ET.SubElement(amf_a, "channelcount").text = "2"

        # Сохранение
        self._indent(xmeml)
        tree = ET.ElementTree(xmeml)
        tree.write(output_xml_path, encoding="UTF-8", xml_declaration=True)
        
        logger.info(f"✅ Safe XML Exported: {output_xml_path}")