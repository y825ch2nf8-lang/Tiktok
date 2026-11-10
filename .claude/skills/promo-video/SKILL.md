---
name: promo-video
description: Schneide professionelle Werbe-, Event- und Business-Videos (Reels, TikTok, Story, Feed) für Unternehmen und Veranstaltungen aus Screenshots, Fotos, Clips oder Logos. Nutze diesen Skill, wenn der Nutzer eine Werbeanimation, ein Promo- oder Aktionsvideo, eine Business-Präsentation als Video, ein Loop-Video, einen Event-Teaser oder ein Erklärvideo zu einer Dienstleistung will, oder wenn ein Video weniger nach KI und mehr nach einem echten Cutter aussehen soll.
---

# Promo-Video: schneiden wie ein Profi

Der Nutzer ist deutschsprachiger Content Creator und verdient mit kurzen Videos. Antworte auf Deutsch, kurz,
umsetzungsorientiert. Werkzeug: `promo/engine/` (Canvas → Headless-Chromium → FFmpeg, Musik per NumPy).
Referenzprojekte: `promo/kehl_event/` (Business-Loop, 27,5 s) und `promo/bonn_leuchtet/` (Event-Promo, 23 s).

## 1. Was wir gelernt haben: woran man KI-Look erkennt

Version 1 von „Bonn leuchtet“ wirkte nach KI. Der Nutzer hat sie abgelehnt. Diese Dinge waren schuld, und wir benutzen sie nicht mehr:

| KI-/Template-Look (nicht machen) | Cutter-Look (so machen) |
|---|---|
| Regenbogen-Verläufe, Neon-Glow auf Schrift | Eine Akzentfarbe aus der Marke, sonst Creme auf Fast-Schwarz (`#0f0d0b`) |
| Emojis im Video, ✨-Funkeln | Keine Emojis. Kleine Labels in Versalien mit Sperrung |
| Glasmorphism-Karten, abgerundete Ecken, Drop-Shadows | Harte Bildkanten, randlose Fotos, Haarlinien als Trenner |
| Schwebende Bokeh-Kugeln als Hintergrund | Filmkorn, Vignette, warme Light Leaks nur an Übergängen |
| Weiche Überblendungen zwischen allem | Harte Schnitte auf dem Beat, ab und zu Whip-Pan oder Flash |
| Alles zentriert, alles faded rein | Linksbündiges Layout, Zeilen steigen per Maske aus einem Schlitz (Expo-Out) |
| Handschrift-Font (Caveat), Montserrat | Instrument Serif *kursiv* (Gefühl) + Inter Tight 800 (Fakten) |
| Gleichförmiges Tempo | Tempowechsel: ruhige Einstellung → 4 schnelle Wort-Schnitte → ruhig |
| Statische Fotos | Leichte Handkamera-Drift, Push-In, Tilt, Punch-In beim Drop |

## 2. Ablauf

