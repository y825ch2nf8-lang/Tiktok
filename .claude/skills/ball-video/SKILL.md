---
name: ball-video
description: Produce and improve "Kann der Ball entkommen?" satisfying physics videos (ball_escape/) for TikTok, Reels and Shorts, and analyze competing simulation accounts to adapt the videos. Use when the user asks for new ball/ring/simulation videos, a video series, a competitor or account analysis of similar satisfying-simulation creators, or wants the videos changed based on what performs better elsewhere.
---

# Ball-Video: produzieren, vergleichen, verbessern

Der Nutzer ist deutschsprachiger TikTok-Creator und verdient mit kurzen Videos. Antworte auf Deutsch, kurz und
umsetzungsorientiert. Das Werkzeug ist `ball_escape/` (Node + Headless-Chromium + FFmpeg), siehe `ball_escape/README.md`.

## 1. Videos produzieren

```bash
node ball_escape/render.js --scene box --skin cat            # Top-Format: Arena, +2 je Entkommen, bis 1.000
node ball_escape/render.js --scene box --lang en             # englisch für weltweite Reichweite
node ball_escape/render.js                                   # Ring-Format: 12 Ringe, Song baut sich pro Ring auf
node ball_escape/render.js --melody korobeiniki,turca,toccata  # Serie, ein Video pro Song
node ball_escape/render.js --seed-start 3000                 # neuer Ablauf (jeder Seed = anderes Video)
node ball_escape/render.js --mode double --target 25         # kurze Version für Shorts/Reels
node ball_escape/render.js --draft --seconds 10              # schnelle Kontrolle
```

- Ergebnis in `output/finished/`: `.mp4` + `.txt` (Caption, Hashtags, angepinnter Kommentar) + `.json`.
- Zwei Durchläufe parallel gehen mit unterschiedlichen `--port`- und `--seed-start`-Werten.
- Vor dem Abschicken: Länge > 61 s (Creator Rewards), keine Warnung „Render weicht ab“, Schlüsselbilder prüfen.
  Dafür einzelne Frames per `ffmpeg -ss <s> -i video.mp4 -frames:v 1 x.png` ziehen und ansehen.
- Ton kann Claude nicht anhören. Das immer offen sagen und den Nutzer bitten, reinzuhören.
- Nur gemeinfreie Melodien (`ball_escape/melodies.js`). Chart-, Film- und Game-Soundtracks lehnen wir ab
  (GEMA/Content ID, Creator Rewards). Volkslieder wie Korobeiniki gehen, aber ohne Markennamen im Video.

## 2. Konkurrenz analysieren

Ziel: herausfinden, was erfolgreichere Accounts **konkret** anders machen. Nichts erfinden: Jede Aussage braucht eine
Quelle (Screenshot, Zahl vom Nutzer, Suchtreffer). Unbelegtes klar als Vermutung kennzeichnen.

1. **Daten holen.** TikTok, YouTube und viele Analyse-Seiten sind in Cloud-Sitzungen oft gesperrt
   (`getaddrinfo ENOTFOUND`). Dann:
   - Websuche nach dem Handle (findet meist Profilzahlen und Video-Titel aus Snippets).
   - Den Nutzer um **Screenshots oder eine Bildschirmaufnahme** bitten: Profil mit Zahlen, die 3 meistgesehenen
     Videos (Startbild, Mitte, Ende), Caption, Sound-Name. Das ist die zuverlässigste Quelle.
   - Alternativ: Domains `tiktok.com`, `www.tiktok.com`, `vm.tiktok.com` in den Netzwerkeinstellungen freischalten lassen.
2. **Vergleichen** mit der Checkliste in [references/analyse-checkliste.md](references/analyse-checkliste.md).
3. **Ergebnis** als Tabelle „Die machen es so / wir machen es so / Änderung“ und dazu die 3 Änderungen mit der größten
   Wirkung zuerst.
4. **Festhalten:** Account und Erkenntnisse in [references/konkurrenz.md](references/konkurrenz.md) eintragen (mit Datum
   und Quelle), damit spätere Sitzungen darauf aufbauen.

## 3. Erkenntnisse in die Videos übernehmen

Welche Stellschraube welche Beobachtung umsetzt: [references/stellschrauben.md](references/stellschrauben.md).
Danach `cd ball_escape && npm test` ausführen, ein Testvideo mit `--draft` rendern, Schlüsselbilder ansehen, dann die
Serie rendern und alles committen.

## 4. Lernen aus eigenen Zahlen

Nennt der Nutzer Views, Likes oder die Watchtime eigener Videos, trägst du sie in `references/konkurrenz.md` unter
„Eigene Videos“ ein (Video-Datei, Song, Seed, Zahlen). Ab 5 Videos lässt sich vergleichen, welcher Song, welche
Länge oder welcher Hook besser läuft. Diese Erkenntnisse kommen in die Regeln unten.

## Gelernte Regeln (immer anwenden, mit Quelle erweitern)

- **4 Test-Formate (06.11., nach Nutzer-Screenshots aus der „Für dich“-Seite):** `--scene dense` (500 Ringe in 1 Minute,
  Vorbild 1,7K Likes), `layers` („Was ist ganz unten?“, 40K Likes), `battle` („Wer gewinnt?“, 296K Likes, eigene Teams
  statt Marken-Logos), `press` (Hydraulische Presse, 62K Likes, eigene Auslegung). Code in `formats.js`. Ergebnisse
  der Tests in konkurrenz.md eintragen, dann das beste Format zum Standard machen.

