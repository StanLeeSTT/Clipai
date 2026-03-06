"""
ClipAI — Intelligent Video Clipping Engine
Main Flask Application
"""

import os
import sys
import json
import uuid
import threading
import logging
from datetime import datetime

from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS

# Setup logging
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/clipai.log', mode='a'),
    ]
)
logger = logging.getLogger('clipai')

# Config
try:
    import config
except ImportError:
    class config:
        HOST = "0.0.0.0"
        PORT = 5000
        DEBUG = False
        UPLOAD_FOLDER = "uploads"
        CLIPS_FOLDER = "clips"
        MAX_CONTENT_LENGTH = 500 * 1024 * 1024
        DEFAULT_CLIP_DURATIONS = [15, 30, 60]
        MAX_CLIPS_PER_VIDEO = 5
        ALLOWED_EXTENSIONS = {'mp4', 'mov', 'avi', 'mkv', 'webm', 'flv', 'm4v', '3gp'}

# Import AI modules
FULL_MODE = False
try:
    from models.clip_analyzer import ClipAnalyzer
    from models.voice_engine import VoiceEngine
    from models.subtitle_engine import SubtitleEngine
    from utils.downloader import VideoDownloader
    from utils.processor import VideoProcessor
    from utils.scorer import ViralityScorer
    FULL_MODE = True
    logger.info("All AI modules loaded")
except ImportError as e:
    logger.warning(f"AI modules unavailable: {e} — running in basic mode")

app = Flask(__name__)
CORS(app)
app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_LENGTH

for d in [config.UPLOAD_FOLDER, config.CLIPS_FOLDER, 'logs']:
    os.makedirs(d, exist_ok=True)

jobs = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in config.ALLOWED_EXTENSIONS

def update_job(job_id, **kwargs):
    if job_id in jobs:
        jobs[job_id].update(kwargs)
        jobs[job_id]['updated_at'] = datetime.now().isoformat()

def get_video_duration(filepath):
    import subprocess
    try:
        cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', filepath]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            return float(json.loads(r.stdout)['format']['duration'])
    except Exception:
        pass
    try:
        from moviepy.editor import VideoFileClip
        with VideoFileClip(filepath) as c:
            return c.duration
    except Exception:
        return None

# ── Routes ────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'mode': 'full' if FULL_MODE else 'basic', 'version': '1.0.0'})

@app.route('/api/upload', methods=['POST'])
def upload_video():
    if 'video' not in request.files:
        return jsonify({'error': 'No video file provided'}), 400
    file = request.files['video']
    if not file.filename or not allowed_file(file.filename):
        return jsonify({'error': 'Invalid or unsupported file type'}), 400

    job_id = str(uuid.uuid4())[:8]
    ext = file.filename.rsplit('.', 1)[1].lower()
    filepath = os.path.join(config.UPLOAD_FOLDER, f"{job_id}.{ext}")
    file.save(filepath)

    settings = {
        'clip_durations': json.loads(request.form.get('clip_durations', '[30]')),
        'max_clips': int(request.form.get('max_clips', config.MAX_CLIPS_PER_VIDEO)),
        'add_subtitles': request.form.get('add_subtitles', 'true') == 'true',
        'add_voice': request.form.get('add_voice', 'false') == 'true',
        'orientation': request.form.get('orientation', 'vertical'),
        'transition': request.form.get('transition', 'fade'),
        'music_mood': request.form.get('music_mood', 'none'),
        'music_volume': float(request.form.get('music_volume', '0.15')),
        'voice_style': request.form.get('voice_style', 'DeepBass'),
    }

    jobs[job_id] = {
        'id': job_id, 'status': 'queued', 'source': 'upload',
        'filename': file.filename, 'filepath': filepath,
        'settings': settings, 'progress': 0, 'clips': [],
        'error': None, 'message': 'Queued for processing...',
        'created_at': datetime.now().isoformat(), 'updated_at': datetime.now().isoformat(),
    }

    t = threading.Thread(target=process_video_job, args=(job_id,))
    t.daemon = True
    t.start()
    return jsonify({'job_id': job_id, 'status': 'queued'})

