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
| `--sound music\|asmr` | `music` | `asmr`: Geräusche statt Musik (siehe unten) |
| `--music layers\|bounce` | `layers` | `layers`: jeder Ring = neues Instrument (siehe unten). `bounce`: nur Aufprall-Noten |
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

## Zwei Formate

| `--scene` | Ablauf | Vorbild |
|---|---|---|
| `box` (**empfohlen**) | Eine große Arena mit wandernder Lücke. Jeder entkommene Ball fällt raus, dafür kommen **+2** rein. Der Zähler wächst bis `--goal` (Standard 1.000). An 12 Meilensteinen kommt je ein Instrument dazu, beim Ziel explodiert alles | Top-Videos von @loopdatcoding (523K Views) und @realracery (3,3M) |
| `rings` | 12 Ringe nacheinander zerstören, +2 Bälle und ein Instrument pro Ring | klassisches „Can the ball escape?“ |

Weitere Optionen: `--skin smiley|cat|egg|neon` (Figuren statt Bälle), `--lang de|en`, `--watermark @deinhandle`.

```bash
node ball_escape/render.js --scene box --skin cat --melody korobeiniki --watermark @deinhandle
```

## ASMR-Modus: Geräusche statt Musik

`--sound asmr` ersetzt die Musik durch selbst erzeugte, **leise und weiche** Geräusche (≈ −21 LUFS statt Musik-Lautstärke):

| Moment | Geräusch |
|---|---|
| Aufprall | Standard `soft`: gedämpfter Faden-„Thup“, tief (130–260 Hz), lange Fäden etwas tiefer. Je dichter die Aufpralle, desto leiser jeder einzelne, damit es wie ein sanftes Rieseln klingt |
| Entkommen | kleiner Wassertropfen, höchstens 6 pro Sekunde, steigt bis zum Ziel nur um 1 Oktave |
| Meilenstein | leiser, reiner Zweiklang (kein Metall, immer gleiche Höhe), ca. 15 dB unter den Aufprall-Tönen. Im Bild steht „LEVEL 5“ |
| Finale | weicher Knall, danach Stille |

Mit `--asmr soft|drop|string|click|marble|glass|pop|boing|plop|crack` wählst du ein anderes Aufprall-Geräusch
(`drop` = Wassertropfen, `string` = leise gezupft). Der Hook wird zu „SCHAFFT ER 1.000 BÄLLE?“, die Caption endet mit
„Ton an 🔊“.

```bash
node ball_escape/render.js --scene box --skin cat --sound asmr --threads
node ball_escape/render.js --scene box --skin cat --sound asmr --threads --asmr drop
```

### Fäden (`--threads`)

Bei jedem Aufprall spannt sich ein Faden vom Aufprallpunkt an der Wand zur Figur. Die Fäden drehen sich mit der Arena,
das Netz wird mit jeder Stufe dichter. Beim Entkommen reißen sie. Im ASMR-Modus klingt jeder Aufprall wie ein gezupfter
Faden-„Thup“, weich und tief.

```bash
node ball_escape/render.js --scene box --skin cat --sound asmr --threads
```

**A/B-Test:** Mit demselben `--seed` und `--skin` ist der Ablauf identisch, nur der Ton und der Hook unterscheiden sich.

## Song-Aufbau: ein Instrument pro Ring

Standardmäßig (`--music layers`) baut sich der Song mit den Ringen auf:

- **Vor dem ersten Ring** spielt jeder Aufprall die nächste Melodie-Note. So erkennt man den Song schon früh.
- **Ab dem ersten Ring** läuft der Song im Takt und die Ringe pulsieren mit dem Beat. Jeder zerbrochene Ring schaltet ein
  Instrument frei, im Bild steht dann z. B. „+ Bass“:

  Beat → Melodie → Bass → Hi-Hats → Synth-Flächen → Clap → Arpeggio → Lead-Synth → Glocken → Percussion → Sub & Stabs → Harmonie

- **Beim letzten Ring** läuft der ganze Song („+ Harmonie = ganzer Song!“) und blendet zum Loop hin aus.

Bei mehr oder weniger als 12 Ringen werden die Instrumente gleichmäßig verteilt. Der letzte Ring macht den Song immer komplett.
Mit `--music bounce` bekommst du den alten Stil zurück, bei dem nur die Aufprall-Noten spielen.

## Songs

Alle gemeinfrei (Komponist > 70 Jahre tot bzw. Volkslied), selbst arrangiert in `melodies.js` (Melodie mit Rhythmus, Akkorde, Tempo):

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
| `audio.js` | Synthesizer: Kick, Clap, Hats, Bass, Pads, Arp, Lead, Glocken … + Sidechain, Hall, Limiter → WAV |
| `arrangement.js` | welcher Ring welches Instrument freischaltet + Notenplan pro Instrument |
| `melodies.js` | gemeinfreie Melodien als Notenlisten (eigene leicht ergänzbar) |
| `render.js` | CLI: Seed suchen → Audio → Frames (Headless-Chromium) → FFmpeg → MP4 + Caption |
| `index.html` | Live-Vorschau im Browser |
| `fonts/` | Montserrat Black + JetBrains Mono Bold (SIL Open Font License, siehe `OFL-*.txt`) |

Tests: `cd ball_escape && npm test`
