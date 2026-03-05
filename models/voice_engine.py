"""
ClipAI — Voice Engine
Assigns random AI voices per video based on content mood and generates narration.
"""

import os
import random
import logging
import tempfile
from typing import Optional, Dict

logger = logging.getLogger('clipai.voice')

# Voice profiles — each has a personality mapped to content types
VOICE_PROFILES = [
    {
        'name': 'Alex', 'gender': 'male', 'style': 'energetic',
        'tld': 'com', 'lang': 'en',
        'moods': ['action', 'sports', 'gaming', 'motivation'],
        'description': 'High energy, enthusiastic',
    },
    {
        'name': 'Maya', 'gender': 'female', 'style': 'warm',
        'tld': 'co.uk', 'lang': 'en',
        'moods': ['lifestyle', 'wellness', 'cooking', 'travel'],
        'description': 'Warm, friendly British accent',
    },
    {
        'name': 'Jordan', 'gender': 'neutral', 'style': 'casual',
        'tld': 'com.au', 'lang': 'en',
        'moods': ['comedy', 'vlog', 'daily', 'casual'],
        'description': 'Relaxed Australian accent',
    },
    {
        'name': 'Sam', 'gender': 'male', 'style': 'professional',
        'tld': 'ca', 'lang': 'en',
        'moods': ['news', 'education', 'finance', 'tech'],
        'description': 'Clear professional narrator',
    },
    {
        'name': 'Zara', 'gender': 'female', 'style': 'dramatic',
        'tld': 'co.za', 'lang': 'en',
        'moods': ['drama', 'story', 'entertainment', 'fashion'],
        'description': 'Dramatic, expressive',
    },
    {
        'name': 'Chris', 'gender': 'male', 'style': 'smooth',
        'tld': 'com', 'lang': 'en',
        'moods': ['music', 'art', 'culture', 'general'],
        'description': 'Smooth, deep voice',
    },
    {
        'name': 'Riley', 'gender': 'neutral', 'style': 'upbeat',
        'tld': 'ie', 'lang': 'en',
        'moods': ['kids', 'fun', 'party', 'celebrations'],
        'description': 'Upbeat Irish accent',
    },
    {
        'name': 'Morgan', 'gender': 'neutral', 'style': 'calm',
        'tld': 'com', 'lang': 'en',
        'moods': ['nature', 'documentary', 'science', 'history'],
        'description': 'Calm, measured narrator',
    },
]

# Keyword → mood mapping for auto-detection
MOOD_KEYWORDS = {
    'action': ['fight', 'run', 'speed', 'fast', 'quick', 'rush', 'attack', 'action'],
    'sports': ['game', 'score', 'win', 'lose', 'team', 'play', 'match', 'sport', 'goal'],
    'gaming': ['game', 'level', 'player', 'kill', 'loot', 'stream', 'epic', 'boss'],
    'motivation': ['success', 'goal', 'dream', 'hustle', 'grind', 'win', 'achieve', 'inspire'],
    'lifestyle': ['day', 'life', 'routine', 'morning', 'night', 'home', 'family'],
    'wellness': ['health', 'yoga', 'meditat', 'relax', 'stress', 'sleep', 'mental'],
    'cooking': ['food', 'cook', 'eat', 'recipe', 'ingredient', 'delicious', 'meal'],
    'travel': ['travel', 'trip', 'visit', 'country', 'city', 'explore', 'adventure'],
    'comedy': ['funny', 'laugh', 'joke', 'hilarious', 'lol', 'comedy', 'humor'],
    'tech': ['tech', 'code', 'software', 'app', 'ai', 'computer', 'digital', 'robot'],
    'education': ['learn', 'study', 'school', 'teach', 'lesson', 'understand', 'knowledge'],
    'drama': ['drama', 'story', 'shocking', 'believe', 'secret', 'reveal', 'trust'],
    'music': ['music', 'song', 'beat', 'dance', 'artist', 'sing', 'album', 'concert'],
    'finance': ['money', 'invest', 'stock', 'crypto', 'income', 'rich', 'profit', 'business'],
}


