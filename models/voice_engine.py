"""
ClipAI — Voice Engine
Deep bass male TikTok-style voice narration using gTTS + FFmpeg pitch/speed control.
No extra packages needed beyond gTTS (already installed).
"""

import os
import random
import logging
import subprocess
from typing import Optional, Dict

logger = logging.getLogger('clipai.voice')

# Voice profiles — all use gTTS + FFmpeg post-processing to shape the voice
# The deep bass TikTok voice is the DEFAULT
VOICE_PROFILES = [
    {
        'name': 'DeepBass',
        'gender': 'male',
        'style': 'deep_bass',
        'description': '🎙️ Deep bass TikTok male voice (DEFAULT)',
        'tld': 'com',
        'lang': 'en',
        'pitch': -4.0,       # semitones down = deeper
        'speed': 0.92,       # slightly slower = more authoritative
        'bass_boost': 12,    # dB bass boost
        'default': True,
        'moods': ['all'],
    },
    {
        'name': 'TikTokNarrator',
        'gender': 'male',
        'style': 'narrator',
        'description': '🎤 Classic TikTok narrator voice',
        'tld': 'com',
        'lang': 'en',
        'pitch': -2.5,
        'speed': 0.95,
        'bass_boost': 8,
        'default': False,
        'moods': ['news', 'education', 'drama', 'story'],
    },
    {
        'name': 'Hype',
        'gender': 'male',
        'style': 'energetic',
        'description': '⚡ High energy hype voice',
        'tld': 'com',
        'lang': 'en',
        'pitch': 0.0,
        'speed': 1.05,
        'bass_boost': 5,
        'default': False,
        'moods': ['sports', 'gaming', 'action', 'motivation'],
    },
    {
        'name': 'Cinema',
        'gender': 'male',
        'style': 'cinematic',
        'description': '🎬 Deep cinematic movie trailer voice',
        'tld': 'co.uk',
        'lang': 'en',
        'pitch': -6.0,       # very deep
        'speed': 0.88,       # slow and dramatic
        'bass_boost': 15,
        'default': False,
        'moods': ['drama', 'action', 'motivation'],
    },
    {
        'name': 'Smooth',
        'gender': 'male',
        'style': 'smooth',
        'description': '😎 Smooth cool voice',
        'tld': 'com.au',
        'lang': 'en',
        'pitch': -1.5,
        'speed': 0.97,
        'bass_boost': 6,
        'default': False,
        'moods': ['lifestyle', 'travel', 'music', 'fashion'],
    },
    {
        'name': 'Maya',
        'gender': 'female',
        'style': 'warm',
        'description': '💫 Warm female voice',
        'tld': 'co.uk',
        'lang': 'en',
        'pitch': 1.5,
        'speed': 0.97,
        'bass_boost': 3,
        'default': False,
        'moods': ['wellness', 'cooking', 'lifestyle'],
    },
]

# Content mood detection keywords
MOOD_KEYWORDS = {
    'sports':     ['game', 'score', 'win', 'team', 'play', 'match', 'goal', 'champion'],
    'gaming':     ['game', 'level', 'player', 'stream', 'boss', 'loot', 'epic', 'kill'],
    'motivation': ['success', 'goal', 'dream', 'hustle', 'grind', 'win', 'achieve'],
    'drama':      ['shocking', 'believe', 'secret', 'reveal', 'trust', 'story'],
    'education':  ['learn', 'study', 'teach', 'lesson', 'understand', 'knowledge', 'how to'],
    'news':       ['breaking', 'report', 'happened', 'today', 'update', 'latest'],
    'lifestyle':  ['day', 'life', 'routine', 'morning', 'home', 'family', 'food'],
    'wellness':   ['health', 'yoga', 'meditate', 'relax', 'mental', 'sleep'],
    'cooking':    ['food', 'cook', 'eat', 'recipe', 'ingredient', 'delicious'],
    'travel':     ['travel', 'trip', 'visit', 'country', 'city', 'explore'],
    'music':      ['music', 'song', 'beat', 'dance', 'artist', 'sing', 'album'],
    'fashion':    ['style', 'outfit', 'wear', 'trend', 'look', 'fashion', 'clothes'],
}


