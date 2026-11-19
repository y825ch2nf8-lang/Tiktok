# Memecoin-Bot für Telegram 🔎🪙

Ein Telegram-Bot, der auf Anfrage nach Memecoins sucht, die **über Trust Wallet kaufbar** sind
(Solana, BNB Smart Chain, Ethereum, Base). Er prüft sie auf Rug-Pull, Honeypot und Insider-Wallets und schickt dir:

- die **3 besten Kandidaten** mit Contract-Adresse,
- deinen **Favoriten** mit 7 Punkten: Warum? Market Cap, Potenzial, Risiken, Kauf über Trust Wallet, Contract, Kaufbedingungen,
- **Szenarien** für 100 / 500 / 1.000 € bei 5x, 10x, 20x und 50x, inklusive Gebühren, Slippage und Verlustfällen,
- eine Liste der **aussortierten Coins** mit Grund.

Findet er nichts Überzeugendes, sagt er das klar: **„keine Kaufempfehlung“**.

> ⚠️ **Keine Anlageberatung.** Memecoins können jederzeit auf 0 fallen. Der Bot gibt nie „Kaufen!“ aus,
> sondern höchstens „Watchlist – nur unter Bedingungen“. Er kauft auch nichts selbst und braucht keinen Zugriff auf deine Wallet.

## Befehle in Telegram

| Befehl | Was passiert |
|---|---|
| `/scan` | Scannt alle 4 Chains. Dauert ca. 3–12 Minuten (je nach Auslastung der Datenquellen). |
| `/scan solana` | Nur eine Chain (`solana`, `bsc`, `eth`, `base`). Geht schneller. |
| `/check <Contract>` | Prüft einen bestimmten Coin. Du kannst auch einfach nur die Adresse schicken. |
| `/check <Contract> base` | Wie oben, mit fester Chain. |
| `/invest 250` | Szenarien für 250 € mit dem Favoriten des letzten Scans |
| `/invest 250 <Contract>` | Szenarien für einen bestimmten Coin |
| `/status` | Wann war der letzte Scan, wer war Favorit? |
| `/hilfe` | Übersicht |

## Am einfachsten: per GitHub-Kommentar (nur Handy, gratis, ohne Einrichtung)

Der Bot läuft schon fertig in diesem GitHub-Projekt.
1. GitHub-App öffnen → Projekt **Tiktok** → **Issues** → **„🤖 Memecoin-Bot“**.
2. Einen Kommentar mit dem Befehl schreiben, z. B. `/scan`, `/scan solana` oder `/check <Contract>`.
3. Der Bot reagiert sofort mit 👀. Die Antwort kommt als Kommentar (`/check` ca. 1 Min., `/scan` ca. 10 Min.),
   und die GitHub-App schickt dir eine Benachrichtigung.

Nur Kommentare vom Besitzer des Projekts lösen den Bot aus. Fremde können also keine Scans starten.
Weil das Projekt öffentlich ist, sind die Antworten für alle sichtbar.
Technik: `.github/workflows/memecoin-bot.yml` startet `python -m memecoin_bot github` auf GitHub Actions
(für öffentliche Projekte kostenlos). `/invest` braucht hier immer einen Contract (`/invest 250 <Contract>`).

## Als Telegram-Bot nur mit dem Handy (Railway, ca. 10 Minuten)

Der Bot läuft auf **Railway**, einem Cloud-Dienst, den du komplett im Handy-Browser bedienst.
Kosten: der erste Monat ist mit Testguthaben gratis, danach ca. 5 $/Monat (Hobby-Plan).

**1. Bot bei Telegram anlegen**
In Telegram **@BotFather** öffnen → `/newbot` → Name und Benutzername (endet auf `bot`) wählen →
den **Token** kopieren (z. B. `7123456789:AAH...`). Den gibst du niemandem.

