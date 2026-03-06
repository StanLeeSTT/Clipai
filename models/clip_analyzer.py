"""
ClipAI — Clip Analyzer
Uses faster-whisper (no torch needed!) for transcription + AI scoring.
faster-whisper is faster, lighter, and works on all Android CPUs.
"""

import os
import json
import logging
import re
import subprocess
from typing import List, Dict, Optional, Callable

logger = logging.getLogger('clipai.analyzer')

HOOK_PATTERNS = [
    r'\b(secret|reveal|you won\'t believe|shocking|amazing|incredible|never|always|everyone)\b',
    r'\b(how to|tip|trick|hack|method|strategy|mistake|wrong|right way)\b',
    r'\b(actually|honestly|real talk|truth|fact|story|moment|question)\b',
    r'\b(first|last|never before|exclusive|breaking|urgent|warning)\b',
    r'\b(funny|hilarious|crazy|insane|unbelievable|legendary|epic)\b',
    r'\b(i was wrong|i learned|changed my|life|money|success|fail)\b',
]

FILLER_PATTERNS = [
    r'\b(um+|uh+|hmm+|like,? like|you know,? you know|so so|basically basically)\b',
    r'\b(err+|ahh+|uhh+)\b',
]

# Auto-detect best available whisper backend
WHISPER_BACKEND = None

def _detect_whisper():
    global WHISPER_BACKEND
    try:
        import faster_whisper
        WHISPER_BACKEND = 'faster_whisper'
        logger.info("✓ faster-whisper backend available (no torch needed)")
        return
    except ImportError:
        pass
    try:
        import whisper
        WHISPER_BACKEND = 'openai_whisper'
        logger.info("✓ openai-whisper backend available")
        return
    except ImportError:
        pass
    logger.warning("No whisper backend — using FFmpeg-only mode")

_detect_whisper()