class VoiceEngine:
    """
    Generates deep bass TikTok-style voice narration.
    Uses gTTS for TTS + FFmpeg for pitch/speed/bass processing.
    The default is the deep bass male voice popular on TikTok.
    """

    def __init__(self):
        self.gtts_available = self._check_gtts()
        if not self.gtts_available:
            logger.warning("gTTS not installed: pip install gTTS")

    def _check_gtts(self) -> bool:
        try:
            from gtts import gTTS
            return True
        except ImportError:
            return False

    def select_voice(self, video_content: Optional[Dict] = None,
                     force_deep_bass: bool = True) -> Dict:
        """
        Select voice profile. Defaults to DeepBass (TikTok style).
        Set force_deep_bass=False to auto-select based on content mood.
        """
        if force_deep_bass:
            return next(v for v in VOICE_PROFILES if v['default'])

        if not video_content:
            return next(v for v in VOICE_PROFILES if v['default'])

        text = (video_content.get('transcript', '') + ' ' +
                video_content.get('summary', '')).lower()

        # Detect mood
        mood_scores = {}
        for mood, keywords in MOOD_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                mood_scores[mood] = score

        if mood_scores:
            top_mood = max(mood_scores, key=mood_scores.get)
            matching = [v for v in VOICE_PROFILES
                       if top_mood in v.get('moods', []) or 'all' in v.get('moods', [])]
            if matching:
                chosen = random.choice(matching)
                logger.info(f"Voice: {chosen['name']} for mood '{top_mood}'")
                return chosen

        return next(v for v in VOICE_PROFILES if v['default'])

    def add_narration(self, video_path: str, text: str,
                      video_content: Optional[Dict] = None,
                      voice_name: Optional[str] = None) -> bool:
        """
        Generate deep bass narration and mix into video.
        """
        if not text or not text.strip():
            return False
        if not os.path.exists(video_path):
            return False
        if not self.gtts_available:
            logger.warning("gTTS not available — skipping narration")
            return False

        # Select voice
        if voice_name:
            profile = next((v for v in VOICE_PROFILES if v['name'] == voice_name),
                          None) or self.select_voice(video_content)
        else:
            profile = self.select_voice(video_content)

        logger.info(f"Generating narration with '{profile['name']}' voice...")

        # Generate raw TTS
        raw_tts = video_path.replace('.mp4', '_tts_raw.mp3')
        processed_tts = video_path.replace('.mp4', '_tts_deep.mp3')

        # Generate TTS
        if not self._generate_tts(text, raw_tts, profile):
            return False

        # Apply deep bass processing
        if not self._process_voice(raw_tts, processed_tts, profile):
            processed_tts = raw_tts  # fallback to unprocessed

        # Mix into video
        success = self._mix_into_video(video_path, processed_tts)

        # Store voice name in clip metadata
        if success:
            try:
                import json
                meta = video_path.replace('.mp4', '.voice.json')
                with open(meta, 'w') as f:
                    json.dump({'voice': profile['name'],
                               'style': profile['style'],
                               'description': profile['description']}, f)
            except Exception:
                pass

        # Cleanup
        for f in [raw_tts, processed_tts]:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except Exception:
                pass

        return success

    def _generate_tts(self, text: str, output_path: str, profile: Dict) -> bool:
        """Generate TTS audio using gTTS"""
        try:
            from gtts import gTTS
            # Limit text length and clean it up
            clean_text = text.strip()[:600]
            tts = gTTS(
                text=clean_text,
                lang=profile['lang'],
                tld=profile['tld'],
                slow=(profile['speed'] < 0.9),
            )
            tts.save(output_path)
            logger.info(f"TTS generated: {os.path.basename(output_path)}")
            return os.path.exists(output_path)
        except Exception as e:
            logger.error(f"gTTS failed: {e}")
            return False

    def _process_voice(self, input_path: str, output_path: str,
                       profile: Dict) -> bool:
        """
        Process voice with FFmpeg to create the deep bass TikTok sound.
        Applies: pitch shift + speed + bass boost + compression + normalization
        """
        pitch = profile.get('pitch', -4.0)
        speed = profile.get('speed', 0.92)
        bass_boost = profile.get('bass_boost', 12)

        # Convert pitch semitones to FFmpeg atempo/asetrate values
        # pitch shift via sample rate manipulation
        import math
        pitch_factor = 2 ** (pitch / 12.0)
        new_rate = int(44100 * pitch_factor)

        # Build audio filter chain
        # 1. Resample to shift pitch
        # 2. Speed adjustment via atempo
        # 3. Bass boost with equalizer
        # 4. Compression to punch it up
        # 5. Normalize loudness
        filters = [
            f"asetrate={new_rate}",           # pitch shift
            f"aresample=44100",               # restore sample rate
            f"atempo={speed}",                # speed control
            f"equalizer=f=80:t=o:w=100:g={bass_boost}",   # bass boost at 80Hz
            f"equalizer=f=200:t=o:w=80:g={bass_boost//2}", # upper bass
            f"equalizer=f=3000:t=o:w=500:g=-2",            # reduce harshness
            f"acompressor=threshold=-18dB:ratio=4:attack=5:release=50:makeup=4",  # punch
            f"loudnorm=I=-14:LRA=7:TP=-1",   # TikTok loudness standard
        ]

        af = ','.join(filters)

        cmd = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-af', af,
            '-ar', '44100',
            '-b:a', '192k',
            output_path
        ]

        try:
            r = subprocess.run(cmd, capture_output=True, timeout=60)
            if r.returncode == 0 and os.path.exists(output_path):
                logger.info(f"✓ Deep bass voice processed (pitch={pitch:+.1f}, "
                           f"speed={speed}, bass=+{bass_boost}dB)")
                return True
            else:
                logger.warning(f"Voice processing failed: {r.stderr[-200:]}")
                return False
        except Exception as e:
            logger.error(f"Voice processing error: {e}")
            return False

    def _mix_into_video(self, video_path: str, audio_path: str) -> bool:
        """Mix narration audio with video, ducking original audio"""
        temp = video_path.replace('.mp4', '_narrated.mp4')

        # Duck original audio to 20% when narration plays, narration at 100%
        filter_complex = (
            '[0:a]volume=0.20[orig];'
            '[1:a]volume=1.0[narr];'
            '[orig][narr]amix=inputs=2:duration=shortest:dropout_transition=1[aout]'
        )

        cmd = [
            'ffmpeg', '-y',
            '-i', video_path,
            '-i', audio_path,
            '-filter_complex', filter_complex,
            '-map', '0:v',
            '-map', '[aout]',
            '-c:v', 'copy',
            '-c:a', 'aac', '-b:a', '192k',
            '-shortest',
            '-movflags', '+faststart',
            temp
        ]

        try:
            r = subprocess.run(cmd, capture_output=True, timeout=120)
            if r.returncode == 0 and os.path.exists(temp):
                os.replace(temp, video_path)
                logger.info("✓ Narration mixed into video")
                return True
            else:
                logger.warning(f"Mix failed: {r.stderr[-200:]}")
                if os.path.exists(temp):
                    os.remove(temp)
                return False
        except Exception as e:
            logger.error(f"Mix error: {e}")
            return False

    def get_available_voices(self) -> list:
        return [{'name': v['name'], 'style': v['style'],
                 'gender': v['gender'], 'description': v['description'],
                 'default': v.get('default', False)}
                for v in VOICE_PROFILES]