**2. Auf Railway starten**
1. **railway.com** im Handy-Browser öffnen → **Login with GitHub** (das Konto mit dem Projekt „Tiktok“).
2. **New Project** → **Deploy from GitHub repo** → Zugriff auf **Tiktok** erlauben → auswählen.
3. Auf den Service tippen → **Variables** → **Raw Editor** → diese drei Zeilen einfügen und ausfüllen:
   ```
   MEMECOIN_BOT_TOKEN=7123456789:AAH...
   TELEGRAM_ALLOWED_USERS=deinTelegramName
   RAILPACK_START_CMD=python -m memecoin_bot bot
   ```
   Dein Telegram-Name steht in Telegram unter Einstellungen → Benutzername (ohne @ eintragen).
4. Speichern → **Deploy**. Unter **Deployments → View Logs** erscheint nach ein paar Minuten
   **„✅ Bot @deinbot läuft“**.

**3. Loslegen**
Deinem Bot in Telegram `/scan` schicken.

| Problem | Lösung |
|---|---|
| In den Logs stehen Fehler zu `main.py`, FFmpeg oder LLM | Railway startet das Video-Projekt statt des Bots: **Settings → Deploy → Custom Start Command** = `python -m memecoin_bot bot` |
| „Bot-Token fehlt“ | Variable heißt nicht genau `MEMECOIN_BOT_TOKEN` oder Leerzeichen vor dem Token |
| Bot antwortet „Dieser Bot ist privat“ | Benutzername falsch geschrieben – der Bot zeigt dir in der Antwort deinen echten Namen und deine Chat-ID |
| Du hast keinen Telegram-Benutzernamen | Bot schickt dir bei `/start` deine Chat-ID → als `TELEGRAM_ALLOWED_CHATS` eintragen |

## Einrichtung auf dem eigenen PC

1. Bot bei @BotFather anlegen (wie oben).
2. `.env.example` nach `.env` kopieren und ausfüllen:
   ```
   MEMECOIN_BOT_TOKEN=7123456789:AAH...
   TELEGRAM_ALLOWED_USERS=deinTelegramName
   ```
3. Starten:
   ```bash
   pip install -r requirements.txt
   python -m memecoin_bot bot
   ```
Der Bot läuft, solange das Fenster offen und der PC an ist.

> Warum die Sperre mit Benutzername/Chat-ID? Sonst könnte jeder, der deinen Bot findet, Scans starten und deine
> API-Limits aufbrauchen.

## Ohne Telegram testen

```bash
python -m memecoin_bot demo                 # erfundene Tokens, ohne Internet – zeigt alle Regeln in Aktion
python -m memecoin_bot scan                 # echter Scan im Terminal
python -m memecoin_bot scan --chain solana  # nur Solana
python -m memecoin_bot check 2j5SaS7xy776qCBpyPQbZjyQSAtKiFgrwjfErthnW2ZM
python -m pytest memecoin_bot/tests         # automatische Tests
```

## Wie der Bot arbeitet

```
1. Sammeln     DexScreener (Boosts, neue Profile, Community-Takeovers) + GeckoTerminal-Trendlisten (1h/6h/24h)
2. Anreichern  Preis, Market Cap, Liquidität, Volumen, Alter je Token (DexScreener)
3. Vorfilter   nur Memes: keine Stablecoins/Aktien-Tokens; MC 150 Tsd.–30 Mio. $, Liquidität ≥ 40 Tsd. $, Volumen ≥ 100 Tsd. $
4. Tiefenprüfung (die 10 vielversprechendsten)
   • Kursverlauf 30 Tage: Volumen-Trend, 7-Tage-Änderung, Abstand zum Hoch, 7-Tage-Tief
   • Große Trades > 500 $: kaufen oder verkaufen die größeren Wallets?
   • Käufer/Verkäufer (unique Wallets) der letzten 24 h
   • Solana: RugCheck (Mint/Freeze, LP-Sperre, Top-Holder ohne Pools, Insider-Netzwerke) + GoPlus (Holder)
   • BSC/ETH/Base: GoPlus (Honeypot, Steuern, Owner-Rechte, LP-Sperre, Holder) + Honeypot.is (Kauf/Verkauf simuliert)
5. Bewerten    harte Ausschlussgründe → raus; sonst Score 0–100
6. Antwort     Top 3, Favorit (nur ab Score 60), Bedingungen, Szenarien
```