1. **Material sichten.** Screenshots in `~/.claude/uploads/...` zuschneiden, nicht die ganzen Screenshots verwenden.
   - Fremde Logos, Wasserzeichen und Rahmen (z. B. City-Marketing-Rahmen) entfernen. Dünne Linien per Zeilen- oder
     Spalten-Interpolation retuschieren. **Kein Klonstempel auf Menschen**: das sieht man sofort. Lieber wegschneiden.
   - Instagram-UI (Play-Icons, Mehrfachbeitrag-Symbol, Texteinblendungen) wegschneiden.
   - **Immer die schärfste Quelle nehmen.** Hat der Nutzer dasselbe Foto mehrfach geschickt (Story, Beitrag,
     Kachel), die Schärfe messen (Kantenvarianz `ImageFilter.FIND_EDGES` → `.var()` auf demselben Ausschnitt).
     Beispiel Bonn: Der Beitrag-Screenshot war 4,5× schärfer als der Story-Screenshot, obwohl die Pixelzahl ähnlich war.
   - Instagram-Overlays wegretuschieren: Karussell-Zähler „1/5“ (oben rechts, im Nachthimmel per Zeilen-Interpolation),
     rote Rahmen, Logos.
   - **Jedes Foto KI-schärfen (Pflicht, der Nutzer will es so):** `python3 promo/engine/upscale.py in.png out.jpg --mix 0.85`
     (Real-ESRGAN x4plus auf CPU, Modell kommt automatisch aus PyPI). Bei sehr unscharfen Quellen `--mix 0.7`,
     sonst erfindet die KI Details (Flaschen werden zu „Häuschen“). Dauer: ca. 9 s pro 192er-Kachel, also etwa
     5 Minuten für ein Foto mit 1 MP. Mehrere Fotos nacheinander im Hintergrund laufen lassen (`nohup`) und
     währenddessen am Schnitt arbeiten. Erst retuschieren, dann hochskalieren. Fokus- und Crop-Werte bleiben
     gleich, weil `photo()` relativ arbeitet. Pixelzugriffe auf Assets (z. B. Logo-Ausschnitt) mit
     `I.logo.width/<alte Breite>` skalieren.
   - Beurteilen auf Handygröße (Frame auf ~585 px Breite verkleinert), nicht im 100-%-Ausschnitt. Bei 5× Vergrößerung
     wirkt jedes KI-Bild im Pixel-Crop gemalt.
   - Randlos (Vollbild) nur bis ca. 3× Quellauflösung vor dem KI-Upscale. Bei schwächerem Material das Bild als Plate
     (volle Breite, nicht volle Höhe) zeigen oder als Motion-Graphic lösen.
   - **Beste Quelle sind Screenshots vom Reels-Tab** des Profils: Jede Kachel hat ca. 388×690 px, im Beitragsraster
     nur ca. 388×515 px. Die Aufrufzahl unten (Auge-Symbol) und Play-Icons wegschneiden, ebenso Logos von Kunden
     (Becher, Messewände, Fahrzeuge). Bei Story-Highlights (ca. 180 px) lohnt es sich meist nicht.
   - Echte Fotos schlagen gezeichnete Grafiken. Sobald ein echtes Foto einer Leistung da ist, ersetzt es die Motion-Graphic.
   - Hook mit Mensch: Wenn es ein Foto gibt, auf dem jemand der Kamera einen Drink oder das Produkt entgegenhält, als
     Hook-Hintergrund nehmen. Den Bildausschnitt so wählen (`zoom` 1,15 + `fy`), dass Gesicht und Produkt über dem Text liegen.
   - Instagram, Firmen-Websites und Stock-Seiten sind in Cloud-Sessions oft gesperrt. Dann mit dem Material aus dem
     Chat arbeiten und dem Nutzer sagen, welche Domain freigegeben werden müsste. Für mehr Qualität echte Clips
     anfragen (Handyvideos der Bar, Drinks, Gäste).
2. **Fakten nur aus dem Material.** Leistungen, Daten und Orte nur aus Screenshots, Bio und Hashtags. Keine
   erfundenen Preise, Kapazitäten oder Kundenzahlen. Fremde Fotos (z. B. von der Stadt) nicht in ein
   Firmenvideo übernehmen.
3. **Skript als Schnittliste auf dem Beat-Raster** (siehe Abschnitt 3), dann `edit.js` und `score.json` schreiben.
4. **Vorschau** als Kontaktbogen, ansehen, korrigieren. Erst danach komplett rendern.
5. **QA** (Abschnitt 6), dann committen, pushen und beide Formate schicken, mit Caption-Vorschlag.

## 3. Dramaturgie

**Hook (0–1,5 s):** Frame 0 trägt schon die Botschaft, kein Fade-In aus Schwarz. Ein Satz, der die
Dienstleistung erklärt und neugierig macht, Wort für Wort auf den Beat: „Die Bar / kommt / zu dir.“
Oben ein kleines Label mit der Kategorie („MOBILE BARS & CATERING · RHEINLAND“).

**Business-Loop (bewährt, 11 Takte bei 96 BPM = 27,5 s):**
| Takte | Szene | Zweck |
|---|---|---|
| 0–0,75 | Hook, kinetische Typo | stoppt den Daumen |
| 0,75–2 | Produkt-Reveal (Shutter-Wipe) + 3 Verben auf Beats | Was ist es? |
| 2–3 | 4 Anlässe, ein Wort pro Beat, Farbwechsel | Bin ich gemeint? |
| 3–6 | Leistungen als Karussell (je 2 Beats, Whip dazwischen, Zähler 01/06) | Was bekomme ich? |
| 6–7 | „In drei Schritten“: Anfragen, Planen, Feiern (Break in der Musik) | Wie einfach ist Buchen? |
| 7–8 | Vibe-Montage: 4 randlose Bilder, ein Schnitt pro Beat, Text bleibt stehen (Drop: Impact + Flash) | Gefühl |
| 8–10 | CTA: Teamfoto oben (Vertrauen), darunter „Deine Feier. Unsere Bar.“ + Pill-Button mit Domain, pulsiert auf dem Beat | Handlung |
| 10–11 | Endkarte „Kehl Event —“, Push-In beschleunigt in den Schnitt | Loop |

