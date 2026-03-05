# ClipAI Configuration
import os

HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", 5000))
DEBUG = os.environ.get("DEBUG", "false").lower() == "true"

UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "uploads")
CLIPS_FOLDER = os.environ.get("CLIPS_FOLDER", "clips")
LOGS_FOLDER = "logs"
MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB

DEFAULT_CLIP_DURATIONS = [15, 30, 60]
MAX_CLIPS_PER_VIDEO = 5
MIN_CLIP_SCORE = 0.35
OUTPUT_FPS = 30

WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "base")
USE_GPU = False
FALLBACK_MODE = True

ENABLE_VOICE_NARRATION = True
VOICE_LANGUAGE = "en"
ENABLE_SUBTITLES = True

ALLOWED_EXTENSIONS = {'mp4', 'mov', 'avi', 'mkv', 'webm', 'flv', 'm4v', '3gp'}
