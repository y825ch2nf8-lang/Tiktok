---
name: ball-video
description: Produce and improve "Kann der Ball entkommen?" satisfying physics videos (ball_escape/) for TikTok, Reels and Shorts, and analyze competing simulation accounts to adapt the videos. Use when the user asks for new ball/ring/simulation videos, a video series, a competitor or account analysis of similar satisfying-simulation creators, or wants the videos changed based on what performs better elsewhere.
---

# Ball-Video: produzieren, vergleichen, verbessern

Der Nutzer ist deutschsprachiger TikTok-Creator und verdient mit kurzen Videos. Antworte auf Deutsch, kurz und
umsetzungsorientiert. Das Werkzeug ist `ball_escape/` (Node + Headless-Chromium + FFmpeg), siehe `ball_escape/README.md`.

## 1. Videos produzieren

```bash
node ball_escape/render.js                                   # 1 Video, ~67 s, 12 Ringe, Song baut sich pro Ring auf
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

- Hook als Frage oben im Bild, Regel in einer Zeile darunter. Keine Voiceover-Stimme. *(Recherche Nov 2026)*
- 61–75 s für TikTok Creator Rewards, 60 fps, 1080×1920. Rechts 140 px und unten 380 px frei lassen für die TikTok-Buttons.
- Nahtloser Loop: Der letzte Frame entspricht dem ersten. YouTube zählt seit 31.03.2025 jede Wiederholung als View,
  deshalb lohnt sich der Loop auf Shorts besonders. *(Suchtreffer channelprofiler.com)*
- Gute Kommentar-Auslöser: „Erkennst du den Song?“, Auflösung im angepinnten Kommentar, „Teil 2“-Serien.
- Täglich posten, jedes Video auf TikTok, Reels und Shorts.
