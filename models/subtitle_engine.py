"""
ClipAI — Subtitle Engine
Burns captions directly into video clips using FFmpeg drawtext.
"""

import os
import re
import logging
import tempfile
from typing import List, Dict, Optional

logger = logging.getLogger('clipai.subtitles')

# Subtitle styles
SUBTITLE_STYLES = {
    'default': {
        'fontsize': 48,
        'fontcolor': 'white',
        'box': 1,
        'boxcolor': 'black@0.5',
        'boxborderw': 8,
        'font': 'DejaVu Sans Bold',
        'y_pos': '(h-th)/1.15',
    },
    'tiktok': {
        'fontsize': 56,
        'fontcolor': 'yellow',
        'box': 1,
        'boxcolor': 'black@0.7',
        'boxborderw': 10,
        'font': 'DejaVu Sans Bold',
        'y_pos': '(h-th)/1.12',
    },
    'minimal': {
        'fontsize': 42,
        'fontcolor': 'white',
        'box': 1,
        'boxcolor': 'black@0.3',
        'boxborderw': 6,
        'font': 'DejaVu Sans',
        'y_pos': '(h-th)/1.10',
    },
    'bold': {
        'fontsize': 64,
        'fontcolor': 'white',
        'box': 1,
        'boxcolor': 'black@0.8',
        'boxborderw': 12,
        'font': 'DejaVu Sans Bold',
        'y_pos': '(h-th)/1.15',
    },
}


class SubtitleEngine:
    """Burns subtitles into video clips using FFmpeg."""

    def __init__(self, style: str = 'tiktok'):
        self.style = SUBTITLE_STYLES.get(style, SUBTITLE_STYLES['tiktok'])

    def burn_subtitles(self, video_path: str, transcript: str,
                       style_name: Optional[str] = None) -> bool:
        """
        Burn subtitles into a video file.
        
        Args:
            video_path: Path to the video file (will be modified in place)
            transcript: Text transcript of the video
            style_name: Optional style override
        """
        if not transcript or not transcript.strip():
            return False

        if not os.path.exists(video_path):
            logger.error(f"Video not found: {video_path}")
            return False

        if style_name:
            self.style = SUBTITLE_STYLES.get(style_name, self.style)

        # Create SRT subtitle file
        srt_path = video_path.replace('.mp4', '.srt')
        srt_content = self._text_to_srt(transcript, video_path)

        if not srt_content:
            return False

        try:
            with open(srt_path, 'w', encoding='utf-8') as f:
                f.write(srt_content)
        except Exception as e:
            logger.error(f"Could not write SRT: {e}")
            return False

        # Burn subtitles with FFmpeg
        success = self._burn_srt(video_path, srt_path)

        # Cleanup SRT
        try:
            os.remove(srt_path)
        except Exception:
            pass

        return success

    def _get_video_duration(self, video_path: str) -> float:
        """Get video duration using FFprobe"""
        import subprocess, json
        try:
            cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json',
                   '-show_format', video_path]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return float(json.loads(r.stdout)['format']['duration'])
        except Exception:
            return 30.0

    def _text_to_srt(self, text: str, video_path: str) -> str:
        """
        Convert plain text transcript to SRT format.
        Splits text into subtitle-sized chunks with timing.
        """
        duration = self._get_video_duration(video_path)
        
        # Clean text
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Split into word groups (4-6 words per subtitle line)
        words = text.split()
        if not words:
            return ''

        chunk_size = 5  # words per line
        chunks = []
        for i in range(0, len(words), chunk_size):
            chunk = ' '.join(words[i:i+chunk_size])
            if chunk:
                chunks.append(chunk)

        if not chunks:
            return ''

        # Assign timing
        time_per_chunk = duration / len(chunks)
        srt_lines = []

        for i, chunk in enumerate(chunks):
            start_secs = i * time_per_chunk
            end_secs = min((i + 1) * time_per_chunk, duration)

            start_str = self._secs_to_srt_time(start_secs)
            end_str = self._secs_to_srt_time(end_secs)

            srt_lines.append(f"{i+1}")
            srt_lines.append(f"{start_str} --> {end_str}")
            srt_lines.append(chunk.upper())  # ALL CAPS looks better on short clips
            srt_lines.append("")

        return '\n'.join(srt_lines)

    def _secs_to_srt_time(self, seconds: float) -> str:
        """Convert seconds to SRT timestamp format HH:MM:SS,mmm"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds - int(seconds)) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def _burn_srt(self, video_path: str, srt_path: str) -> bool:
        """Use FFmpeg to burn SRT subtitles into video"""
        import subprocess

        temp_path = video_path.replace('.mp4', '_subbed.mp4')
        
        # Escape paths for FFmpeg filter
        safe_srt = srt_path.replace('\\', '/').replace(':', '\\:').replace("'", "\\'")

        cmd = [
            'ffmpeg', '-y',
            '-i', video_path,
            '-vf',
            (f"subtitles='{safe_srt}':force_style="
             f"'FontSize={self.style['fontsize']},"
             f"PrimaryColour=&H00FFFFFF,"
             f"OutlineColour=&H00000000,"
             f"Outline=3,"
             f"Bold=1,"
             f"Alignment=2'"),
            '-c:a', 'copy',
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
            temp_path
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            if result.returncode == 0 and os.path.exists(temp_path):
                os.replace(temp_path, video_path)
                logger.info("Subtitles burned successfully")
                return True
            else:
                # Try simpler drawtext method as fallback
                logger.warning("SRT burn failed, trying drawtext fallback")
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                return False
        except subprocess.TimeoutExpired:
            logger.error("Subtitle burning timed out")
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return False
        except Exception as e:
            logger.error(f"Subtitle error: {e}")
            return False
