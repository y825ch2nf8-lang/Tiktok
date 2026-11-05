# Ball Escape – „Kann der Ball 12 Ringe zerstören?“

Rendert ein fertiges **Satisfying-Physik-Video** für TikTok/Reels/Shorts: ein leuchtender Ball springt in
12 rotierenden Neon-Ringen. Jedes Mal, wenn er durch eine Lücke entkommt, zerbricht der Ring und es gibt
**+2 Bälle**. Jede Kollision spielt die nächste Note einer **gemeinfreien Melodie** (Grieg/Beethoven).

- **1080×1920, 60 fps, H.264 + AAC**, ca. **67 s** lang: Der letzte Ring bricht bei ~60 s, so ist das Video über 1 Minute und erfüllt damit die Längen-Voraussetzung für TikTok Creator Rewards.
- **Komplett synthetischer Ton**: keine Musiklizenz nötig, kein Copyright-Claim.
- **Echte Physik**: fester Zeitschritt und geseedeter Zufall. Das Ende wird nicht gefälscht, sondern per Seed-Suche ausgewählt.
- **Nahtloser Loop**: Am Ende wachsen die Ringe zurück und der letzte Frame entspricht dem ersten.
- Zu jedem Video gibt es eine Caption, Hashtags und einen Vorschlag für den angepinnten Kommentar (`.txt` + `.json`).

## Einrichtung (einmalig)

Voraussetzungen: **Node.js ≥ 18** und **FFmpeg** (siehe Haupt-README, Abschnitt 2).

```bash
cd ball_escape
npm install
npx playwright install chromium
```

## Benutzung

Aus dem Projektordner (`Tiktok/`):

```bash
node ball_escape/render.js                 # Standard-Video (~5–8 min Renderzeit)
node ball_escape/render.js --draft         # schnelle Vorschau: 540×960, 30 fps, gleiche Physik
node ball_escape/render.js --serve         # Live-Vorschau mit Ton im Browser: http://localhost:8080
```

Das Ergebnis landet in `output/finished/`:

```
2026-11-05_ball-escape_12ringe_plus2_seed11.mp4   ← hochladen
2026-11-05_ball-escape_12ringe_plus2_seed11.txt   ← Caption + Hashtags + angepinnter Kommentar
2026-11-05_ball-escape_12ringe_plus2_seed11.json  ← Metadaten (Seed, Ringbruch-Zeiten …)
```

### Optionen

| Option | Standard | Bedeutung |
|---|---|---|
| `--rings N` | `12` | Anzahl Ringe (Hook passt sich an: „Kann der Ball N Ringe zerstören?“) |
| `--mode plus2\|double` | `plus2` | `plus2`: +2 Bälle je Ring (~60 s). `double`: Bälle verdoppeln sich, endet mit 4.096 Bällen; ca. 25 s, gut für Shorts/Reels |
| `--melody NAME[,NAME…]` | `bergkoenig` | Song (siehe Liste unten). Mehrere mit Komma = **Serie**, ein Video pro Song mit eigenem Seed |
| `--seed N\|auto` | `auto` | `auto` sucht einen Seed, bei dem der letzte Ring bei `--target` Sekunden bricht |
| `--target S` / `--tol S` | `60` / `2` | Zielzeit des Finales (bei `double`: 25) |
| `--seed-start N` | `1` | Ab welchem Seed gesucht wird. Ändern, um ein **neues** Video zu bekommen |
| `--seconds S` | – | nur die ersten S Sekunden rendern (Test) |
| `--hook "Zeile 1\|Zeile 2"` | – | eigener Hook-Text (`\|` = Zeilenumbruch) |
| `--draft` | aus | halbe Auflösung, 30 fps, schneller Encoder |
| `--out PFAD` | – | eigener Ausgabepfad |

**Jeden Tag ein neues Video:** einfach `--seed-start` hochzählen (z. B. `--seed-start 1000`, `--seed-start 2000` …).
Jeder Seed ergibt einen anderen Ablauf.