- **Hook nie über y≈250 px.** In der TikTok-App liegt dort die Such-/Tab-Leiste. v1 war verdeckt.
  *(eigener Screenshot 05.11.: 1.973 Views, aber nur 0,6 % Likes)*
- **Unter 10K Followern: kurz (`--length short`, ≈34 s, Standard bei Box).** Mehr Leute schauen bis zum Höhepunkt,
  das bringt mehr Likes und Push. 60+ s erst, wenn die Creator Rewards erreichbar sind.
- **Die ersten 2 Sekunden müssen etwas zeigen:** Die Figur ist groß, das erste Entkommen kommt nach spätestens 3 s
  (`maxFirst`).
- **Die erste Sekunde entscheidet:** v1 verlor die meisten Zuschauer bei 0:01 (Ø 13,9 s, 0,84 % ganz gesehen). Ab dem
  ersten Frame muss sich etwas bewegen oder aufbauen. Likes kamen bei 0:04, sobald etwas passierte.
- **Wenige große Figuren statt 1.000 Punkte** (`--goal 100` → Figuren 80 px Radius, Lücke 48°). Grund: Racerys Top-Video
  (3,3 Mio.) zeigt ~10 große Gesichter. `--skin faces` = 5 Gesichter mit Ausdruck (erschrocken, lachend, cool, wütend,
  verliebt). Bei Figuren ist der Glow reduziert, damit Gesichter erkennbar bleiben.
- **Wassertropfen-Melodie (`--asmr dropmelody --melody …`):** Tropfen spielen die Song-Noten. So bleibt es ASMR, und die
  Leute können trotzdem den Song raten. Beide Top-Accounts setzen auf Song-Raten.
- **Nahtloser Loop (`--loop seamless`):** keine Schlusstafel; nach der Explosion wächst die Arena in 1,3 s zurück, der
  letzte Frame ist identisch mit dem ersten. Zuschauer schauen ungewollt nochmal (Wunsch des Nutzers 06.11.).
- **Dateigröße:** Standard jetzt crf 23 (≈ 20–25 MB statt 100 MB). 100-MB-Dateien ließen sich am Handy nicht laden.
- **ASMR-Standard = Wassertropfen (`drop`).** Der Nutzer hat am 06.11. aus 3 Hörproben (Thup, Wassertropfen, leise gezupft)
  den Wassertropfen gewählt.
- **ASMR muss leise und weich sein.** Nutzer-Feedback 05.11.: Das Level-up-Ding (FM-Glocke, wurde immer höher) und das
  gezupfte Aufprall-Geräusch (3 Oktaven, langes Nachklingen, −14 LUFS) waren „viel zu laut und unsatisfying“. Seitdem gilt:
  ca. −21 LUFS, Aufprall tief und kurz (`soft`), dichte Phasen automatisch leiser, Level-up ca. 15 dB unter den
  Aufprall-Tönen, nichts Metallisches und nichts, was endlos höher steigt. Neue Klänge immer mit 12-s-Hörproben
  (`--seconds 12 --out …`) vom Nutzer abnehmen lassen, Claude kann nicht hören.
- **Fäden (`--threads`)** sorgen ab dem ersten Aufprall für ein wachsendes Muster. Dazu passt der weiche Faden-„Thup“
  (`--sound asmr` wählt automatisch `drop`). Beim Entkommen reißen die Fäden.
- **Bei wenigen Likes zuerst die Analytics anfordern:** durchschnittliche Wiedergabezeit und „Gesamtes Video angesehen“
  in Prozent. Erst damit lässt sich sagen, wo die Leute abspringen.

- **Standard = `--scene box`** mit Figuren (`--skin cat|smiley|egg`), Zähler bis `--goal 1000`. Die Top-Videos von
  @loopdatcoding und @realracery funktionieren genau so; Videos mit schlichten Bällen liegen weit dahinter.
  *(Screenshots 05.11.2026, siehe konkurrenz.md)*
- Text kurz und in Großbuchstaben: Frage oben („WIE SCHNELL ERKENNST DU DEN SONG?“), Regel als weißes Label. Jedes Mal
  derselbe Hook, damit er zum Markenzeichen wird.
- Wasserzeichen mit dem Handle des Nutzers (`--watermark @handle`) gegen Reuploads.
- Caption: Frage + genau 4 Hashtags (`#satisfyingvideos #bouncingball #relaxing #physics`).
- A/B-Test Deutsch vs. Englisch (`--lang en`), Zahlen in konkurrenz.md eintragen.
- **Laufender A/B-Test Song vs. ASMR** (`--sound asmr`): gleicher Seed und gleiche Figur, nur der Ton ist anders.
  Paare stehen in konkurrenz.md. Gewinnt ASMR bei Views und Watchtime, wird `--sound asmr` der Standard. Ansonsten bleibt
  der Song-Aufbau. Dafür mindestens 2 Paare auswerten, dann entscheiden.

- Hook als Frage oben im Bild, Regel in einer Zeile darunter. Keine Voiceover-Stimme. *(Recherche Nov 2026)*
- 61–75 s für TikTok Creator Rewards, 60 fps, 1080×1920. Rechts 140 px und unten 380 px frei lassen für die TikTok-Buttons.
- Nahtloser Loop: Der letzte Frame entspricht dem ersten. YouTube zählt seit 31.03.2025 jede Wiederholung als View,
  deshalb lohnt sich der Loop auf Shorts besonders. *(Suchtreffer channelprofiler.com)*
- Gute Kommentar-Auslöser: „Erkennst du den Song?“, Auflösung im angepinnten Kommentar, „Teil 2“-Serien.
- Täglich posten, jedes Video auf TikTok, Reels und Shorts.
