"""HTML- und Markdown-Report inkl. TikTok-Hooks."""
from __future__ import annotations

import html
from collections import Counter
from datetime import datetime
from pathlib import Path

from .analysis import HORIZONS, SESSION_INFO, SESSIONS, WEEKDAYS, Profile


def _de(s: str) -> str:
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def money(v) -> str:
    if v is None:
        return "–"
    sign = "-" if v < 0 else ""
    v = abs(v)
    for div, suf in ((1e9, " Mrd. $"), (1e6, " Mio. $"), (1e3, " Tsd. $")):
        if v >= div:
            return sign + _de(f"{v / div:,.1f}") + suf
    return sign + _de(f"{v:,.0f}") + " $"


def pct(v, sign=True) -> str:
    return "–" if v is None else _de(f"{v * 100:{'+' if sign else ''}.1f}") + " %"


def hours_txt(h) -> str:
    if h is None:
        return "–"
    if h < 1:
        return f"{h * 60:.0f} Min."
    return _de(f"{h:.1f}") + " Std." if h < 48 else _de(f"{h / 24:.1f}") + " Tage"


def _lev(v) -> str:
    return "–" if v is None else f"{v:.1f}x".replace(".", ",")


def hooks(res: dict) -> list[str]:
    o: Profile = res["overall"]
    out = []
    n = len(res["profiles"])
    if sum(o.hour_long.values()) >= 10:
        h, c = o.hour_long.most_common(1)[0]
        out.append(f"Die {n} besten Krypto-Trader eröffnen die meisten Longs um {h} Uhr deutscher Zeit "
                   f"({c / sum(o.hour_long.values()):.0%} aller Long-Einstiege in dieser Stunde).")
    if sum(o.hour_short.values()) >= 10:
        h, _ = o.hour_short.most_common(1)[0]
        out.append(f"Shorts dagegen am häufigsten um {h} Uhr.")
    if o.session_open:
        s, c = o.session_open.most_common(1)[0]
        out.append(f"{c / sum(o.session_open.values()):.0%} aller Einstiege passieren während der {s}-Session.")
    if o.weekend_share is not None:
        ws = o.weekend_share
        out.append(f"Am Wochenende passieren nur {ws:.0%} der Trades – die Profis machen Pause." if ws < 2 / 7 * 0.8
                   else f"Krypto schläft nie: {ws:.0%} der Trades fallen aufs Wochenende.")
    if o.median_hold is not None:
        out.append(f"Ein Trade der Profis dauert im Median nur {hours_txt(o.median_hold)} – dann sind sie wieder raus.")
    if o.long_ratio is not None:
        out.append(f"{o.long_ratio:.0%} ihrer Einstiege sind Longs, {1 - o.long_ratio:.0%} Shorts.")
    for s in res["sentiment"][:1]:
        if s["n_long"] + s["n_short"] >= 3:
            side, share = ("long", s["long_share"]) if s["long_share"] >= 0.5 else ("short", 1 - s["long_share"])
            out.append(f"Gerade sind die Top-Trader zu {share:.0%} {side} auf {s['coin']} – Positionen im Wert von {money(s['total'])}.")
    best = max((p for p in res["profiles"] if p.info), key=lambda p: p.info.pnl_month, default=None)
    if best and best.info.pnl_month > 0:
        wr = f" bei {best.win_rate:.0%} Trefferquote" if best.win_rate is not None else ""
        out.append(f"{best.name} hat in 30 Tagen {money(best.info.pnl_month)} Gewinn gemacht{wr}.")
    c24 = o.copy.get(24)
    if c24 and len(c24) >= 10:
        out.append(f"Hättest du alle Einstiege {res['delay_min']} Minuten später kopiert, lagst du nach 24 Std. im Schnitt bei "
                   f"{pct(o.copy_avg(24))} – Trefferquote {o.copy_hit(24):.0%}.")
    return out


def _bars(counter: Counter, order: list, color: str, height=120) -> str:
    m = max(counter.values(), default=0) or 1
    cells = "".join(
        f'<div class="bar"><b>{counter.get(k, 0) or ""}</b><div class="fill" style="height:{counter.get(k, 0) / m * 100:.0f}%;background:{color}"></div>'
        f'<span>{html.escape(str(k))}</span></div>' for k in order)
    return f'<div class="bars" style="height:{height}px">{cells}</div>'


