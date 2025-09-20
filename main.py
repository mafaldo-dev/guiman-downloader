# app.py
import os
import subprocess
import yt_dlp
from flask import Flask, render_template, request, jsonify, send_file
from faster_whisper import WhisperModel
import warnings
import datetime
from concurrent.futures import ThreadPoolExecutor
import imageio_ffmpeg
import librosa
from transformers import pipeline
from deepface import DeepFace
import threading
import time

warnings.filterwarnings('ignore')

# Caminho do FFmpeg
FFMPEG_BINARY = imageio_ffmpeg.get_ffmpeg_exe()

# Pipeline de sentimento offline (transformers)
sentiment_pipeline = pipeline(
    "sentiment-analysis",
    model="distilbert-base-uncased-finetuned-sst-2-english"
)

app = Flask(__name__)
app.config['DOWNLOAD_FOLDER'] = os.path.abspath('downloads')
app.config['SHORTS_FOLDER'] = os.path.abspath('shorts')

# Whisper (transcrição local)
whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")

def log(msg):
    timestamp = datetime.datetime.now().strftime('%H:%M:%S')
    print(f"[{timestamp}] {msg}")
    return f"[{timestamp}] {msg}"

def run_ffmpeg(cmd):
    try:
        subprocess.run(cmd, check=True, shell=True)
        return True
    except Exception as e:
        log(f"Erro FFmpeg: {e}")
        return False

# ------------------ Limpeza automática ------------------
def clean_old_files(folder, max_age_hours=24):
    now = time.time()
    max_age_seconds = max_age_hours * 3600
    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)
        if os.path.isfile(file_path):
            file_age = now - os.path.getmtime(file_path)
            if file_age > max_age_seconds:
                try:
                    os.remove(file_path)
                    log(f"Arquivo removido: {file_path}")
                except Exception as e:
                    log(f"Erro ao remover {file_path}: {e}")

def periodic_cleanup(interval_hours=1):
    while True:
        log("Iniciando limpeza periódica de arquivos antigos...")
        clean_old_files(app.config['DOWNLOAD_FOLDER'], max_age_hours=24)
        clean_old_files(app.config['SHORTS_FOLDER'], max_age_hours=24)
        log("Limpeza concluída. Próxima verificação em 1 hora.")
        time.sleep(interval_hours * 3600)

# Rodar limpeza em thread separada
cleanup_thread = threading.Thread(target=periodic_cleanup, daemon=True)
cleanup_thread.start()

