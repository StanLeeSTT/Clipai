"""
ClipAI — Video Downloader
Scrapes and downloads videos from 1000+ platforms via yt-dlp
"""

import os
import logging
from typing import Optional, Callable

logger = logging.getLogger('clipai.downloader')


class VideoDownloader:
    """Downloads videos from YouTube, TikTok, Instagram, Twitter/X, and 1000+ other sites."""

    SUPPORTED_SITES = [
        'youtube.com', 'youtu.be', 'tiktok.com', 'instagram.com',
        'twitter.com', 'x.com', 'facebook.com', 'fb.watch',
        'twitch.tv', 'reddit.com', 'vimeo.com', 'dailymotion.com',
        'bilibili.com', 'rumble.com', 'odysee.com', 'streamable.com',
        'medal.tv', 'clips.twitch.tv', 'vm.tiktok.com',
    ]

    def __init__(self):
        self._check_ytdlp()

    def _check_ytdlp(self):
        try:
            import yt_dlp
            self.yt_dlp_available = True
            logger.info("yt-dlp available")
        except ImportError:
            self.yt_dlp_available = False
            logger.warning("yt-dlp not installed: pip install yt-dlp")

    def download(self, url: str, output_dir: str = 'uploads',
                 job_id: Optional[str] = None,
                 progress_callback: Optional[Callable] = None) -> Optional[str]:
        """
        Download a video from a URL.
        Returns the local filepath on success, None on failure.
        """
        os.makedirs(output_dir, exist_ok=True)
        filename_base = job_id or 'download'
        output_template = os.path.join(output_dir, f"{filename_base}.%(ext)s")

        if self.yt_dlp_available:
            return self._download_ytdlp(url, output_template, output_dir,
                                         filename_base, progress_callback)
        else:
            return self._download_subprocess(url, output_template, output_dir, filename_base)

    def _download_ytdlp(self, url: str, output_template: str,
                        output_dir: str, filename_base: str,
                        progress_callback: Optional[Callable]) -> Optional[str]:
        """Download using yt-dlp Python library"""
        import yt_dlp

        downloaded_path = [None]

        def hook(d):
            if d['status'] == 'downloading' and progress_callback:
                try:
                    pct = d.get('downloaded_bytes', 0) / max(d.get('total_bytes', 1), 1)
                    progress_callback(pct)
                except Exception:
                    pass
            elif d['status'] == 'finished':
                downloaded_path[0] = d.get('filename') or d.get('info_dict', {}).get('filepath')

        ydl_opts = {
            'format': 'bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]/best',
            'outtmpl': output_template,
            'noplaylist': True,
            'progress_hooks': [hook],
            'quiet': True,
            'no_warnings': True,
            'merge_output_format': 'mp4',
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
            # Mobile-friendly: limit resolution
            'format_sort': ['res:1080', 'ext:mp4:m4a'],
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if info:
                    # Find the downloaded file
                    filepath = self._find_downloaded_file(output_dir, filename_base)
                    if filepath:
                        logger.info(f"Downloaded: {filepath}")
                        return filepath
        except yt_dlp.utils.DownloadError as e:
            logger.error(f"yt-dlp DownloadError: {e}")
            raise Exception(f"Could not download video: {str(e)[:200]}")
        except Exception as e:
            logger.error(f"Download failed: {e}")
            raise

        return None

    def _download_subprocess(self, url: str, output_template: str,
                              output_dir: str, filename_base: str) -> Optional[str]:
        """Fallback: use yt-dlp as a subprocess"""
        import subprocess
        cmd = [
            'yt-dlp',
            '--format', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            '--output', output_template,
            '--no-playlist',
            '--merge-output-format', 'mp4',
            url
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                filepath = self._find_downloaded_file(output_dir, filename_base)
                if filepath:
                    return filepath
            else:
                raise Exception(f"yt-dlp failed: {result.stderr[:300]}")
        except subprocess.TimeoutExpired:
            raise Exception("Download timed out (5 min). Try a shorter video.")

        return None

    def _find_downloaded_file(self, output_dir: str, filename_base: str) -> Optional[str]:
        """Find the downloaded file by scanning the output directory"""
        video_exts = {'.mp4', '.mkv', '.webm', '.mov', '.avi', '.m4v'}
        for f in os.listdir(output_dir):
            if f.startswith(filename_base):
                ext = os.path.splitext(f)[1].lower()
                if ext in video_exts:
                    return os.path.join(output_dir, f)
        return None

    def get_video_info(self, url: str) -> Optional[dict]:
        """Get video metadata without downloading"""
        if not self.yt_dlp_available:
            return None
        try:
            import yt_dlp
            with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                return {
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'uploader': info.get('uploader', 'Unknown'),
                    'thumbnail': info.get('thumbnail', ''),
                    'view_count': info.get('view_count', 0),
                }
        except Exception as e:
            logger.warning(f"Could not get video info: {e}")
            return None

    @staticmethod
    def is_supported_url(url: str) -> bool:
        """Check if a URL is likely supported"""
        url_lower = url.lower()
        return any(site in url_lower for site in VideoDownloader.SUPPORTED_SITES)
