"""
ClipAI — Virality Scorer
Multi-factor scoring engine to rank clip segments by engagement potential
"""

import re
import logging
import math
from typing import List, Dict

logger = logging.getLogger('clipai.scorer')


class ViralityScorer:
    """
    Scores video segments for viral/engagement potential using:
    - Transcript analysis (keywords, emotional language, hooks)
    - Pacing (speech rate, pauses)
    - Structural position (beginnings are often stronger)
    - Duration optimization (30s sweet spot for most platforms)
    """

    # Platform-optimized duration sweet spots
    DURATION_SCORES = {
        (0, 10): 0.3,     # Too short
        (10, 20): 0.7,    # TikTok ideal
        (20, 45): 1.0,    # Universal sweet spot
        (45, 75): 0.85,   # Instagram Reels / YouTube Shorts
        (75, 120): 0.65,  # Longer short-form
        (120, 999): 0.4,  # Too long for viral
    }

    VIRAL_HOOKS = [
        'wait for it', 'you won\'t believe', 'this changed', 'the secret',
        'nobody tells you', 'stop doing this', 'the truth about',
        'here\'s why', 'this is why', 'the real reason', 'i was wrong',
        'actually works', 'proven', 'game changer', 'life hack',
        'before you', 'if you want', 'most people don\'t',
        '3 things', '5 ways', 'number one', 'first thing',
    ]

    STORY_MARKERS = [
        'so i was', 'and then', 'all of a sudden', 'out of nowhere',
        'the moment', 'that\'s when', 'i realized', 'i found out',
        'turns out', 'what happened was',
    ]

    CTA_PATTERNS = [
        r'\b(follow|subscribe|like|share|comment|watch|click|check|go to|visit)\b',
        r'\b(let me know|tell me|thoughts|agree|disagree)\b',
    ]

    def score_segments(self, segments: List[Dict], filepath: str = None) -> List[Dict]:
        """
        Score and sort segments by virality potential.
        Returns sorted list with scores added to each segment.
        """
        if not segments:
            return []

        for seg in segments:
            seg['score'] = self._compute_score(seg, len(segments))

        scored = sorted(segments, key=lambda x: x['score'], reverse=True)
        
        # Log top scores
        for i, s in enumerate(scored[:3]):
            logger.info(f"Top clip #{i+1}: score={s['score']:.2f}, "
                       f"time={s['start']:.1f}s-{s['end']:.1f}s")

        return scored

    def _compute_score(self, segment: Dict, total_segments: int) -> float:
        """Compute composite virality score for a segment"""
        scores = {}
        
        text = segment.get('text', '') or segment.get('transcript', '')
        duration = segment.get('end', 0) - segment.get('start', 0)
        start_time = segment.get('start', 0)

        # 1. Text-based scoring (40% weight)
        scores['text'] = self._score_text(text) * 0.40

        # 2. Duration scoring (25% weight)
        scores['duration'] = self._score_duration(duration) * 0.25

        # 3. Position scoring (20% weight) — earlier segments often stronger
        scores['position'] = self._score_position(start_time, total_segments) * 0.20

        # 4. Energy/pacing scoring (15% weight)
        scores['energy'] = self._score_energy(text, duration) * 0.15

        total = sum(scores.values())
        total = min(1.0, max(0.0, total))

        segment['score_breakdown'] = {k: round(v, 3) for k, v in scores.items()}
        return round(total, 3)

    def _score_text(self, text: str) -> float:
        """Score text for engagement potential"""
        if not text or len(text.strip()) < 10:
            return 0.2

        score = 0.4
        text_lower = text.lower()
        words = text.split()
        word_count = len(words)

        # Viral hooks
        for hook in self.VIRAL_HOOKS:
            if hook in text_lower:
                score += 0.08
                break  # Only count once

        # Story markers
        for marker in self.STORY_MARKERS:
            if marker in text_lower:
                score += 0.06
                break

        # Questions (high engagement)
        question_count = text.count('?')
        score += min(0.1, question_count * 0.04)

        # Exclamations (energy)
        exclaim_count = text.count('!')
        score += min(0.06, exclaim_count * 0.02)

        # CTA patterns
        for pattern in self.CTA_PATTERNS:
            if re.search(pattern, text_lower):
                score += 0.05
                break

        # Numbers/stats (credibility)
        numbers = re.findall(r'\b\d+(?:\.\d+)?%?\b', text)
        if numbers:
            score += min(0.08, len(numbers) * 0.02)

        # Emotional intensity words
        high_emotion = ['incredible', 'insane', 'crazy', 'amazing', 'shocking',
                       'terrifying', 'hilarious', 'devastating', 'legendary',
                       'perfect', 'worst', 'best', 'never', 'always', 'every']
        emotion_count = sum(1 for w in high_emotion if w in text_lower)
        score += min(0.1, emotion_count * 0.025)

        # Penalize filler words
        fillers = ['um', 'uh', 'like', 'you know', 'basically', 'literally']
        filler_count = sum(text_lower.count(f) for f in fillers)
        filler_ratio = filler_count / max(1, word_count)
        score -= min(0.15, filler_ratio * 0.8)

        # Word count sweet spot (30-150 words ideal for <60s clips)
        if 30 <= word_count <= 150:
            score += 0.05
        elif word_count < 10:
            score -= 0.15

        return min(1.0, max(0.0, score))

    def _score_duration(self, duration: float) -> float:
        """Score based on clip duration vs platform sweet spots"""
        for (low, high), score in self.DURATION_SCORES.items():
            if low <= duration < high:
                return score
        return 0.3

    def _score_position(self, start_time: float, total_segments: int) -> float:
        """
        Earlier segments often have stronger hooks.
        But mid-video can also have great moments.
        Use a bell curve slightly weighted toward the beginning.
        """
        if total_segments <= 1:
            return 0.7

        # Normalize position 0-1
        position = start_time / max(1, total_segments * 30)  # rough estimate
        position = min(1.0, position)

        # Bell curve peaking at 15% into the video
        peak = 0.15
        width = 0.4
        score = math.exp(-((position - peak) ** 2) / (2 * width ** 2))

        return 0.5 + score * 0.5  # Range: 0.5 to 1.0

    def _score_energy(self, text: str, duration: float) -> float:
        """Score speech energy/pacing"""
        if not text or duration <= 0:
            return 0.5

        words = text.split()
        wpm = (len(words) / duration) * 60

        # Ideal WPM: 130-175 (conversational but engaging)
        if 130 <= wpm <= 175:
            return 1.0
        elif 100 <= wpm < 130:
            return 0.8
        elif 175 < wpm <= 200:
            return 0.75
        elif 80 <= wpm < 100:
            return 0.6
        elif wpm > 200:
            return 0.55  # Too fast, hard to follow
        else:
            return 0.4  # Too slow

    def explain_score(self, segment: Dict) -> str:
        """Return human-readable explanation of score"""
        score = segment.get('score', 0)
        breakdown = segment.get('score_breakdown', {})

        if score >= 0.75:
            rating = "🔥 HIGH VIRAL POTENTIAL"
        elif score >= 0.55:
            rating = "⚡ GOOD ENGAGEMENT"
        elif score >= 0.4:
            rating = "👍 MODERATE"
        else:
            rating = "📉 LOW POTENTIAL"

        return f"{rating} (score: {score:.0%})"