### Harte Ausschlussgründe (Red Flags)
- Mint- oder Freeze-Authority aktiv, Honeypot, Steuer über 5 %, Owner kann minten, pausieren, blacklisten oder Steuern ändern
- weniger als 80 % der Liquidität gesperrt oder verbrannt
- eine Wallet hält mehr als 15 %, die Top 10 halten mehr als 50 %, der Entwickler mehr als 10 %, ein Netz verbundener Wallets mehr als 25 %
- jünger als 24 h oder schon mehr als 300 % in 24 h gestiegen (nicht mehr „früh“)
- Wash-Trading: mehr als 5× so viele Trader wie Holder, oder hohes Volumen ohne echte große Trades
- Hype vorbei: mehr als 40 % Verlust in 7 Tagen bei fallendem Volumen

### Score (0–100)
| Baustein | Punkte | Gut ist … |
|---|---|---|
| Volumen-Trend | 15 | letzte 3 Tage deutlich über den 7 Tagen davor |
| Whales | 15 | große Trades netto auf der Kaufseite |
| Verteilung | 15 | Top 10 halten wenig |
| Market Cap | 10 | niedrig (mehr Luft nach oben, aber mehr Risiko) |
| Käuferdruck | 10 | mehr Käufer- als Verkäufer-Wallets |
| Community | 10 | viele Holder im Verhältnis zur Market Cap |
| Liquidität | 10 | hohe Liquidität im Verhältnis zur MC |
| Momentum | 7 | Aufwärtstrend, aber nicht parabolisch |
| Nicht überhitzt | 8 | keine +200 % in 24 h |

Abzüge: jede Warnung −2 Punkte (max. −12), „Hype schon gelaufen“ zusätzlich −10.
Ab **60 Punkten** wird der beste Coin Favorit, darunter heißt es „kein überzeugender Coin – keine Kaufempfehlung“.
Alle Schwellen stehen in `memecoin_bot/config.yaml` und lassen sich ändern.

## Ehrliche Grenzen
- **„Smart Money“** misst der Bot über große Trades (> 500 $ bzw. > 5.000 $). Benannte Profi-Wallets
  (wie bei Nansen oder GMGN) kennt er nicht – dafür gibt es keine kostenlose Schnittstelle.
- **Trust-Wallet-Swap:** Alle vier Chains unterstützt Trust Wallet. Ob ein bestimmter Coin direkt im Swap-Menü auftaucht,
  lässt sich nicht per API prüfen. Falls nicht, nennt der Bot den Aggregator (z. B. Jupiter) für den dApp-Browser.
- **Gebühren** in den Szenarien sind Schätzungen (Kauf der Kryptowährung per Karte ~2 %, Swap ~1 %, Slippage aus der Liquidität).
  Die echten Kosten zeigt die Swap-Vorschau in Trust Wallet.
- **Rate-Limits:** GeckoTerminal erlaubt ohne Key ca. 30 Anfragen pro Minute. Bei Überlastung wartet der Bot automatisch,
  dann dauert ein Scan länger.
- **Momentaufnahme:** Memecoin-Daten ändern sich in Minuten. Vor jedem Kauf neu `/check`en.
- Auf **TikTok** über einen Coin sprechen, den du selbst hältst? Position offenlegen und nicht erst kaufen und dann pushen
  (Marktmanipulation/„Scalping“).

## Dateien

```
memecoin_bot/
  __main__.py      Befehle: bot, scan, check, demo, github
  github_reply.py  GitHub-Modus: Befehl aus Issue-Kommentar -> Antwort-Kommentar
  telegram_bot.py  Telegram (Long-Polling, Warteschlange, Zugriffsschutz)
  scanner.py       Ablauf: sammeln → filtern → Tiefenprüfung → bewerten
  sources.py       DexScreener, GeckoTerminal, RugCheck, GoPlus, Honeypot.is (Rate-Limit, Cache, Retries)
  analysis.py      Kennzahlen, Red Flags, Score (ohne Netzwerk, gut testbar)
  scenarios.py     Investment-Szenarien inkl. Kosten und Slippage
  report.py        deutsche Telegram-Nachrichten
  demo.py          erfundene Test-Tokens (für demo und Tests)
  config.yaml      alle Schwellenwerte
  tests/           pytest
```