@app.route('/api/download', methods=['POST'])
def download_from_url():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({'error': 'No URL provided'}), 400
    url = data['url'].strip()
    if not url.startswith(('http://', 'https://')):
        return jsonify({'error': 'Invalid URL'}), 400

    job_id = str(uuid.uuid4())[:8]
    settings = {
        'clip_durations': data.get('clip_durations', [30]),
        'max_clips': data.get('max_clips', config.MAX_CLIPS_PER_VIDEO),
        'add_subtitles': data.get('add_subtitles', True),
        'add_voice': data.get('add_voice', False),
        'orientation': data.get('orientation', 'vertical'),
        'transition': data.get('transition', 'fade'),
        'music_mood': data.get('music_mood', 'none'),
        'music_volume': data.get('music_volume', 0.15),
        'voice_style': data.get('voice_style', 'DeepBass'),
    }

    jobs[job_id] = {
        'id': job_id, 'status': 'downloading', 'source': 'url',
        'url': url, 'filepath': None, 'settings': settings,
        'progress': 5, 'clips': [], 'error': None,
        'message': 'Downloading video...', 
        'created_at': datetime.now().isoformat(), 'updated_at': datetime.now().isoformat(),
    }

    t = threading.Thread(target=download_and_process_job, args=(job_id, url))
    t.daemon = True
    t.start()
    return jsonify({'job_id': job_id, 'status': 'downloading'})

@app.route('/api/job/<job_id>')
def get_job_status(job_id):
    if job_id not in jobs:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify(jobs[job_id])

@app.route('/api/jobs')
def list_jobs():
    return jsonify(sorted(jobs.values(), key=lambda x: x['created_at'], reverse=True)[:50])

@app.route('/api/delete/<job_id>', methods=['DELETE'])
def delete_job(job_id):
    if job_id not in jobs:
        return jsonify({'error': 'Job not found'}), 404
    job = jobs[job_id]
    try:
        if job.get('filepath') and os.path.exists(job['filepath']):
            os.remove(job['filepath'])
        for clip in job.get('clips', []):
            p = os.path.join(config.CLIPS_FOLDER, clip['filename'])
            if os.path.exists(p):
                os.remove(p)
    except Exception as e:
        logger.warning(f"Cleanup error: {e}")
    del jobs[job_id]
    return jsonify({'status': 'deleted'})

@app.route('/clips/<path:filename>')
def serve_clip(filename):
    return send_from_directory(config.CLIPS_FOLDER, filename)

# ── Background Jobs ───────────────────────────────────────

def download_and_process_job(job_id, url):
    try:
        update_job(job_id, status='downloading', progress=5, message='Downloading video...')
        if FULL_MODE:
            dl = VideoDownloader()
            filepath = dl.download(url, output_dir=config.UPLOAD_FOLDER, job_id=job_id,
                                   progress_callback=lambda p: update_job(job_id, progress=5+int(p*0.3)))
        else:
            filepath = basic_download(url, job_id)

        if not filepath or not os.path.exists(filepath):
            update_job(job_id, status='error', error='Download failed. Check the URL and try again.')
            return

        update_job(job_id, filepath=filepath, status='analyzing', progress=35)
        process_video_job(job_id)
    except Exception as e:
        logger.error(f"Download job {job_id}: {e}")
        update_job(job_id, status='error', error=str(e))

def basic_download(url, job_id):
    import subprocess
    output = os.path.join(config.UPLOAD_FOLDER, f"{job_id}.%(ext)s")
    cmd = ['yt-dlp', '--format', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
           '--output', output, '--no-playlist', url]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise Exception(f"yt-dlp failed: {r.stderr[:300]}")
    for f in os.listdir(config.UPLOAD_FOLDER):
        if f.startswith(job_id):
            return os.path.join(config.UPLOAD_FOLDER, f)
    raise Exception("Downloaded file not found")

def process_video_job(job_id):
    job = jobs.get(job_id)
    if not job:
        return
    try:
        if FULL_MODE:
            _process_full(job_id, job['filepath'], job['settings'])
        else:
            _process_basic(job_id, job['filepath'], job['settings'])
    except Exception as e:
        logger.error(f"Processing {job_id}: {e}", exc_info=True)
        update_job(job_id, status='error', error=str(e))