# ------------------ Classe Shorts ------------------
class ShortsCreator:
    def __init__(self, max_workers=4):
        self.ensure_directories()
        self.max_workers = max_workers

    def ensure_directories(self):
        os.makedirs(app.config['DOWNLOAD_FOLDER'], exist_ok=True)
        os.makedirs(app.config['SHORTS_FOLDER'], exist_ok=True)

    def download_video(self, url):
        log(f"Iniciando download: {url}")
        ydl_opts = {
            'format': 'mp4[ext=mp4][height<=720]/best',
            'outtmpl': os.path.join(app.config['DOWNLOAD_FOLDER'], '%(id)s.%(ext)s'),
            'quiet': False,
            'ignoreerrors': True
        }
        if os.path.exists("cookies.txt"):
            ydl_opts['cookiefile'] = "cookies.txt"
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                video_path = os.path.abspath(ydl.prepare_filename(info))
                log(f"Download finalizado: {video_path}")
                return video_path, info
        except Exception as e:
            log(f"Erro no download: {e}")
            return None, None

    def get_transcription(self, video_path):
        log(f"Iniciando transcrição: {video_path}")
        segments, _ = whisper_model.transcribe(video_path, beam_size=5)
        timed_segments = []
        for seg in segments:
            text = seg.text.strip()
            if text:
                timed_segments.append({"start": seg.start, "end": seg.end, "text": text})
        log(f"Transcrição concluída: {len(timed_segments)} segmentos")
        return timed_segments

    def split_segments(self, timed_segments, max_duration=50):  # <=50 seg
        shorts = []
        current_start = None
        current_text = []
        last_time = None
        for seg in timed_segments:
            if current_start is None:
                current_start = seg["start"]
            current_text.append(seg["text"])
            last_time = seg["end"]
            if last_time - current_start >= max_duration:
                shorts.append({"start": current_start, "end": last_time, "text": " ".join(current_text)})
                current_start = None
                current_text = []
        if current_start and last_time:
            shorts.append({"start": current_start, "end": last_time, "text": " ".join(current_text)})
        log(f"{len(shorts)} shorts planejados")
        return shorts

    def create_short_ffmpeg(self, video_path, start_time, end_time, output_path):
        try:
            video_path = os.path.abspath(video_path)
            output_path = os.path.abspath(output_path)
            ffmpeg_cmd = [
                FFMPEG_BINARY, "-y",
                "-ss", str(start_time),
                "-to", str(end_time),
                "-i", video_path,
                "-c:a", "aac",
                "-c:v", "libx264",
                "-preset", "fast",
                output_path
            ]
            if run_ffmpeg(ffmpeg_cmd):
                log(f"Short criado: {output_path}")
                return output_path
            return None
        except Exception as e:
            log(f"Erro ao criar short {output_path}: {e}")
            return None

    def generate_thumbnail_ffmpeg(self, video_path, timestamp, output_path):
        try:
            ffmpeg_cmd = [
                FFMPEG_BINARY, "-y",
                "-ss", str(timestamp),
                "-i", video_path,
                "-frames:v", "1",
                output_path
            ]
            if run_ffmpeg(ffmpeg_cmd):
                log(f"Thumbnail gerada: {output_path}")
                return output_path
            return None
        except Exception as e:
            log(f"Erro na thumbnail {output_path}: {e}")
            return None

    def create_shorts(self, video_path, shorts_segments, video_id):
        results = []
        for i, seg in enumerate(shorts_segments):
            short_file_name = f"{video_id}_short_{i}.mp4"
            thumb_file_name = f"{video_id}_thumb_{i}.jpg"
            short_file = os.path.join(app.config['SHORTS_FOLDER'], short_file_name)
            thumb_file = os.path.join(app.config['SHORTS_FOLDER'], thumb_file_name)

            created_path = self.create_short_ffmpeg(video_path, seg['start'], seg['end'], short_file)
            if created_path:
                self.generate_thumbnail_ffmpeg(video_path, seg['start'], thumb_file)
                results.append({
                    'path': f"/shorts/{short_file_name}",
                    'thumbnail': f"/thumbnails/{thumb_file_name}",
                    'start': seg['start'],
                    'end': seg['end'],
                    'text': seg['text'][:120] + "..."
                })
        return results

    def generate_transcripts_for_shorts(self, shorts):
        for short in shorts:
            short_path = os.path.join(app.config['SHORTS_FOLDER'], os.path.basename(short['path']))
            timed_segments = self.get_transcription(short_path)
            transcript_segments = []
            for seg in timed_segments:
                words = seg['text'].split()
                duration = seg['end'] - seg['start']
                word_duration = duration / max(len(words), 1)
                for i, word in enumerate(words):
                    transcript_segments.append({
                        'text': word,
                        'start': seg['start'] + i*word_duration,
                        'end': seg['start'] + (i+1)*word_duration
                    })
            short['transcript_segments'] = transcript_segments
            log(f"Transcrição gerada para {short['path']}")
        return shorts

shorts_creator = ShortsCreator(max_workers=6)

