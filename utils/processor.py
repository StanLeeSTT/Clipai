"""
ClipAI — Video Processor
Cuts, resizes, and enhances video clips using FFmpeg
"""

import os
import subprocess
import logging
from typing import Optional, Tuple

logger = logging.getLogger('clipai.processor')

ORIENTATIONS = {
    'vertical':   (1080, 1920),
    'horizontal': (1920, 1080),
    'square':     (1080, 1080),
}


class VideoProcessor:
    """Handles all FFmpeg-based video operations."""

    def __init__(self):
        self.ffmpeg_available = self._check_ffmpeg()

    def _check_ffmpeg(self) -> bool:
        try:
            result = subprocess.run(['ffmpeg', '-version'],
                                    capture_output=True, timeout=5)
            return result.returncode == 0
        except Exception:
            logger.error("FFmpeg not found! Install with: pkg install ffmpeg")
            return False

    def cut_clip(self, input_path: str, output_path: str,
                 start: float, end: float,
                 orientation: str = 'vertical',
                 add_fade: bool = True) -> bool:
        """
        Cut a segment from a video and optionally resize/reframe it.
        """
        if not self.ffmpeg_available:
            logger.error("FFmpeg not available")
            return False

        if not os.path.exists(input_path):
            logger.error(f"Input file not found: {input_path}")
            return False

        duration = end - start
        if duration < 1:
            logger.warning(f"Clip too short: {duration}s")
            return False

        w, h = ORIENTATIONS.get(orientation, (1080, 1920))

        # Build video filter
        vf_parts = [
            f"scale={w}:{h}:force_original_aspect_ratio=decrease",
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black",
        ]

        # Add fade in/out
        if add_fade and duration > 2:
            fade_dur = min(0.5, duration * 0.1)
            vf_parts.append(f"fade=t=in:st=0:d={fade_dur}")
            vf_parts.append(f"fade=t=out:st={duration-fade_dur:.2f}:d={fade_dur}")

        vf = ','.join(vf_parts)

        cmd = [
            'ffmpeg', '-y',
            '-ss', str(start),
            '-i', input_path,
            '-t', str(duration),
            '-vf', vf,
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '22',
            '-profile:v', 'high',
            '-level', '4.1',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-ar', '44100',
            '-movflags', '+faststart',
            '-avoid_negative_ts', 'make_zero',
            output_path
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, timeout=180)
            if result.returncode == 0 and os.path.exists(output_path):
                size_mb = os.path.getsize(output_path) / (1024*1024)
                logger.info(f"Clip saved: {output_path} ({size_mb:.1f}MB)")
                return True
            else:
                logger.error(f"FFmpeg error: {result.stderr[-500:]}")
                return False
        except subprocess.TimeoutExpired:
            logger.error("FFmpeg timed out")
            return False
        except Exception as e:
            logger.error(f"cut_clip error: {e}")
            return False

    def get_info(self, filepath: str) -> Optional[dict]:
        """Get video metadata"""
        try:
            import json
            cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json',
                   '-show_format', '-show_streams', filepath]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if r.returncode == 0:
                data = json.loads(r.stdout)
                fmt = data.get('format', {})
                video_stream = next((s for s in data.get('streams', [])
                                    if s.get('codec_type') == 'video'), {})
                return {
                    'duration': float(fmt.get('duration', 0)),
                    'size': int(fmt.get('size', 0)),
                    'bitrate': int(fmt.get('bit_rate', 0)),
                    'width': video_stream.get('width', 0),
                    'height': video_stream.get('height', 0),
                    'fps': eval(video_stream.get('r_frame_rate', '30/1')),
                    'codec': video_stream.get('codec_name', 'unknown'),
                }
        except Exception as e:
            logger.warning(f"Could not get video info: {e}")
        return None

    def add_watermark(self, video_path: str, text: str = 'ClipAI') -> bool:
        """Add a subtle watermark to a clip"""
        if not self.ffmpeg_available:
            return False
        temp = video_path.replace('.mp4', '_wm.mp4')
        cmd = [
            'ffmpeg', '-y', '-i', video_path,
            '-vf', (f"drawtext=text='{text}':fontcolor=white@0.3:"
                    f"fontsize=24:x=w-tw-20:y=20"),
            '-c:a', 'copy',
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
            temp
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=60)
            if r.returncode == 0:
                os.replace(temp, video_path)
                return True
        except Exception as e:
            logger.warning(f"Watermark failed: {e}")
        return False

    def extract_thumbnail(self, video_path: str, output_path: str,
                          time: float = 2.0) -> bool:
        """Extract a thumbnail frame from the video"""
        cmd = [
            'ffmpeg', '-y', '-ss', str(time), '-i', video_path,
            '-vframes', '1', '-q:v', '2', output_path
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=30)
            return r.returncode == 0 and os.path.exists(output_path)
        except Exception:
            return False
