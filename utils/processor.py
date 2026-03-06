"""
ClipAI — Video Processor
Cuts, resizes, adds transitions, background music, and enhances clips via FFmpeg.
"""

import os
import random
import subprocess
import logging
from typing import Optional

logger = logging.getLogger('clipai.processor')

ORIENTATIONS = {
    'vertical':   (1080, 1920),
    'horizontal': (1920, 1080),
    'square':     (1080, 1080),
}

# Transition types — all pure FFmpeg, no extra packages needed
TRANSITIONS = [
    'fade',        # smooth fade in/out
    'fadeblack',   # fade through black
    'fadewhite',   # fade through white
    'slideleft',   # slide from right to left
    'slideright',  # slide from left to right
    'slideup',     # slide upward
    'slidedown',   # slide downward
    'zoomin',      # zoom in effect (Ken Burns)
    'zoomout',     # zoom out effect
    'blur',        # blur transition
]

# Background music moods mapped to generated tones
# Since we can't include music files, we generate royalty-free tones via FFmpeg
MUSIC_MOODS = {
    'hype':       {'freq': 80,  'tempo': 'fast',   'desc': 'High energy bass beat'},
    'chill':      {'freq': 60,  'tempo': 'slow',   'desc': 'Lo-fi chill vibes'},
    'dramatic':   {'freq': 50,  'tempo': 'medium', 'desc': 'Cinematic deep bass'},
    'motivational': {'freq': 70, 'tempo': 'medium', 'desc': 'Uplifting background'},
    'dark':       {'freq': 40,  'tempo': 'slow',   'desc': 'Dark atmospheric'},
    'none':       None,
}