# ------------------ Classe Viral Analyzer ------------------
class ViralAnalyzer:
    def extract_audio_features(self, video_path):
        """Extrai batidas, energia e volume do áudio."""
        try:
            y, sr = librosa.load(video_path, sr=None)
            tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
            rms = librosa.feature.rms(y=y).mean()
            beat_density = len(beat_frames) / max(len(y)/sr, 1)  # beats por segundo
            return {"tempo": tempo, "rms": rms, "beat_density": beat_density}
        except:
            return {"tempo": 0, "rms": 0, "beat_density": 0}

    def analyze_sentiment(self, text):
        """Analisa sentimento do texto e converte para 0-100"""
        try:
            result = sentiment_pipeline(text[:512])[0]
            label = result['label']
            score = result['score']
            if label == 'POSITIVE':
                return score * 100
            elif label == 'NEGATIVE':
                return (1 - score) * 100
            else:  # NEUTRAL
                return 50
        except:
            return 50

    def detect_emotions(self, video_path):
        """Detecta emoções predominantes no vídeo e retorna score"""
        try:
            result = DeepFace.analyze(video_path, actions=["emotion"], enforce_detection=False)
            emotion = result[0]["dominant_emotion"].lower()
            # mapeamento para score de viralidade
            if emotion in ["happy", "surprise"]:
                return 100
            elif emotion in ["neutral"]:
                return 60
            elif emotion in ["sad", "angry", "fear"]:
                return 30
            else:
                return 50
        except:
            return 50

    def calculate_score(self, audio, sentiment_score, emotion_score):
        """Calcula score de viralidade (0 a 100) ponderado"""
        # Normaliza métricas de áudio
        tempo_score = min(max(audio['tempo']/150*100, 0), 100)      
        rms_score = min(max(audio['rms']/0.1*100, 0), 100)          
        beat_score = min(max(audio['beat_density']*100,0),100)

        audio_score = (tempo_score*0.4 + rms_score*0.3 + beat_score*0.3)

        # Média ponderada geral
        final_score = (audio_score*0.3 + sentiment_score*0.3 + emotion_score*0.4)
        return round(final_score, 1)


viral_analyzer = ViralAnalyzer()

# ------------------ Rotas Flask ------------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process_video():
    data = request.json
    url = data.get('url')
    if not url:
        return jsonify({'error': 'URL não fornecida'}), 400

    video_path, info = shorts_creator.download_video(url)
    if not video_path:
        return jsonify({'error': 'Erro ao baixar o vídeo'}), 500

    video_id = info['id']
    title = info['title']
    duration = info.get('duration', 0)

    # 1️⃣ Gerar shorts sem transcrição
    timed_segments = shorts_creator.get_transcription(video_path)
    shorts_segments = shorts_creator.split_segments(timed_segments, max_duration=50)
    generated_shorts = shorts_creator.create_shorts(video_path, shorts_segments, video_id)

    # 2️⃣ Gerar transcrição sequencial para cada short
    generated_shorts = shorts_creator.generate_transcripts_for_shorts(generated_shorts)

    # Análise de viralidade
    audio = viral_analyzer.extract_audio_features(video_path)
    sentiment = viral_analyzer.analyze_sentiment(" ".join([s['text'] for s in timed_segments]))
    emotion = viral_analyzer.detect_emotions(video_path)
    viral_score = viral_analyzer.calculate_score(audio, sentiment, emotion)

    return jsonify({ 
        'success': True, 
        'video_info': 
            {
                'title': title, 
                'duration': duration, 
                'id': video_id
            }, 
        'shorts': generated_shorts, 
        'viral_analysis': 
            { 
                'audio': audio, 
                'sentiment': sentiment, 
                'emotion': emotion, 
                'score': viral_score
            } 
    })

@app.route('/shorts/<filename>')
def serve_short(filename):
    return send_file(os.path.join(app.config['SHORTS_FOLDER'], filename))

@app.route('/thumbnails/<filename>')
def serve_thumbnail(filename):
    return send_file(os.path.join(app.config['SHORTS_FOLDER'], filename))

if __name__ == '__main__':
    log("Servidor iniciado na porta 5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