def _process_full(job_id, filepath, settings):
    update_job(job_id, status='analyzing', progress=40, message='Transcribing with Whisper AI...')
    analyzer = ClipAnalyzer()
    segments = analyzer.analyze(filepath,
        progress_callback=lambda p: update_job(job_id, progress=40+int(p*0.2)))

    update_job(job_id, status='scoring', progress=60, message='Calculating virality scores...')
    scorer = ViralityScorer()
    top = scorer.score_segments(segments, filepath)[:settings.get('max_clips', 5)]

    update_job(job_id, status='clipping', progress=65, message='Cutting clips...')
    processor = VideoProcessor()
    clips = []

    for i, seg in enumerate(top):
        if jobs[job_id]['status'] == 'cancelled':
            break
        p = 65 + int((i / len(top)) * 25)
        update_job(job_id, progress=p, message=f'Clip {i+1}/{len(top)}: cutting & enhancing...')

        fname = f"{job_id}_clip{i+1}_{int(seg['start'])}s.mp4"
        cpath = os.path.join(config.CLIPS_FOLDER, fname)
        ok = processor.cut_clip(
            filepath, cpath, seg['start'], seg['end'],
            orientation=settings.get('orientation', 'vertical'),
            transition=settings.get('transition', 'fade'),
            music_mood=settings.get('music_mood', 'none'),
            music_volume=settings.get('music_volume', 0.15),
        )
        if ok:
            if settings.get('add_subtitles') and seg.get('transcript'):
                SubtitleEngine().burn_subtitles(cpath, seg['transcript'])
            if settings.get('add_voice'):
                VoiceEngine().add_narration(cpath, seg.get('summary', ''), video_content=seg, voice_name=settings.get('voice_style', 'DeepBass'))

            clips.append({
                'filename': fname, 'url': f'/clips/{fname}',
                'clip_number': i+1, 'start': round(seg['start'], 1),
                'end': round(seg['end'], 1), 'duration': round(seg['end']-seg['start'], 1),
                'score': round(seg.get('score', 0.5), 2),
                'transcript': seg.get('transcript', ''),
                'summary': seg.get('summary', ''),
                'file_size': os.path.getsize(cpath) if os.path.exists(cpath) else 0,
                'voice': seg.get('voice_name'),
            })

    update_job(job_id, status='done', progress=100, clips=clips, message=f'{len(clips)} clips ready!')

def _process_basic(job_id, filepath, settings):
    import subprocess
    update_job(job_id, status='analyzing', progress=45, message='Analyzing video...')
    duration = get_video_duration(filepath)
    if not duration:
        update_job(job_id, status='error', error='Could not read video. Is FFmpeg installed?')
        return

    max_clips = settings.get('max_clips', 5)
    clip_dur = settings.get('clip_durations', [30])[0]
    margin = duration * 0.1
    usable = duration - 2*margin

    if usable < clip_dur:
        starts = [margin]
    else:
        step = usable / max_clips
        starts = [margin + i*step for i in range(max_clips)]

    orient = settings.get('orientation', 'vertical')
    vf = ("scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2"
          if orient == 'vertical' else
          "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2")

    clips = []
    for i, start in enumerate(starts):
        if jobs[job_id]['status'] == 'cancelled':
            break
        end = min(start + clip_dur, duration - 1)
        if end - start < 5:
            continue
        p = 55 + int((i / len(starts)) * 35)
        update_job(job_id, progress=p, message=f'Cutting clip {i+1}/{len(starts)}...')

        fname = f"{job_id}_clip{i+1}_{int(start)}s.mp4"
        cpath = os.path.join(config.CLIPS_FOLDER, fname)
        cmd = ['ffmpeg', '-y', '-ss', str(start), '-i', filepath,
               '-t', str(end-start), '-vf', vf,
               '-c:v', 'libx264', '-preset', 'fast', '-crf', '22',
               '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', cpath]
        r = subprocess.run(cmd, capture_output=True, timeout=120)
        if r.returncode == 0 and os.path.exists(cpath):
            clips.append({
                'filename': fname, 'url': f'/clips/{fname}',
                'clip_number': i+1, 'start': round(start,1), 'end': round(end,1),
                'duration': round(end-start,1), 'score': round(0.5+0.3*(i==0), 2),
                'transcript': '', 'summary': f'Clip {i+1} ({int(start)}s–{int(end)}s)',
                'file_size': os.path.getsize(cpath),
            })

    if clips:
        update_job(job_id, status='done', progress=100, clips=clips, message=f'{len(clips)} clips ready!')
    else:
        update_job(job_id, status='error', error='No clips generated. Ensure FFmpeg is installed: pkg install ffmpeg')

if __name__ == '__main__':
    logger.info("ClipAI starting...")
    logger.info(f"Mode: {'Full AI' if FULL_MODE else 'Basic (FFmpeg)'}")
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG, threaded=True)
