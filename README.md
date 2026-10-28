# TikTok-Bot – Dark Cinematic Knowledge

Vollautomatische Produktion von TikTok-Videos (1080×1920, 30 fps, H.264) mit einem einzigen Befehl:

```
python main.py
```

Der Bot sucht echte Themen, bewertet sie, schreibt ein Skript mit Hook, erzeugt Voice-over, Visuals,
Untertitel, Musik und Soundeffekte, rendert per FFmpeg und legt **MP4 + Metadaten + Caption** ab.

```
Themen finden → bewerten → bestes wählen → Skript/Hooks/Szenen (LLM, JSON-validiert)
  → Voice-over (TTS) → Visuals pro Szene → Untertitel (Wort-Timing) → Sound-Mix (Ducking)
  → FFmpeg-Rendering (Zoom, Übergänge, Grading) → output/finished/2026-10-28_001_dark-cinematic-knowledge.mp4
```

---

## 1. Voraussetzungen

| Was | Wofür | Pflicht? |
|---|---|---|
| Python **3.10 oder neuer** (getestet mit 3.11) | Programm | ja |
| **FFmpeg** (≥ 5.0, inkl. `ffprobe`, mit libass/libx264) | Rendering | ja |
| LLM-API-Key (Anthropic, `LLM_API_KEY`) | Themenbewertung, Skript, Caption | ja (außer `--test`) |
| Pexels-API-Key (kostenlos, `STOCK_API_KEY`) | Stock-Videos | empfohlen |
| ElevenLabs-Key (`TTS_API_KEY`) | beste Stimme | optional (Standard `edge` ist gratis) |
| OpenAI-Key (`IMAGE_API_KEY`) | KI-Bilder | optional |

## 2. FFmpeg installieren

