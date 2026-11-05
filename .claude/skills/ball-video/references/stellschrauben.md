# Stellschrauben in ball_escape/

| Beobachtung bei der Konkurrenz | Umsetzung |
|---|---|
| Anderer Hook-Text | `--hook "Zeile 1\|Zeile 2"`, Standard in `renderer.js` → `hookLines()` / `subLine()` |
| Schnellerer Start | `findSeed` in `sim.js`: `maxFirst` (Sekunden bis zum ersten Ring) senken |
| Längere/kürzere Videos | `--target` (Finale-Zeitpunkt), `outroDur` in `sim.js` |
| Mehr Chaos am Ende | `--mode double` (bis 4.096 Bälle), oder `PRESETS` in `sim.js` |
| Mehr/weniger Ringe, Serie | `--rings N`, End-Screen-Teaser automatisch „Teil 2: 2N Ringe“ |
| Lückengröße / Schwierigkeit | `gapStartDeg`, `gapEndDeg` in `DEFAULTS` (`sim.js`), danach Seed-Trefferquote prüfen |
| Farben / Glow | `ringHue()`, `glowSprite()`, `bloom()` in `renderer.js` |
| Hintergrund | Vignette in `renderFrame()` (`renderer.js`) |
| Neuer Song | in `melodies.js` mit Rhythmus + Akkorden eintragen; Test `npm test` prüft die Längen |
| Instrument-Reihenfolge / Lautstärke | `LAYERS` in `arrangement.js`, `MIX` in `audio.js` |
| Nur Aufprall-Noten statt Song-Aufbau | `--music bounce` |
| Caption / angepinnter Kommentar | `captionFor()` in `render.js` |
| Neue Mechanik (z. B. Rennen, Farbkampf) | neues Modul neben `sim.js`, gleiche Timeline-/Event-Schnittstelle nutzen |

Nach jeder Änderung: `npm test`, ein `--draft`-Render, Schlüsselbilder ansehen.