def _timing(p: Profile, title: str, tz: str) -> str:
    hrs = list(range(24))
    return (f"<h3>{html.escape(title)}</h3><div class='grid'>"
            f"<div><h4>Long-Einstiege nach Uhrzeit ({html.escape(tz)})</h4>{_bars(p.hour_long, hrs, 'var(--buy)')}</div>"
            f"<div><h4>Short-Einstiege nach Uhrzeit</h4>{_bars(p.hour_short, hrs, 'var(--sell)')}</div>"
            f"<div><h4>Schließen (Gewinnmitnahme/Stop) nach Uhrzeit</h4>{_bars(p.hour_close, hrs, 'var(--acc)')}</div>"
            f"<div><h4>Einstiege nach Wochentag</h4>{_bars(p.weekday_open, WEEKDAYS, 'var(--buy)')}</div>"
            f"<div><h4>Ausstiege nach Wochentag</h4>{_bars(p.weekday_close, WEEKDAYS, 'var(--acc)')}</div>"
            f"<div><h4>Einstiege nach Session</h4>{_bars(p.session_open, SESSIONS, 'var(--acc)')}"
            f"<p class='mut small'>{SESSION_INFO}</p></div></div>")


COLS = ["Trader", "30T-Gewinn", "Konto", "Orders", "Long-Quote", "Trefferquote", "Profit-Faktor", "Ø Haltedauer",
        "Lieblings-Uhrzeit", "Lieblings-Tag", "Wochenende", "Top-Coins"] + [f"Kopiert +{h}h" for h in HORIZONS]


def _row(p: Profile) -> list[str]:
    return [p.name, money(p.info.pnl_month) if p.info else "–", money(p.info.account_value) if p.info else "–",
            str(p.orders), pct(p.long_ratio, False), pct(p.win_rate, False),
            "–" if p.profit_factor is None else f"{p.profit_factor:.2f}".replace(".", ","), hours_txt(p.median_hold),
            "–" if p.fav_open_hour is None else f"{p.fav_open_hour} Uhr", p.fav_weekday or "–", pct(p.weekend_share, False),
            ", ".join(c for c, _ in p.coins.most_common(3))] + [pct(p.copy_avg(h)) for h in HORIZONS]


CSS = """
:root{--bg:#fafaf7;--fg:#1d1d1f;--mut:#6b6b70;--card:#fff;--line:#e4e4e0;--buy:#1f9d55;--sell:#d64545;--acc:#3b6fd8}
@media (prefers-color-scheme:dark){:root{--bg:#121214;--fg:#ececee;--mut:#9a9aa2;--card:#1c1c20;--line:#2c2c32;--buy:#3cc47c;--sell:#ef6b6b;--acc:#7aa2ff}}
body{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;margin:0;padding:24px 16px}
main{max-width:1200px;margin:auto}h1{margin:0 0 4px}.mut{color:var(--mut)}.small{font-size:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 20px;margin:16px 0;overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:13px}td,th{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:18px}
.bars{display:flex;gap:2px;align-items:flex-end}.bar{flex:1;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;height:100%;font-size:9px;min-width:0}
.fill{width:100%;border-radius:2px 2px 0 0;min-height:1px}.bar span{color:var(--mut);margin-top:2px}.bar b{font-weight:500;color:var(--mut)}
.warn{border-left:4px solid var(--sell)}.hook li{margin:6px 0}.tag{display:inline-block;padding:1px 8px;border-radius:9px;background:var(--line);font-size:12px;vertical-align:middle}
.meter{height:8px;border-radius:4px;background:var(--sell);overflow:hidden;min-width:120px}.meter div{height:100%;background:var(--buy)}
"""