**Loop-Technik:** Der Schluss endet mit einem Gedankenstrich, und der Anfang setzt den Satz fort:
„Kehl Event — / Die Bar kommt zu dir.“ Der Loop-Schnitt sitzt auf der Eins. Die Musik endet mit einem Riser
in die Eins, bei t=0 kommen Impact und Flash. Die Musik wird periodisch gerendert (`"loop": true`), dadurch
laufen Hall-Fahnen nahtlos über den Loop-Punkt. Kein Fade-Out bei Loops.

**Event-Promo (nicht geloopt):** Hook-Titel → 4 Wort-Schnitte → Ort/Bar → Programm als Liste → Einladung → Endkarte, Fade-Out.

## 4. Schnitt- und Gestaltungsregeln

- **Beat-Raster:** Jeder Schnitt liegt auf `n * 60/BPM`. Entspannt: 90–96 BPM. Wort-Montagen schneiden pro Beat,
  normale Einstellungen dauern 2–5 Beats, Lesetexte (Listen) mindestens 3 Sekunden ab dem letzten Element.
- **Typo:** Maximal 2 Schriften. Serif kursiv für Emotion („zu dir.“, „Ihr feiert.“), Grotesk 800 mit
  negativem Tracking für Fakten, Labels 22–26 px in Versalien mit +22 % Sperrung. Zu lange Wörter mit `fit()` verkleinern.
- **Farbe:** Fast-Schwarz, Creme und **eine** Markenfarbe (Kehl: Orange `#e8853a`). Optional eine Zweitfläche
  (Weinrot, Papier). Fotos bekommen alle denselben Grade (`GRADE`).
- **Safe Zones (9:16):** Text nur zwischen y=270 und y=1450. Rechts ca. 150 px frei lassen (Buttons), x ≤ ~930.
  Bilder dürfen in die UI-Zonen hineinlaufen. Bei 4:5 Text zwischen 70 und H−80.
- **Bewegung:** Alles bewegt sich leicht (Drift `hh()`, Zoom +2–5 %/s). Drop: Punch-In von 1,12× auf 1×.
  Endkarte: leichter Push-In.
- **Übergänge:** Standard ist der harte Schnitt. Whip-Pan bei Karussell und Szenenwechseln im selben Thema,
  Light Leak bei Kapitelwechseln, Flash nur auf Drops. Höchstens 2 Leaks pro Video.
- **Fehlendes Footage** als Motion-Graphic lösen, nicht als KI-Bild: Strichgrafik in der Markenpalette
  (Kaffeetasse mit Dampf, Glas, das sich füllt, rotierender Text-Badge um ein Produktfoto).
- **Sound:** Groove + Sounddesign gehören zum Schnitt. Riser in Drops, Impact auf der Eins, Whoosh bei Leaks,
  Swish bei Whips, Tick bei Wort-Schnitten. Lautheit ca. −13 bis −14 LUFS.

## 5. Engine benutzen

Neues Projekt = Ordner `promo/<name>/` mit `index.html` (von `promo/kehl_event/` kopieren), `edit.js`, `score.json`, `img/`.

```bash
python3 promo/engine/music.py promo/<name>/score.json promo/<name>/music.wav
node promo/engine/render.js promo/<name> preview reel 0.3,1.5,3.6,8.0,12.0   # -> preview/contact_reel.jpg
node promo/engine/render.js promo/<name> render reel                       # -> out/<name>_reel_4k.mp4, 2160x3840 (Standard)
node promo/engine/render.js promo/<name> render feed                       # 4:5 in 4K, 2160x2700
node promo/engine/render.js promo/<name> render reel --k=1                 # schneller 1080p-Entwurf
```
**Ausgabe ist immer 4K** (`K=2`: Layout bleibt in 1080er-Einheiten, Canvas rendert doppelt so dicht). Die Bitrate ist
auf 24 Mbit/s gedeckelt, damit 30 s unter ca. 90 MB bleiben (GitHub-Limit 100 MB). Reel und Feed parallel rendern:
etwa 7 Minuten für 23 s in 4K. Vorschauen laufen in 1080p (schnell). Canvas-`blur()`-Werte skaliert die Engine automatisch mit `K`.
Ältere Projektseiten ohne Engine (`promo/bonn_leuchtet/index.html`) haben dieselbe `?k=`-Logik und einen `prepare`-Stub.