**Serie / Teil 2:** `--rings 24 --target 75`. Der End-Screen zeigt automatisch „Teil 2: 24 Ringe“.
Bei mehr Ringen dauert die Suche länger, dann ggf. `--tol 4` setzen.

## Songs

Alle gemeinfrei (Komponist > 70 Jahre tot bzw. Volkslied), als eigene Notenliste in `melodies.js`:

| Name | Song | Gut für |
|---|---|---|
| `korobeiniki` | Korobeiniki: russisches Volkslied, bekannt als Tetris-Melodie | sofort erkannt, viele Kommentare |
| `turca` | Türkischer Marsch (Mozart) | schnell, verspielt |
| `hummelflug` | Hummelflug (Rimski-Korsakow) | passt perfekt zur Chaos-Phase |
| `jinglebells` | Jingle Bells (Pierpont) | November/Dezember |
| `toccata` | Toccata und Fuge d-Moll (Bach) | dramatisch, gruselig |
| `bergkoenig` | In der Halle des Bergkönigs (Grieg) | Spannung, wird immer höher |
| `fuenfte` | 5. Sinfonie „Schicksal“ (Beethoven) | dramatischer Einstieg |
| `elise` | Für Elise (Beethoven) | ruhig, bekannt |
| `ode` | Ode an die Freude (Beethoven) | bekannt, fröhlich |
| `nachtmusik` | Eine kleine Nachtmusik (Mozart) | klassisch, bekannt |
| `morgenstimmung` | Morgenstimmung (Grieg) | entspannt |
| `wiegenlied` | Wiegenlied „Guten Abend, gut’ Nacht“ (Brahms) | ruhig, ASMR |

**Warum keine Chart-Songs?** Aktuelle Hits sowie Film- und Game-Soundtracks sind geschützt, auch wenn sie nur als einzelne
Synth-Noten gespielt werden. Das kann zu Claims, Sperren und dem Verlust von Creator-Rewards-Einnahmen führen.

Beispiel für eine Serie:
```bash
node ball_escape/render.js --melody korobeiniki,turca,hummelflug,jinglebells,toccata
```

## Posting-Tipps (aus der Recherche)

- **Caption**: Frage als Hook, dann 4–6 Hashtags. Beides steht fertig in der `.txt`-Datei.
- **Angepinnter Kommentar** mit der Auflösung bringt Antworten und Diskussionen.
- **Cross-Posten**: dasselbe MP4 auch auf Reels und Shorts hochladen. Für Shorts lohnt sich ein kürzeres `--mode double`-Video.
- **Regelmäßig posten**: Top-Accounts im Bereich posten täglich. Mit `--seed-start` kostet ein neues Video nur die Renderzeit.
- **Melodie**: Nur gemeinfreie Stücke (Komponist > 70 Jahre tot) verwenden, eigene Transkription. Bekannte Charts- oder Film-Melodien
  sind urheberrechtlich geschützt (GEMA), auch wenn sie nur als einzelne Synth-Noten gespielt werden.

## Aufbau

| Datei | Inhalt |
|---|---|
| `sim.js` | deterministische Physik (Ringe, Lücken, Kollisionen, Ringbruch, Zeitlupe, Seed-Suche). Läuft in Node und im Browser |
| `renderer.js` | Canvas-Zeichnung: Neon-Ringe, Bloom, Trails, Splitter, Funken, Screen-Shake, Texte, Outro/Loop |
| `audio.js` | Ton aus dem Event-Log: Marimba-Noten, Glasbruch, Finale, Hall, Limiter → WAV |
| `melodies.js` | gemeinfreie Melodien als Notenlisten (eigene leicht ergänzbar) |
| `render.js` | CLI: Seed suchen → Audio → Frames (Headless-Chromium) → FFmpeg → MP4 + Caption |
| `index.html` | Live-Vorschau im Browser |
| `fonts/` | Montserrat Black + JetBrains Mono Bold (SIL Open Font License, siehe `OFL-*.txt`) |

Tests: `cd ball_escape && npm test`