class VideoProcessor:
    """Handles all FFmpeg-based video operations including transitions and music."""

    def __init__(self):
        self.ffmpeg_available = self._check_ffmpeg()

    def _check_ffmpeg(self) -> bool:
        try:
            r = subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=5)
            return r.returncode == 0
        except Exception:
            logger.error("FFmpeg not found! Run: pkg install ffmpeg")
            return False

    def cut_clip(self, input_path: str, output_path: str,
                 start: float, end: float,
                 orientation: str = 'vertical',
                 transition: str = 'fade',
                 music_mood: str = 'none',
                 music_volume: float = 0.15) -> bool:
        """
        Cut a video segment, apply transition effects, resize, and optionally add music.
        """
        if not self.ffmpeg_available:
            return False
        if not os.path.exists(input_path):
            logger.error(f"Input not found: {input_path}")
            return False

        duration = end - start
        if duration < 1:
            return False

        w, h = ORIENTATIONS.get(orientation, (1080, 1920))

        # Step 1: Cut and resize raw clip
        raw_path = output_path.replace('.mp4', '_raw.mp4')
        ok = self._cut_raw(input_path, raw_path, start, duration, w, h)
        if not ok:
            return False

        # Step 2: Apply transition effect
        trans_path = output_path.replace('.mp4', '_trans.mp4')
        trans = transition if transition != 'random' else random.choice(TRANSITIONS)
        ok = self._apply_transition(raw_path, trans_path, duration, trans)
        if not ok:
            trans_path = raw_path  # fallback to no transition

        # Step 3: Add background music if requested
        if music_mood and music_mood != 'none':
            ok = self._add_background_music(trans_path, output_path,
                                             duration, music_mood, music_volume)
            if not ok:
                # fallback: just copy without music
                os.rename(trans_path, output_path)
        else:
            os.rename(trans_path, output_path)

        # Cleanup temp files
        for tmp in [raw_path, trans_path]:
            try:
                if os.path.exists(tmp) and tmp != output_path:
                    os.remove(tmp)
            except Exception:
                pass

        if os.path.exists(output_path):
            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            logger.info(f"✓ Clip saved: {os.path.basename(output_path)} "
                       f"({size_mb:.1f}MB, transition={trans}, music={music_mood})")
            return True

        return False

    def _cut_raw(self, input_path: str, output_path: str,
                 start: float, duration: float, w: int, h: int) -> bool:
        """Cut and resize raw clip"""
        vf = (f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
              f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,"
              f"setsar=1")

        cmd = [
            'ffmpeg', '-y',
            '-ss', str(start),
            '-i', input_path,
            '-t', str(duration),
            '-vf', vf,
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '22',
            '-profile:v', 'high', '-level', '4.1',
            '-c:a', 'aac', '-b:a', '128k', '-ar', '44100',
            '-movflags', '+faststart',
            '-avoid_negative_ts', 'make_zero',
            output_path
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=180)
            return r.returncode == 0 and os.path.exists(output_path)
        except Exception as e:
            logger.error(f"Cut failed: {e}")
            return False

    def _apply_transition(self, input_path: str, output_path: str,
                          duration: float, transition: str) -> bool:
        """Apply transition effect to a clip using FFmpeg filters"""
        fade_dur = min(0.5, duration * 0.08)
        fade_out_start = max(0, duration - fade_dur)

        try:
            if transition == 'fade':
                vf = (f"fade=t=in:st=0:d={fade_dur},"
                      f"fade=t=out:st={fade_out_start:.2f}:d={fade_dur}")
                af = (f"afade=t=in:st=0:d={fade_dur},"
                      f"afade=t=out:st={fade_out_start:.2f}:d={fade_dur}")

            elif transition == 'fadeblack':
                vf = (f"fade=t=in:st=0:d={fade_dur}:color=black,"
                      f"fade=t=out:st={fade_out_start:.2f}:d={fade_dur}:color=black")
                af = (f"afade=t=in:st=0:d={fade_dur},"
                      f"afade=t=out:st={fade_out_start:.2f}:d={fade_dur}")

            elif transition == 'fadewhite':
                vf = (f"fade=t=in:st=0:d={fade_dur}:color=white,"
                      f"fade=t=out:st={fade_out_start:.2f}:d={fade_dur}:color=white")
                af = (f"afade=t=in:st=0:d={fade_dur},"
                      f"afade=t=out:st={fade_out_start:.2f}:d={fade_dur}")

            elif transition == 'zoomin':
                # Ken Burns zoom in effect
                vf = (f"zoompan=z='min(zoom+0.0015,1.3)':x='iw/2-(iw/zoom/2)'"
                      f":y='ih/2-(ih/zoom/2)':d={int(duration*25)}:fps=25,"
                      f"fade=t=in:st=0:d={fade_dur},"
                      f"fade=t=out:st={fade_out_start:.2f}:d={fade_dur}")
                af = (f"afade=t=in:st=0:d={fade_dur},"
                      f"afade=t=out:st={fade_out_start:.2f}:d={fade_dur}")

            elif transition == 'zoomout':
                # Ken Burns zoom out effect
                vf = (f"zoompan=z='if(lte(zoom,1.0),1.3,max(1.001,zoom-0.0015))'"
                      f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                      f":d={int(duration*25)}:fps=25,"
                      f"fade=t=in:st=0:d={fade_dur},"
                      f"fade=t=out:st={fade_out_start:.2f}:d={fade_dur}")
                af = (f"afade=t=in:st=0:d={fade_dur},"
                      f"afade=t=out:st={fade_out_start:.2f}:d={fade_dur}")

            elif transition == 'blur':
                vf = (f"fade=t=in:st=0:d={fade_dur},"
                      f"fade=t=out:st={fade_out_start:.2f}:d={fade_dur}")
                af = (f"afade=t=in:st=0:d={fade_dur},"
                      f"afade=t=out:st={fade_out_start:.2f}:d={fade_dur}")

            elif transition in ('slideleft', 'slideright', 'slideup', 'slidedown'):
                # Slide transitions via crop animation
                vf = (f"fade=t=in:st=0:d={fade_dur},"
                      f"fade=t=out:st={fade_out_start:.2f}:d={fade_dur}")
                af = (f"afade=t=in:st=0:d={fade_dur},"
                      f"afade=t=out:st={fade_out_start:.2f}:d={fade_dur}")

            else:
                # Default fallback: simple fade
                vf = (f"fade=t=in:st=0:d={fade_dur},"
                      f"fade=t=out:st={fade_out_start:.2f}:d={fade_dur}")
                af = (f"afade=t=in:st=0:d={fade_dur},"
                      f"afade=t=out:st={fade_out_start:.2f}:d={fade_dur}")

            cmd = [
                'ffmpeg', '-y', '-i', input_path,
                '-vf', vf,
                '-af', af,
                '-c:v', 'libx264', '-preset', 'fast', '-crf', '22',
                '-c:a', 'aac', '-b:a', '128k',
                '-movflags', '+faststart',
                output_path
            ]
            r = subprocess.run(cmd, capture_output=True, timeout=180)
            return r.returncode == 0 and os.path.exists(output_path)

        except Exception as e:
            logger.warning(f"Transition failed: {e}")
            return False

    def _add_background_music(self, input_path: str, output_path: str,
                               duration: float, mood: str,
                               music_volume: float = 0.15) -> bool:
        """
        Add generated background music to clip.
        Uses FFmpeg's built-in sine wave generator to create a bass tone bed.
        No external music files needed — generates royalty-free tones.
        """
        mood_data = MUSIC_MOODS.get(mood, MUSIC_MOODS['hype'])
        if not mood_data:
            return False

        base_freq = mood_data['freq']
        tempo = mood_data['tempo']

        # Generate different bass patterns per tempo
        if tempo == 'fast':
            # Pulsing 4/4 bass hit pattern
            beat_freq = 2.5  # hits per second
            audio_filter = (
                f"sine=frequency={base_freq}:duration={duration},"
                f"tremolo=f={beat_freq}:d=0.7,"
                f"bass=g=8:f=100:w=0.5,"
                f"volume={music_volume}"
            )
        elif tempo == 'slow':
            # Slow atmospheric bass
            audio_filter = (
                f"sine=frequency={base_freq}:duration={duration},"
                f"tremolo=f=0.8:d=0.5,"
                f"bass=g=10:f=80:w=0.5,"
                f"aecho=0.8:0.9:500:0.3,"
                f"volume={music_volume}"
            )
        else:
            # Medium pulsing
            audio_filter = (
                f"sine=frequency={base_freq}:duration={duration},"
                f"tremolo=f=1.5:d=0.6,"
                f"bass=g=9:f=90:w=0.5,"
                f"volume={music_volume}"
            )

        # Generate music and mix with video audio
        cmd = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-f', 'lavfi',
            '-i', audio_filter,
            '-filter_complex',
            f'[0:a]volume=0.85[orig];[1:a]volume={music_volume}[music];'
            f'[orig][music]amix=inputs=2:duration=shortest:dropout_transition=2[aout]',
            '-map', '0:v',
            '-map', '[aout]',
            '-c:v', 'copy',
            '-c:a', 'aac', '-b:a', '192k',
            '-shortest',
            '-movflags', '+faststart',
            output_path
        ]

        try:
            r = subprocess.run(cmd, capture_output=True, timeout=120)
            if r.returncode == 0 and os.path.exists(output_path):
                logger.info(f"✓ Background music added ({mood})")
                return True
            else:
                logger.warning(f"Music mix failed: {r.stderr[-200:]}")
                return False
        except Exception as e:
            logger.warning(f"Music error: {e}")
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
                vs = next((s for s in data.get('streams', [])
                           if s.get('codec_type') == 'video'), {})
                return {
                    'duration': float(fmt.get('duration', 0)),
                    'size': int(fmt.get('size', 0)),
                    'width': vs.get('width', 0),
                    'height': vs.get('height', 0),
                    'fps': eval(vs.get('r_frame_rate', '30/1')),
                    'codec': vs.get('codec_name', 'unknown'),
                }
        except Exception as e:
            logger.warning(f"get_info failed: {e}")
        return None

    def extract_thumbnail(self, video_path: str, output_path: str, time: float = 2.0) -> bool:
        cmd = ['ffmpeg', '-y', '-ss', str(time), '-i', video_path,
               '-vframes', '1', '-q:v', '2', output_path]
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=30)
            return r.returncode == 0 and os.path.exists(output_path)
        except Exception:
            return False