class ClipAnalyzer:
    def __init__(self):
        self.model = None
        self.backend = WHISPER_BACKEND
        self.model_size = os.environ.get('WHISPER_MODEL', 'base')
        self._load_model()

    def _load_model(self):
        if self.backend == 'faster_whisper':
            self._load_faster_whisper()
        elif self.backend == 'openai_whisper':
            self._load_openai_whisper()

    def _load_faster_whisper(self):
        try:
            from faster_whisper import WhisperModel
            logger.info(f"Loading faster-whisper {self.model_size}...")
            self.model = WhisperModel(
                self.model_size,
                device="cpu",
                compute_type="int8",
                download_root=os.path.join("models", "weights"),
            )
            logger.info("✓ faster-whisper ready")
        except Exception as e:
            logger.error(f"faster-whisper load failed: {e}")
            self.model = None
            self.backend = None

    def _load_openai_whisper(self):
        try:
            import whisper
            logger.info(f"Loading openai-whisper {self.model_size}...")
            self.model = whisper.load_model(self.model_size)
            logger.info("✓ openai-whisper ready")
        except Exception as e:
            logger.warning(f"openai-whisper load failed: {e}")
            self.model = None
            self.backend = None

    def analyze(self, filepath: str, progress_callback: Optional[Callable] = None) -> List[Dict]:
        if progress_callback:
            progress_callback(0.05)

        if self.model and self.backend == 'faster_whisper':
            transcript_data = self._transcribe_faster(filepath)
        elif self.model and self.backend == 'openai_whisper':
            transcript_data = self._transcribe_openai(filepath)
        else:
            transcript_data = {'segments': [], 'text': ''}

        if progress_callback:
            progress_callback(0.6)

        segments = self._build_segments(transcript_data, filepath)

        if progress_callback:
            progress_callback(0.9)

        logger.info(f"Found {len(segments)} candidate segments")
        return segments

    def _transcribe_faster(self, filepath: str) -> Dict:
        try:
            logger.info("Transcribing with faster-whisper (CPU int8)...")

            # Extract 16kHz mono audio — whisper works best with this
            audio_path = os.path.join('uploads', f'_audio_{os.path.basename(filepath)}.wav')
            cmd = ['ffmpeg', '-y', '-i', filepath,
                   '-ar', '16000', '-ac', '1', '-c:a', 'pcm_s16le', audio_path]
            subprocess.run(cmd, capture_output=True, timeout=120)

            source = audio_path if os.path.exists(audio_path) else filepath

            segments_gen, info = self.model.transcribe(
                source,
                beam_size=3,
                language=None,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
                word_timestamps=True,
            )

            raw_segments = []
            for seg in segments_gen:
                raw_segments.append({
                    'start': seg.start,
                    'end': seg.end,
                    'text': seg.text.strip(),
                })

            try:
                if os.path.exists(audio_path):
                    os.remove(audio_path)
            except Exception:
                pass

            full_text = ' '.join(s['text'] for s in raw_segments)
            logger.info(f"Transcribed {len(raw_segments)} segments | lang: {info.language}")
            return {'segments': raw_segments, 'text': full_text}

        except Exception as e:
            logger.error(f"faster-whisper failed: {e}")
            return {'segments': [], 'text': ''}

    def _transcribe_openai(self, filepath: str) -> Dict:
        try:
            result = self.model.transcribe(filepath, task='transcribe',
                                           word_timestamps=True, verbose=False)
            return result
        except Exception as e:
            logger.error(f"openai-whisper failed: {e}")
            return {'segments': [], 'text': ''}

    def _build_segments(self, transcript_data: Dict, filepath: str) -> List[Dict]:
        raw_segments = transcript_data.get('segments', [])
        if not raw_segments:
            return self._build_segments_no_transcript(filepath)

        segments = []
        for tlen in [15, 30, 60]:
            clips = self._group_into_clips(raw_segments, tlen)
            for clip in clips:
                clip['score'] = self._score_segment(clip['text'], clip['end'] - clip['start'])
                clip['target_duration'] = tlen
                segments.append(clip)

        return sorted(self._deduplicate(segments), key=lambda x: x['score'], reverse=True)

    def _group_into_clips(self, raw_segs, target_len):
        clips = []
        i = 0
        while i < len(raw_segs):
            start_time = raw_segs[i]['start']
            clip_text = []
            j = i
            while j < len(raw_segs):
                seg = raw_segs[j]
                clip_text.append(seg['text'].strip())
                if seg['end'] - start_time >= target_len:
                    break
                j += 1
            end_time = raw_segs[min(j, len(raw_segs)-1)]['end']
            text = ' '.join(clip_text).strip()
            if text and (end_time - start_time) >= 5:
                clips.append({
                    'start': start_time, 'end': end_time,
                    'text': text, 'transcript': text,
                    'summary': self._summarize(text),
                    'word_count': len(text.split()),
                })
            i += max(1, j - i - 2)
        return clips

    def _build_segments_no_transcript(self, filepath):
        try:
            cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', filepath]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            duration = float(json.loads(r.stdout)['format']['duration'])
        except Exception:
            duration = 120.0

        segments = []
        for target in [15, 30, 60]:
            if duration < target + 5:
                continue
            margin = duration * 0.1
            usable = duration - 2 * margin
            count = max(1, int(usable / target))
            for i in range(count):
                start = margin + i * (usable / count)
                end = min(start + target, duration - 1)
                if end - start >= 5:
                    segments.append({
                        'start': start, 'end': end, 'text': '', 'transcript': '',
                        'summary': f'Segment at {int(start)}s',
                        'score': round(0.5 - 0.05 * i, 2), 'target_duration': target,
                    })
        return segments

    def _score_segment(self, text, duration):
        if not text:
            return 0.3
        score = 0.4
        text_lower = text.lower()
        words = text.split()
        word_count = len(words)
        hook_count = sum(len(re.findall(p, text_lower)) for p in HOOK_PATTERNS)
        score += min(0.25, hook_count * 0.05)
        filler_count = sum(len(re.findall(p, text_lower)) for p in FILLER_PATTERNS)
        score -= min(0.15, (filler_count / max(1, word_count)) * 0.5)
        if duration > 0:
            wpm = (word_count / duration) * 60
            if 120 <= wpm <= 180:
                score += 0.1
            elif wpm > 200:
                score -= 0.05
        score += min(0.1, text.count('?') * 0.04)
        score += min(0.06, text.count('!') * 0.02)
        numbers = re.findall(r'\b\d+(?:\.\d+)?%?\b', text)
        score += min(0.08, len(numbers) * 0.02)
        emotional = ['incredible','insane','crazy','amazing','shocking','hilarious',
                     'devastating','legendary','perfect','worst','best','never','always']
        score += min(0.1, sum(0.02 for w in emotional if w in text_lower))
        if 30 <= word_count <= 150:
            score += 0.05
        elif word_count < 10:
            score -= 0.15
        return round(min(1.0, max(0.0, score)), 3)

    def _summarize(self, text):
        words = text.split()
        if len(words) <= 15:
            return text
        sentences = text.split('.')
        if sentences and len(sentences[0].split()) >= 5:
            return sentences[0].strip()[:100]
        return ' '.join(words[:15]) + '...'

    def _deduplicate(self, segments):
        if not segments:
            return segments
        kept = []
        for seg in sorted(segments, key=lambda x: x.get('score', 0), reverse=True):
            overlap = any(
                (min(seg['end'], k['end']) - max(seg['start'], k['start'])) /
                max(seg['end'] - seg['start'], 0.1) > 0.5
                for k in kept
            )
            if not overlap:
                kept.append(seg)
        return kept
