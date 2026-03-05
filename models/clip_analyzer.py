"""
ClipAI — Clip Analyzer
Uses Whisper for transcription + AI scoring to find the best moments
"""

import os
import json
import logging
import re
from typing import List, Dict, Optional, Callable

logger = logging.getLogger('clipai.analyzer')

# High-engagement keyword patterns
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


class ClipAnalyzer:
    """
    AI-powered video analysis engine.
    Transcribes audio, detects scene changes, and scores segments.
    """

    def __init__(self):
        self.whisper_model = None
        self.model_size = os.environ.get('WHISPER_MODEL', 'base')
        self._load_whisper()

    def _load_whisper(self):
        try:
            import whisper
            logger.info(f"Loading Whisper {self.model_size} model...")
            self.whisper_model = whisper.load_model(self.model_size)
            logger.info("Whisper loaded")
        except ImportError:
            logger.warning("openai-whisper not installed — using basic audio analysis")
        except Exception as e:
            logger.warning(f"Whisper failed to load: {e}")

    def analyze(self, filepath: str, progress_callback: Optional[Callable] = None) -> List[Dict]:
        """
        Analyze video and return scored segments.
        Returns list of: {start, end, transcript, score, keywords, summary}
        """
        if progress_callback:
            progress_callback(0.05)

        # Step 1: Transcribe audio
        transcript_data = self._transcribe(filepath, progress_callback)

        if progress_callback:
            progress_callback(0.6)

        # Step 2: Score and segment
        segments = self._build_segments(transcript_data, filepath)

        if progress_callback:
            progress_callback(0.9)

        logger.info(f"Found {len(segments)} candidate segments")
        return segments

    def _transcribe(self, filepath: str, progress_cb=None) -> Dict:
        """Transcribe audio using Whisper"""
        if self.whisper_model:
            try:
                logger.info("Transcribing audio...")
                result = self.whisper_model.transcribe(
                    filepath,
                    task='transcribe',
                    word_timestamps=True,
                    verbose=False,
                )
                return result
            except Exception as e:
                logger.warning(f"Whisper transcription failed: {e}")

        # Fallback: return empty transcription
        return {'segments': [], 'text': ''}

    def _build_segments(self, transcript_data: Dict, filepath: str) -> List[Dict]:
        """
        Build clip segments from transcript data.
        Groups whisper segments into clips of varying lengths.
        """
        raw_segments = transcript_data.get('segments', [])

        if not raw_segments:
            return self._build_segments_no_transcript(filepath)

        segments = []
        target_lengths = [15, 30, 60]  # seconds

        for tlen in target_lengths:
            clips = self._group_into_clips(raw_segments, tlen)
            for clip in clips:
                score = self._score_segment(clip['text'], clip['end'] - clip['start'])
                clip['score'] = score
                clip['target_duration'] = tlen
                segments.append(clip)

        # Deduplicate overlapping segments (keep higher scores)
        segments = self._deduplicate(segments)
        return sorted(segments, key=lambda x: x['score'], reverse=True)

    def _group_into_clips(self, raw_segs: List[Dict], target_len: float) -> List[Dict]:
        """Group transcript segments into clips of ~target_len seconds"""
        clips = []
        i = 0
        while i < len(raw_segs):
            start_time = raw_segs[i]['start']
            clip_text = []
            j = i
            while j < len(raw_segs):
                seg = raw_segs[j]
                clip_text.append(seg['text'].strip())
                current_duration = seg['end'] - start_time
                if current_duration >= target_len:
                    break
                j += 1

            end_time = raw_segs[min(j, len(raw_segs)-1)]['end']
            text = ' '.join(clip_text).strip()

            if text and (end_time - start_time) >= 5:
                clips.append({
                    'start': start_time,
                    'end': end_time,
                    'text': text,
                    'transcript': text,
                    'summary': self._summarize(text),
                    'word_count': len(text.split()),
                })

            step = max(1, j - i - 2)  # Sliding window with overlap
            i += step

        return clips

    def _build_segments_no_transcript(self, filepath: str) -> List[Dict]:
        """Fallback segment builder using video duration only"""
        try:
            import subprocess, json
            cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json',
                   '-show_format', '-show_streams', filepath]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            data = json.loads(r.stdout)
            duration = float(data['format']['duration'])
        except Exception:
            duration = 120.0  # assume 2 min

        segments = []
        for target in [15, 30, 60]:
            if duration < target + 5:
                continue
            margin = duration * 0.1
            usable = duration - 2*margin
            count = max(1, int(usable / target))
            for i in range(count):
                start = margin + i * (usable / count)
                end = min(start + target, duration - 1)
                if end - start < 5:
                    continue
                segments.append({
                    'start': start, 'end': end,
                    'text': '', 'transcript': '',
                    'summary': f'Segment at {int(start)}s',
                    'score': 0.5 - (0.1 * i),  # first segments score higher
                    'target_duration': target,
                })

        return segments

    def _score_segment(self, text: str, duration: float) -> float:
        """Score a text segment for virality/engagement potential"""
        if not text:
            return 0.3

        score = 0.4  # Base score
        text_lower = text.lower()
        words = text.split()
        word_count = len(words)

        # Hook keywords boost
        hook_count = 0
        for pattern in HOOK_PATTERNS:
            matches = len(re.findall(pattern, text_lower))
            hook_count += matches
        score += min(0.25, hook_count * 0.05)

        # Penalize excessive fillers
        filler_count = sum(len(re.findall(p, text_lower)) for p in FILLER_PATTERNS)
        filler_ratio = filler_count / max(1, word_count)
        score -= min(0.15, filler_ratio * 0.5)

        # Speaking pace score (ideal: 120-180 words/min)
        if duration > 0:
            wpm = (word_count / duration) * 60
            if 120 <= wpm <= 180:
                score += 0.1
            elif wpm > 200:
                score -= 0.05  # too fast

        # Sentence variety (questions, exclamations)
        if '?' in text:
            score += 0.05
        if '!' in text:
            score += 0.03

        # Penalize very short or very long text
        if word_count < 10:
            score -= 0.1
        elif word_count > 250:
            score -= 0.05

        # Emotional words
        emotional = ['love', 'hate', 'fear', 'excited', 'angry', 'happy', 'sad',
                     'amazing', 'terrible', 'best', 'worst', 'perfect', 'horrible']
        for word in emotional:
            if word in text_lower:
                score += 0.02

        return min(1.0, max(0.0, score))

    def _summarize(self, text: str) -> str:
        """Create a short summary of the segment"""
        words = text.split()
        if len(words) <= 15:
            return text
        # Take first sentence or first 15 words
        sentences = text.split('.')
        if sentences and len(sentences[0].split()) >= 5:
            return sentences[0].strip()[:100]
        return ' '.join(words[:15]) + '...'

    def _deduplicate(self, segments: List[Dict]) -> List[Dict]:
        """Remove heavily overlapping segments, keeping higher-scored ones"""
        if not segments:
            return segments
        
        sorted_segs = sorted(segments, key=lambda x: x.get('score', 0), reverse=True)
        kept = []
        
        for seg in sorted_segs:
            overlap = False
            for k in kept:
                # Check if >50% overlap
                overlap_start = max(seg['start'], k['start'])
                overlap_end = min(seg['end'], k['end'])
                if overlap_end > overlap_start:
                    overlap_duration = overlap_end - overlap_start
                    seg_duration = seg['end'] - seg['start']
                    if overlap_duration / seg_duration > 0.5:
                        overlap = True
                        break
            if not overlap:
                kept.append(seg)

        return kept