**Windows** (PowerShell):
```powershell
winget install Gyan.FFmpeg
```
Danach PowerShell/Terminal **neu starten** und prüfen: `ffmpeg -version`
(Alternative: ZIP von https://www.gyan.dev/ffmpeg/builds/ entpacken und den `bin`-Ordner zum PATH hinzufügen.)

**macOS** (Homebrew): `brew install ffmpeg`

**Linux** (Debian/Ubuntu): `sudo apt update && sudo apt install ffmpeg`

## 3. Projekt einrichten

**Windows (PowerShell):**
```powershell
cd tiktok_bot
python -m venv .venv
.venv\Scripts\Activate.ps1          # bei Fehlermeldung: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements.txt
copy .env.example .env
```

**macOS / Linux:**
```bash
cd tiktok_bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## 4. `.env` und API-Keys

Öffne `.env` in einem Editor und trage die Keys ein. Keys stehen **nie** im Code.

| Variable | Wo bekomme ich sie? | Wofür |
|---|---|---|
| `LLM_API_KEY` | https://console.anthropic.com → *API Keys* (Guthaben aufladen) | Themen, Skripte, Captions. Modell in `config.yaml` → `llm.model` (oder `LLM_MODEL`). OpenAI-kompatibel: `LLM_PROVIDER=openai`. |
| `STOCK_API_KEY` | https://www.pexels.com/api/ (kostenlos) | Stock-Videos im Hochformat |
| `TTS_API_KEY` | https://elevenlabs.io → *Profile → API Keys* | nur bei `voice.provider: elevenlabs` (oder `openai`) |
| `IMAGE_API_KEY` | https://platform.openai.com/api-keys | nur wenn `ai_image` in `visuals.providers` steht |
| `VIDEO_API_KEY` | – | reserviert für den KI-Video-Adapter (s. Abschnitt 9) |

Ohne `STOCK_API_KEY` und ohne eigene Clips nutzt der Bot automatisch die eingebauten dunklen, bewegten
Hintergründe (`procedural`). Das Video wird trotzdem fertig – für Top-Qualität lohnt sich Pexels (gratis).

**Empfohlene Minimal-Einrichtung:** `LLM_API_KEY` + `STOCK_API_KEY`. Stimme: `edge` (gratis, deutsche Neural-Stimme,
liefert exakte Wort-Timings für die Untertitel).

## 5. Bot starten

```
python main.py
```

Weitere Optionen:

```
python main.py --count 3              # drei Videos nacheinander
python main.py --topic "Oktopus"      # eigenes Thema (Titel eines Wikipedia-Artikels) statt Themensuche
python main.py --keep-work -v         # Zwischendateien (output/work/) behalten + Debug-Ausgabe
python main.py --config meine.yaml    # alternative Konfiguration
```

Ergebnis in `output/finished/`:

```
2026-10-28_001_dark-cinematic-knowledge.mp4          ← fertiges Video
2026-10-28_001_dark-cinematic-knowledge.json         ← Metadaten (Skript, Szenen, Quellen, Credits, Scores, ...)
2026-10-28_001_dark-cinematic-knowledge_caption.txt  ← Caption + Hashtags zum Kopieren
```

Typische Konsolenausgabe:
```
[INFO] Suche Themen...
[INFO] 20 Themen gefunden
[INFO] Bestes Thema: Oktopus (Score 8.07, ueberraschende Fakten)
[INFO] Erstelle Skript...
[INFO] Generiere Voice-over (edge)...
[INFO] Erstelle Visuals...
[INFO] Erstelle Untertitel...
[INFO] Rendere Video... (19 Shots, 31.8s)
[SUCCESS] Video fertig:
output/finished/2026-10-28_001_dark-cinematic-knowledge.mp4
```

> Das Rendering braucht je nach Rechner 1–4 Minuten (Übergänge, Zoom, Grain in 1080×1920).

## 6. Testmodus

```
python main.py --test
```

* **keine API-Aufrufe**: Beispiel-Themen/-Skript aus `data/samples/` (Oktopus-Skript mit belegbaren Fakten),
  lokal synthetisierte Platzhalter-Stimme (`mock`), lokale Visuals, lokal erzeugte Musik/SFX.
* Prüft die komplette Kette inklusive FFmpeg, Untertiteln, Mix und Export.
* Die Platzhalter-Stimme besteht aus kurzen Tönen (kein echtes Sprechen) – das ist gewollt.

Unit-Tests: `pytest` (schnell) bzw. `RUN_SLOW=1 pytest` (mit komplettem Render).

## 7. Konfiguration (`config.yaml`)

Alles Wichtige ist ohne Code änderbar:

| Bereich | Beispiele |
|---|---|
| `audio.*` | `voice_volume`, `music_volume`, `ambient_volume`, `sfx_volume`, `whoosh_volume`, `impact_volume`, `riser_volume`, Ducking (`duck_*`), Lautheit `target_lufs` |
| `voice.*` | Anbieter, Stimme (`edge_voice`, `elevenlabs_voice_id`), Tempo (`edge_rate`) |
| `visuals.*` | Anbieter-Reihenfolge `providers`, Clip-Mindestlänge |
| `subtitles.*` | Schrift, Größe, Farben, Position (`y_ratio`), Wörter pro Block |
| `editing.*` | Shot-Länge, Übergänge, Zoomstärke, Color-Grading (`grade.*`) |
| `topics.*` | Quellen, Kategorien, Gewichte für den Viral-Score |
| `content.*` | Sprache, Länge (20–45 s), Szenenzahl |

**Eigene Musik/Sounds (empfohlen für den „Netflix“-Sound):**
* Royalty-free Tracks nach `assets/music/` (mp3/wav) – wird zufällig gewählt, automatisch geloopt, ausgeblendet und unter dem Voice-over abgesenkt.
* Eigene SFX nach `assets/sounds/` benennen mit Präfix `whoosh`, `impact`, `bass_hit`, `riser`, `ambient` (z. B. `impact_01.wav`).
  Nicht vorhanden → werden lokal per FFmpeg synthetisiert.
* Eigene Clips/Bilder nach `assets/videos/` bzw. `assets/images/` (Dateinamen mit Stichwörtern helfen bei der Zuordnung, z. B. `ocean_dark.mp4`).
* **Schrift:** Lege z. B. *Montserrat ExtraBold* (Google Fonts, frei) als `.ttf` in `assets/fonts/` und trage den Familiennamen in `subtitles.font_name` ein. Ohne Font nutzt FFmpeg eine Systemschrift.

## 8. Fehlerbehebung

| Problem | Lösung |
|---|---|
| `'ffmpeg' wurde nicht gefunden` | FFmpeg installieren (Abschnitt 2), Terminal neu starten. |
| `LLM_API_KEY fehlt` / `LLM-Zugriff verweigert` | `.env` im Projektordner? Key korrekt, Guthaben vorhanden? |
| `Modell '...' nicht gefunden` | `llm.model` in `config.yaml` bzw. `LLM_MODEL` auf ein verfügbares Modell setzen. |
| `Edge-TTS lieferte kein Audio` | Internet/Firewall/VPN prüfen; alternativ `voice.provider: elevenlabs`. |
| Keine Stock-Videos, nur dunkle Hintergründe | `STOCK_API_KEY` setzen; Log zeigt „Visual-Anbieter 'pexels' deaktiviert“. |
| Untertitel in falscher Schrift | Font in `assets/fonts/` legen und `subtitles.font_name` exakt auf den Familiennamen setzen. |
| Video zu leise/laut | `audio.*` in `config.yaml`; Gesamtlautheit `target_lufs` (Standard −14). |
| Rendering fehlgeschlagen | Bot versucht automatisch einen **Safe Mode** (harte Schnitte). Details in `output/logs/tiktok_bot.log`; mit `-v` mehr Ausgabe. |
| Skript zu lang/kurz | Wird automatisch gekürzt (Neuaufruf) bzw. leicht beschleunigt (`voice.max_speedup`). |
| PowerShell blockiert `Activate.ps1` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |

Logs: Konsole + `output/logs/tiktok_bot.log`.

## 9. Erweiterungsmöglichkeiten & ehrliche Grenzen

**Nicht eingebaut (bewusst, nichts erfunden):**
* **KI-Video-Generierung:** `AIVideoProvider` in `src/visual_generator.py` ist nur ein markierter Adapter (`NotImplementedError`).
  Anbieter, die sich eignen: Runway, Luma Dream Machine, Kling, fal.ai/Replicate-Modelle. Du brauchst deren API-Doku (Endpunkt,
  Auth, Polling), implementierst `fetch()` (Prompt senden → MP4 laden → `VisualAsset` zurückgeben), setzt `VIDEO_API_KEY` und trägst
  `ai_video` vor `pexels` in `visuals.providers` ein.
* **Automatisches Hochladen zu TikTok:** nicht enthalten (TikTok Content Posting API erfordert eine geprüfte App). Du lädst die MP4
  samt `_caption.txt` selbst hoch.
* **Wort-Timing bei OpenAI-TTS:** liefert keine Zeitstempel → Timing wird geschätzt (edge/elevenlabs sind exakt).
  Verbesserung: Whisper-Alignment als zusätzlicher Schritt in `voice_generator.py`.

**Faktentreue:** Das LLM darf Fakten *ausschließlich* aus dem mitgelieferten Quelltext (Wikipedia-Artikel bzw. Artikeltext) nehmen.
Brainstorm-Themen des LLM zählen nur, wenn ein echter Wikipedia-Artikel existiert. Prüfe das Skript trotzdem kurz in der JSON-Datei,
bevor du veröffentlichst – das LLM kann Quellen missverstehen.

**Ideen:** neuer TTS-Anbieter (Klasse von `TTSProvider` ableiten, in `PROVIDERS` eintragen), weitere Themenquellen
(`TopicFinder._sources`), Wasserzeichen/Intro-Logo, Thumbnail-Export, Planung per Cron/Windows-Aufgabenplanung
(`python main.py` täglich), Mehrsprachigkeit (`content.language`, `voice.edge_voice`), A/B-Hooks (alle Hook-Varianten stehen in der JSON).

## Projektstruktur

```
main.py                 Einstieg (CLI)
config.py / config.yaml Konfiguration (+ .env für Keys)
src/
  pipeline.py           Orchestrierung mit Retry/Fallbacks
  topic_finder.py       Themen finden, belegen, bewerten
  content_generator.py  Skript + Caption zu einem Paket
  script_generator.py   Skript/Hooks/Szenen (LLM)
  llm_client.py         LLM-Anbindung, JSON-Retry
  schema.py             JSON-Validierung
  voice_generator.py    TTS-Anbieter (edge, elevenlabs, openai, mock) + Wort-Timing
  visual_generator.py   Visual-Anbieter (pexels, local, ai_image, ai_video-Adapter, procedural)
  subtitle_generator.py ASS-Untertitel (Wort-Highlighting)
  sound_design.py       Musik, Ambience, SFX, Ducking, Lautheit
  video_editor.py       FFmpeg: Shots, Zoom/Pan, Übergänge, Grading
  exporter.py           Dateinamen, Verifikation, Metadaten
assets/ data/ output/   Eingaben, Beispieldaten, Ergebnisse
```