**`edit.js`** wird vor der Engine geladen. Engine-Globals (`W,H,S,L,T0,B0,FEED,INK,CREAM,ACC,F,x,I`) nur **innerhalb**
von Funktionen benutzen, auf Top-Level eigene Konstanten anlegen (sonst „INK is not defined“).
```js
window.EDIT = { dur, loop: true, accent: '#e8853a',
  assets: { bar: 'img/bar.jpg', clip1: 'clips/pour.webm' },            // Bilder oder Videos (mp4/webm)
  shots: [{ a: 0, b: 1.875, f: (l, t) => {...} }, { a, b, f, media: [{ name: 'clip1', from: 2.0, speed: 1 }] }],
  fx: [{ type: 'flash', t: 0, a: .35 }, { type: 'leak', t: 7.5 }, { type: 'whip', t: 8.75, w: .1 }] };
```
Helfer: `photo(im,X,Y,w,h,{zoom,fx,fy,...hh(t)})` (Cover-Fit + Fokuspunkt, auch für Videos), `line(str,X,Y,F.serif(px),t0,l,{align,d,alpha,instant})`
(Masken-Reveal), `pop()` (Beat-Wort), `rule()`, `shutter()`, `shade()`, `topShade()`, `circleImg()`, `ringText()`, `fill()`, `measure()`.
Fokuspunkte, die im Clamp-Bereich liegen, bewegen sich nicht. Einen Tilt also im wirklich verfügbaren Bereich planen.

**`score.json`:** `bpm, bars, loop, chords (MIDI), roots, drums[] pro Takt ("full"|"nokick"|"break"|"none"), melody{takt:[[beat,midi]]},
sfx[{type: impact|riser|whoosh|swish|reverse|tick, t, dur?, g?}]`. `riser.t` = Ankunft, `whoosh.t` = Peak.

**Serien aus einer Vorlage (`promo/ki_tipps/`, „KI im Alltag“):** Die Inhalte stehen in `topics.js`, `edit.js` liest
`?topic=N`. Ablauf je Video (21,6 s, 100 BPM, Loop): Hook → Schritt 1 (Strichgrafik im Kamerasucher) → Schritt 2 (Prompt
tippt sich auf Akzentfläche) → Schritt 3 (Ergebnisliste) → CTA. Neues Thema = neuer Eintrag in `topics.js` plus ggf. eine
Grafik in `ART`. Rendern für TikTok in 1080p mit kleiner Datei:
`node promo/engine/render.js promo/ki_tipps render reel --k=1 --crf=22 --q=topic=0 --name=ki_trick_01_fernseher`
(`--q` hängt Query-Parameter an, `--name` setzt den Dateinamen, `EDIT.grain` regelt das Filmkorn).
Stil seit Nov 2026 (Nutzerwunsch „spannender, im Trend“; gilt nur für diese Serie, nicht für Firmen-Promos): Hook mit
einem harten Schnitt pro Beat und Vollfläche im ersten Bild, danach eine Chat-Szene wie eine Bildschirmaufnahme
(Foto-Nachricht, Prompt tippt sich, Antwort mit Haken), Pop-Untertitel mit 1–3 Wörtern im Takt der Stimme,
Fortschrittsleiste. Reihenfolge: `python3 promo/ki_tipps/voiceover.py --timing` (schreibt `vo_timing.js` für die
Untertitel) → rendern → `python3 promo/ki_tipps/voiceover.py` (mischt Stimme `vo/NN.mp3` + `vo/NN_hook.mp3` ein).
Stimme: ElevenLabs „Jan – Social Media Creator“. Für das Creator Rewards Program braucht es Videos über 60 s.
Ergebnisse der KI nur so versprechen, wie sie stimmen: Hinweiszeile (`note`) bei Recht, Preisen und Menünamen.

## 6. QA vor dem Abschicken

- Kontaktbogen pro Szene ansehen: keine fremden Logos, Rahmen oder UI-Reste, kein Text in den Safe-Zone-Rändern, nichts abgeschnitten.
- Varianz prüfen: Sehen zwei Einstellungen gleich aus? Dann einen anderen Ausschnitt, andere Bewegung oder ein anderes Motiv wählen.
- Loop: letzten und ersten Frame nebeneinanderlegen. Audio-Naht prüfen: Die zweite Ableitung an der Naht darf nicht
  über dem 99. Perzentil der Umgebung liegen.
- Lautheit: `ffmpeg -i out.mp4 -af ebur128 -f null -` → I ≈ −13 LUFS.
- 4K prüfen: `ffprobe` meldet 2160×3840 (Reel) bzw. 2160×2700 (Feed). Einen Frame auf Handygröße ansehen.
- Ehrlich bleiben: Instagram spielt Reels höchstens in 1080p aus. Der 4K-Upload sorgt dafür, dass nach der
  Neukomprimierung durch Instagram mehr Schärfe übrig bleibt.
- Ton kann Claude nicht anhören. Das offen sagen und den Nutzer bitten reinzuhören.
- Lieferung: beide Formate (9:16 für Reel, Story und TikTok, 4:5 für den Feed) per SendUserFile, dazu Caption,
  Hashtags, Collab-Tipp und Cover-Hinweis (Cover-Bild in der App wählen, z. B. das Hook-Frame).
