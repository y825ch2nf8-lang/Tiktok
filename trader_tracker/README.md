# Trader-Tracker 📈

Verfolgt die **öffentlich gemeldeten Trades** der bekanntesten Investoren und von Firmen-Insidern
und analysiert, **wann** sie kaufen und verkaufen: Wochentag, Monat, Monatsphase, Quartal
und die Uhrzeit, zu der der Trade öffentlich wurde. Daraus entstehen Signale, ein Backtest
(„Hätte sich Kopieren gelohnt?“) und fertige **TikTok-Hooks**.

> ⚠️ **Keine Anlageberatung.** Der Bot führt **keine echten Orders** aus (nur Paper-Trading).
> Die Meldungen kommen verzögert: Form 4 nach etwa 2 Tagen, 13F bis zu 45 Tage nach Quartalsende.

## Datenquellen (alle offiziell und kostenlos)

| Quelle | Wer | Genauigkeit |
|---|---|---|
| **SEC 13F** | Fonds: Buffett, Burry, Ackman, Druckenmiller, Tepper … | nur Quartal, Käufe aus Depot-Differenz |
| **SEC Form 4** | CEOs, CFOs, Vorstände (z.B. NVDA, TSLA, AAPL) | **exaktes Datum** + Uhrzeit der Meldung |
| **CSV-Import** | z.B. US-Politiker (Export von Capitol Trades/Quiver) oder eigene Listen | je nach Quelle |
| Yahoo Finance | Kurse für die Performance-Analyse | täglich |

Die Timing-Analyse (Wochentag/Monat) nutzt **nur Trades mit exaktem Datum**. 13F-Daten fließen in
Konsens und Signale ein.

## Schnellstart

```bash
pip install -r requirements.txt

# 1) Ohne Internet ausprobieren (fiktive Daten)
python -m trader_tracker demo
#  -> output/trader_report/demo/report.html

# 2) Echte Daten: SEC_USER_AGENT in .env eintragen (Name + E-Mail, Pflicht laut SEC)
python -m trader_tracker fetch       # lädt 13F + Form 4 laut traders.yaml
python -m trader_tracker report      # Analyse, Signale, Backtest -> output/trader_report/report.html
python -m trader_tracker signals     # Signale im Terminal
```

Politiker-Trades oder eigene Daten importieren:

```bash
python -m trader_tracker import-csv trades.csv --group Politiker
```
Spalten: `trader,ticker,side,trade_date` (Pflicht) sowie optional `shares,price,value,filed_at,issuer,group,note`.
Für `side` gehen `BUY/SELL`, `Kauf/Verkauf`, `purchase/sale`. Als Datum gehen `2025-01-15`, `15.01.2025` und `01/15/2025`.

## Wen verfolgen? → `traders.yaml`

Trage Fonds per CIK ein (zu finden über die [EDGAR-Suche](https://www.sec.gov/cgi-bin/browse-edgar?type=13F-HR))
und Firmen, deren Insider du beobachten willst, per Ticker. Mit `weight` steuerst du, wie stark ein
Trader in die Signale eingeht.

## Was steht im Report?

- **Trader-Übersicht:** Käufe/Verkäufe, Kaufquote, Ø Tradegröße, Lieblingstag für Kauf/Verkauf,
  stärkstes Kauf-Quartal, Top-Aktien, Meldeverzug, Kursentwicklung 5/20/60 Handelstage **nach Bekanntwerden**
- **Timing-Charts:** Wochentag, Monat, Monatsanfang/-mitte/-ende, Uhrzeit der Veröffentlichung
- **Konsens:** Aktien, die mehrere Profis gleichzeitig kaufen
- **Insider-Cluster:** Mehrere Insider derselben Firma kaufen innerhalb von 30 Tagen
- **Signale + Backtest:** simuliert „Signal kopieren, 60 Tage halten“ gegen den SPY,
  und zwar ab dem Tag, an dem der Trade öffentlich war (ohne Blick in die Zukunft)
- **🎬 TikTok-Hooks:** fertige Aufhänger-Sätze aus den Zahlen

## Tests

```bash
python -m pytest trader_tracker/tests -q
```
