# 🎬 ClipAI — Intelligent Video Clipping Engine

> Turn long videos into viral short clips — powered by AI. Runs fully local on Android via Termux.

ClipAI is an open-source alternative to Opus Clip and Vizard AI that runs **entirely on your device**. No subscriptions. No cloud uploads. Just intelligent clipping.

---

## ✨ Features

- 🤖 **AI-Powered Scene Detection** — Automatically identifies the most engaging moments
- 🎙️ **Dynamic Voice Narration** — Random AI voices matched to video mood/content
- 📱 **Mobile-First Web UI** — Beautiful interface accessible from your Android browser
- 🔗 **URL + Direct Upload** — Paste YouTube/TikTok/Instagram links or upload from your phone
- ✂️ **Smart Clip Generation** — Produces multiple short clips (15s, 30s, 60s) from one video
- 📝 **Auto Subtitles** — Burns captions directly into clips
- 🎯 **Virality Scoring** — Each clip gets an engagement score
- 🌐 **Web Scraper** — Download videos from 1000+ platforms via yt-dlp
- 🏠 **100% Local** — Runs on Termux, no internet needed after setup

---

## 📱 Termux Setup (Android)

### One-Command Install

```bash
curl -sL https://raw.githubusercontent.com/Sranleestt/clipai/main/install.sh | bash
```

### Manual Setup

```bash
# 1. Clone the repo
git clone https://github.com/Stanleestt/clipai.git
cd clipai

# 2. Run the installer (handles everything)
bash install.sh

# 3. Start the server
bash start.sh
```

### Access the App

Open your Android browser and go to:
```
http://localhost:5000
```

Or from another device on the same WiFi:
```
http://YOUR_PHONE_IP:5000
```

---

## 🖥️ Desktop / Linux Setup

```bash
git clone https://github.com/Stanleestt/clipai.git
cd clipai
pip install -r requirements.txt
python app.py
```

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python + Flask |
| Video Processing | FFmpeg + MoviePy |
| AI Analysis | Transformers (DistilBERT) + Whisper |
| Video Download | yt-dlp |
| TTS Voices | pyttsx3 + gTTS |
| Frontend | Vanilla JS + CSS3 |
| Subtitles | faster-whisper |

---

## 📁 Project Structure

```
clipai/
├── app.py              # Main Flask application
├── install.sh          # Auto-installer for Termux/Linux
├── start.sh            # Quick start script
├── requirements.txt    # Python dependencies
├── models/
│   ├── clip_analyzer.py    # AI clip detection engine
│   ├── voice_engine.py     # Dynamic voice assignment
│   └── subtitle_engine.py  # Auto caption generator
├── utils/
│   ├── downloader.py       # yt-dlp video scraper
│   ├── processor.py        # FFmpeg video processor
│   └── scorer.py           # Virality scoring system
├── static/
│   ├── css/style.css       # App styles
│   └── js/app.js           # Frontend logic
└── templates/
    └── index.html          # Main web interface
```

---

## 🎯 How It Works

1. **Input** — Paste a video URL or upload a file
2. **Download** — yt-dlp scrapes the video from any platform
3. **Analyze** — Whisper transcribes audio; AI scores each segment for engagement
4. **Clip** — Top N segments are cut and exported as short-form videos
5. **Enhance** — Optional: add captions, voice narration, background music
6. **Export** — Download your clips directly from the browser

---

## 🔧 Configuration

Edit `config.py` to customize:
- Clip lengths (default: 15s, 30s, 60s)
- Number of clips per video (default: 5)
- Subtitle style and font
- Voice selection preferences
- Output resolution (default: 1080x1920 vertical)

---

## 📄 License

MIT License — free to use, modify, and distribute.

---

## 🙏 Credits

Built with FFmpeg, yt-dlp, OpenAI Whisper, and HuggingFace Transformers.
