# Crypto-Tracker 🪙

Findet die **profitabelsten Krypto-Trader der Welt**, verfolgt **jeden ihrer Trades in Echtzeit**
und analysiert, **wann** sie Long oder Short gehen und wieder aussteigen: Uhrzeit (deutsche Zeit),
Wochentag, Börsen-Session (Asien/Europa/USA) und Wochenende. Dazu kommen Haltedauer und Trefferquote,
und es wird ausgewertet, ob sich Kopieren gelohnt hätte.

> ⚠️ **Keine Anlageberatung.** Der Bot handelt **nur mit Spielgeld** (Paper-Trading).
> Gehebelte Futures können zum Totalverlust führen. Vergangene Gewinne sagen nichts über die Zukunft.

## Woher kommen die Daten?

**Hyperliquid** ist die größte On-Chain-Börse für Krypto-Futures. Auf der Blockchain ist **jeder Trade
öffentlich**: mit Zeitstempel auf die Millisekunde, Preis, Größe und realisiertem Gewinn. Es gibt ein
öffentliches Leaderboard mit nachprüfbaren Gewinnen. Einen API-Key braucht man nicht.

Der Bot wählt daraus die „besten“ Trader nach diesen Regeln:
- Woche, Monat und Allzeit **im Plus** (nicht nur ein Glückstreffer)
- Konto ≥ 100.000 $ (keine Mini-Konten mit 5000 % ROI)
- **Keine Market-Maker oder HFT-Bots**: Wer pro Monat mehr als das 150-fache seines Kontos umsetzt, fliegt raus
- Ranking: 45 % Monats-ROI, 35 % Allzeit-Gewinn, 20 % Wochen-ROI

## Schnellstart

```bash
pip install -r requirements.txt

python -m crypto_tracker demo        # offline testen, fiktive Daten
python -m crypto_tracker discover    # Top-20-Trader aus dem Leaderboard wählen
python -m crypto_tracker fetch       # ihre Trades der letzten 30 Tage + offene Positionen laden
python -m crypto_tracker report      # -> output/crypto_report/report.html
python -m crypto_tracker positions   # Smart Money: wie sind die Profis JETZT positioniert?
python -m crypto_tracker watch       # Live-Bot: meldet neue Trades und kopiert sie mit Spielgeld
```

### Live-Alarme aufs Handy (Telegram)
1. In Telegram `@BotFather` anschreiben → `/newbot` → Token kopieren
2. Deine Chat-ID über `@userinfobot` holen
3. In `.env` eintragen: `TELEGRAM_BOT_TOKEN=...` und `TELEGRAM_CHAT_ID=...`
4. `python -m crypto_tracker watch` starten

Beispiel-Alarme:
```
🟢 0x8a3f…91c2 eröffnet LONG BTC – 2.40 Mio. $ @ 101.250 $ (Di 15:32)
🚨 KONSENS: 4 Top-Trader gehen SHORT auf ETH: ...
📝 Paper: LONG BTC @ 101.250 $ kopiert (100 $)
```

## Was steht im Report?

| Bereich | Inhalt |
|---|---|
| 🎬 TikTok-Hooks | fertige Aufhänger-Sätze aus den echten Zahlen |
| Smart Money | Long/Short-Anteil der Top-Trader pro Coin, Volumen, Ø Hebel |
| Trader-Tabelle | 30-Tage-Gewinn, Trefferquote, Profit-Faktor, Haltedauer, Lieblings-Uhrzeit und -Tag, Wochenend-Anteil, Top-Coins |
| Kopiert +1h/+4h/+24h | Ergebnis, wenn man jeden Einstieg **5 Min. später** kopiert hätte |
| Timing-Charts | Long-/Short-Einstiege und Ausstiege nach Uhrzeit, Wochentag, Session |
| Konsens-Signale | Mindestens 3 Top-Trader steigen innerhalb von 24 Std. in dieselbe Richtung ein |
| Backtest | Ergebnis, wenn man alle Konsens-Signale kopiert und 24 Std. gehalten hätte |

Alles Weitere stellst du in `config.yaml` ein: Anzahl Trader, Mindestgröße, Zeitzone, Kopier-Verzögerung,
Spielgeld pro Trade und eigene Wallets, die zusätzlich beobachtet werden sollen.

## Tests
```bash
python -m pytest crypto_tracker/tests -q
```