def write_reports(res: dict, signals: list, bt: dict | None, out_dir: Path, demo=False, positions_time=None) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    ps: list[Profile] = res["profiles"]
    o: Profile = res["overall"]
    hk = hooks(res)
    tz = res["tz"]
    h = [f"<!doctype html><html lang='de'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
         f"<title>Crypto-Tracker Report</title><style>{CSS}</style></head><body><main>",
         f"<h1>Crypto-Tracker {'<span class=tag>DEMO – fiktive Daten</span>' if demo else ''}</h1>"
         f"<p class='mut'>{len(ps)} Top-Trader · {o.orders} Orders · Uhrzeiten in {html.escape(tz)} · erstellt {stamp}</p>",
         "<div class='card warn'><b>Keine Anlageberatung.</b> Hohe Gewinne der Vergangenheit sagen nichts über die Zukunft. "
         "Perpetual Futures mit Hebel können zum Totalverlust führen. Der Bot handelt nur mit Spielgeld (Paper-Trading).</div>"]
    if hk:
        h.append("<div class='card hook'><h2>🎬 TikTok-Hooks</h2><ul>" + "".join(f"<li>{html.escape(x)}</li>" for x in hk) + "</ul></div>")
    if res["sentiment"]:
        h.append(f"<div class='card'><h2>Smart Money: So sind die Top-Trader jetzt positioniert</h2>"
                 f"<p class='mut small'>Stand: {html.escape(str(positions_time or stamp))}</p><table><tr><th>Coin</th><th>Long / Short</th>"
                 "<th>Long-Anteil</th><th>Trader long/short</th><th>Volumen</th><th>Ø Hebel</th><th>Offener G/V</th></tr>"
                 + "".join(f"<tr><td><b>{html.escape(s['coin'])}</b></td><td><div class='meter'><div style='width:{s['long_share'] * 100:.0f}%'></div></div></td>"
                           f"<td>{pct(s['long_share'], False)}</td><td>{s['n_long']} / {s['n_short']}</td><td>{money(s['total'])}</td>"
                           f"<td>{_lev(s['avg_lev'])}</td><td>{money(s['upnl'])}</td></tr>"
                           for s in res["sentiment"][:15]) + "</table></div>")
    h.append("<div class='card'><h2>Die Top-Trader</h2><table><tr>" + "".join(f"<th>{c}</th>" for c in COLS) + "</tr>"
             + "".join("<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in _row(p)) + "</tr>" for p in ps)
             + f"</table><p class='mut small'>Kopiert +Xh = Ø Ergebnis, wenn man jeden Einstieg {res['delay_min']} Min. später in dieselbe Richtung "
               "kopiert und X Stunden hält (ohne Gebühren/Funding). Trefferquote = Anteil der Schließ-Orders mit Gewinn.</p></div>")
    h.append("<div class='card'>" + _timing(o, "Timing aller Top-Trader zusammen", tz) + "</div>")
    if signals:
        h.append("<div class='card'><h2>Aktuelle Konsens-Signale</h2><table><tr><th>Coin</th><th>Richtung</th><th>Score</th><th>Volumen</th><th>Zeitraum (UTC)</th><th>Trader</th></tr>"
                 + "".join(f"<tr><td><b>{html.escape(s.coin)}</b></td><td style='color:var({'--buy' if s.direction > 0 else '--sell'})'>{s.side}</td><td>{s.score}</td>"
                           f"<td>{money(s.notional)}</td><td>{s.first:%d.%m. %H:%M} – {s.last:%H:%M}</td><td style='white-space:normal'>{html.escape(', '.join(s.traders))}"
                           f"{' · dagegen: ' + html.escape(', '.join(s.against)) if s.against else ''}</td></tr>" for s in signals[:15]) + "</table></div>")
    else:
        h.append("<div class='card'><h2>Aktuelle Konsens-Signale</h2><p class='mut'>Gerade kein Signal: In den letzten 24 Std. sind nicht genug "
                 "Top-Trader gleichzeitig in dieselbe Richtung eingestiegen.</p></div>")
    if bt and bt.get("n"):
        h.append(f"<div class='card'><h2>Backtest: Konsens-Signale kopieren</h2><p>{bt['n']} simulierte Trades (ab {bt['min_traders']} Tradern in dieselbe Richtung, "
                 f"{bt['hold_hours']} Std. gehalten): Ø <b>{pct(bt['avg'])}</b>, Trefferquote <b>{pct(bt['win_rate'], False)}</b>, "
                 f"bester {pct(bt['best'])}, schlechtester {pct(bt['worst'])}. Ohne Hebel, Gebühren und Funding.</p></div>")
    for p in ps[:8]:
        if p.orders >= 10:
            h.append("<div class='card'>" + _timing(p, f"Timing: {p.name}", tz) + "</div>")
    h.append("</main></body></html>")
    hp = out_dir / "report.html"
    hp.write_text("".join(h), encoding="utf-8")

    md = [f"# Crypto-Tracker Report{' (DEMO – fiktive Daten)' if demo else ''}",
          f"_{len(ps)} Top-Trader · {o.orders} Orders · Uhrzeiten in {tz} · erstellt {stamp}_", "",
          "> Keine Anlageberatung. Nur Paper-Trading.", ""]
    if hk:
        md += ["## TikTok-Hooks", *[f"- {x}" for x in hk], ""]
    if res["sentiment"]:
        md += ["## Smart-Money-Positionierung", "| Coin | Long-Anteil | Trader long/short | Volumen |", "|---|---|---|---|",
               *[f"| {s['coin']} | {pct(s['long_share'], False)} | {s['n_long']}/{s['n_short']} | {money(s['total'])} |" for s in res["sentiment"][:10]], ""]
    md += ["## Top-Trader", "| " + " | ".join(COLS) + " |", "|" + "---|" * len(COLS), *["| " + " | ".join(_row(p)) + " |" for p in ps]]
    if signals:
        md += ["", "## Konsens-Signale", *[f"- **{s.side} {s.coin}** (Score {s.score}): {', '.join(s.traders)}" for s in signals[:15]]]
    if bt and bt.get("n"):
        md += ["", f"## Backtest\n{bt['n']} Trades, Ø {pct(bt['avg'])}, Trefferquote {pct(bt['win_rate'], False)}"]
    mp = out_dir / "report.md"
    mp.write_text("\n".join(md) + "\n", encoding="utf-8")
    return hp, mp