class VoiceEngine:
    """
    Assigns contextually appropriate random voices to clips
    and generates TTS narration with gTTS (online) or pyttsx3 (offline).
    """

    def __init__(self):
        self.gtts_available = self._check_gtts()
        self.pyttsx3_available = self._check_pyttsx3()

        if not self.gtts_available and not self.pyttsx3_available:
            logger.warning("No TTS engine available. Install gTTS: pip install gTTS")

    def _check_gtts(self) -> bool:
        try:
            from gtts import gTTS
            return True
        except ImportError:
            return False

    def _check_pyttsx3(self) -> bool:
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.stop()
            return True
        except Exception:
            return False

    def select_voice_for_content(self, video_content: Optional[Dict] = None) -> Dict:
        """
        Intelligently select a voice based on video content/mood.
        Falls back to random selection if mood can't be determined.
        """
        if not video_content:
            return random.choice(VOICE_PROFILES)

        text = (video_content.get('transcript', '') + ' ' +
                video_content.get('summary', '')).lower()

        # Detect mood from text
        mood_scores = {}
        for mood, keywords in MOOD_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                mood_scores[mood] = score

        if mood_scores:
            top_mood = max(mood_scores, key=mood_scores.get)
            # Find voices that match this mood
            matching = [v for v in VOICE_PROFILES if top_mood in v.get('moods', [])]
            if matching:
                voice = random.choice(matching)
                logger.info(f"Selected voice '{voice['name']}' for mood '{top_mood}'")
                return voice

        # Fallback: random voice
        voice = random.choice(VOICE_PROFILES)
        logger.info(f"Selected random voice: {voice['name']}")
        return voice

    def add_narration(self, video_path: str, text: str,
                      video_content: Optional[Dict] = None) -> bool:
        """
        Add AI voice narration to a video clip.
        Generates TTS audio and mixes it with the video.
        """
        if not text or not text.strip():
            logger.warning("No text provided for narration")
            return False

        if not os.path.exists(video_path):
            logger.error(f"Video not found: {video_path}")
            return False

        voice_profile = self.select_voice_for_content(video_content)

        # Generate TTS audio
        audio_path = video_path.replace('.mp4', '_narration.mp3')
        success = self._generate_tts(text, audio_path, voice_profile)

        if not success or not os.path.exists(audio_path):
            logger.warning("TTS generation failed")
            return False

        # Mix audio with video
        mixed = self._mix_audio(video_path, audio_path, voice_profile)

        # Cleanup temp audio
        try:
            os.remove(audio_path)
        except Exception:
            pass

        if mixed:
            # Store voice name in a metadata sidecar
            meta_path = video_path.replace('.mp4', '.voice.json')
            try:
                import json
                with open(meta_path, 'w') as f:
                    json.dump({'voice': voice_profile['name'],
                               'style': voice_profile['style']}, f)
            except Exception:
                pass

        return mixed

    def _generate_tts(self, text: str, output_path: str, voice: Dict) -> bool:
        """Generate TTS audio file"""
        # Try gTTS first (better quality, needs internet)
        if self.gtts_available:
            try:
                from gtts import gTTS
                tts = gTTS(text=text[:500], lang=voice['lang'],
                           tld=voice['tld'], slow=False)
                tts.save(output_path)
                logger.info(f"TTS generated with gTTS voice ({voice['name']})")
                return True
            except Exception as e:
                logger.warning(f"gTTS failed: {e}")

        # Fallback to pyttsx3 (offline)
        if self.pyttsx3_available:
            try:
                import pyttsx3
                engine = pyttsx3.init()
                
                # Try to select appropriate voice by gender
                voices = engine.getProperty('voices')
                if voices:
                    if voice['gender'] == 'female':
                        female_voices = [v for v in voices if 'female' in v.name.lower()
                                        or 'zira' in v.name.lower() or 'hazel' in v.name.lower()]
                        if female_voices:
                            engine.setProperty('voice', female_voices[0].id)
                    else:
                        male_voices = [v for v in voices if 'male' in v.name.lower()
                                      or 'david' in v.name.lower() or 'mark' in v.name.lower()]
                        if male_voices:
                            engine.setProperty('voice', male_voices[0].id)

                # Adjust rate based on style
                rate_map = {'energetic': 200, 'calm': 160, 'professional': 175,
                           'casual': 170, 'warm': 165, 'dramatic': 155}
                engine.setProperty('rate', rate_map.get(voice['style'], 175))
                engine.setProperty('volume', 0.9)

                engine.save_to_file(text[:500], output_path)
                engine.runAndWait()
                logger.info(f"TTS generated with pyttsx3")
                return True
            except Exception as e:
                logger.warning(f"pyttsx3 failed: {e}")

        return False

    def _mix_audio(self, video_path: str, audio_path: str, voice: Dict) -> bool:
        """Mix narration audio with existing video audio using FFmpeg"""
        import subprocess

        temp_path = video_path.replace('.mp4', '_voiced.mp4')
        
        # Mix: original audio at 30% + narration at 70%
        cmd = [
            'ffmpeg', '-y',
            '-i', video_path,
            '-i', audio_path,
            '-filter_complex',
            '[0:a]volume=0.3[orig];[1:a]volume=0.7[narr];[orig][narr]amix=inputs=2:duration=shortest[aout]',
            '-map', '0:v',
            '-map', '[aout]',
            '-c:v', 'copy',
            '-c:a', 'aac', '-b:a', '128k',
            '-shortest',
            temp_path
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, timeout=60)
            if result.returncode == 0 and os.path.exists(temp_path):
                os.replace(temp_path, video_path)
                logger.info("Voice narration mixed successfully")
                return True
            else:
                logger.warning(f"FFmpeg mix failed: {result.stderr[:200]}")
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                return False
        except Exception as e:
            logger.error(f"Audio mixing error: {e}")
            return False

    def get_available_voices(self) -> list:
        """Return list of available voice profiles"""
        return [{'name': v['name'], 'style': v['style'],
                 'gender': v['gender'], 'description': v['description']}
                for v in VOICE_PROFILES]
