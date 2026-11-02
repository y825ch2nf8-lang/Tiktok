"""Erzeugt einen HTML- und Markdown-Report inkl. TikTok-Hooks aus den Ergebnissen."""
from __future__ import annotations

import html
from collections import Counter
from datetime import datetime
from pathlib import Path

from .analysis import HORIZONS, MONTHS, WEEKDAYS, TraderStats, summary_numbers
from .models import BUY, SELL

DAYNAME = {"Mo": "Montag", "Di": "Dienstag", "Mi": "Mittwoch", "Do": "Donnerstag", "Fr": "Freitag"}


def money(v) -> str:
    if v is None:
        return "–"
    for div, suf in ((1e9, " Mrd. $"), (1e6, " Mio. $"), (1e3, " Tsd. $")):
        if abs(v) >= div:
            return _de(f"{v / div:,.1f}") + suf
    return _de(f"{v:,.0f}") + " $"


def _de(num: str) -> str:
    return num.replace(",", "X").replace(".", ",").replace("X", ".")


def pct(v) -> str:
    return "–" if v is None else f"{v * 100:+.1f} %".replace(".", ",")


def hooks(res: dict) -> list[str]:
    """Kurze, faktenbasierte Aufhänger für Erklär-Videos."""
    out = []
    ov = res["overall"]
    wb, ws = ov.weekday[BUY], ov.weekday[SELL]
    if sum(wb.values()) >= 5:
        d, n = wb.most_common(1)[0]
        out.append(f"Die beobachteten Profis kaufen am liebsten am {DAYNAME.get(d, d)}: {n / sum(wb.values()):.0%} aller Käufe fielen auf diesen Tag.")
    if sum(ws.values()) >= 5:
        d, n = ws.most_common(1)[0]
        out.append(f"Verkauft wird dagegen vor allem am {DAYNAME.get(d, d)} – {n} von {sum(ws.values())} Verkäufen.")
    if ov.filing_delays:
        late = sum(1 for x in ov.filing_delays if x > 2)
        out.append(f"Du erfährst von den Trades im Schnitt erst {sorted(ov.filing_delays)[len(ov.filing_delays)//2]} Tage später"
                   + (f" – {late} Meldungen kamen sogar nach über 2 Tagen." if late else "."))
    for c in res["consensus"][:2]:
        if len(c["buyers"]) >= 2:
            out.append(f"{len(c['buyers'])} verschiedene Profis haben zuletzt {c['label']} gekauft: {', '.join(c['buyers'][:3])}.")
    for c in res["clusters"][:1]:
        out.append(f"{len(c['insiders'])} Insider von {c['ticker']} kauften innerhalb weniger Tage eigene Aktien für {money(c['value'])}.")
    best = max((s for s in res["traders"].values() if len(s.fwd.get(20, [])) >= 3),
               key=lambda s: s.avg_return(20) or -9, default=None)
    if best:
        out.append(f"Wer {best.name} nach Bekanntwerden kopiert hätte, lag nach 1 Monat im Schnitt bei {pct(best.avg_return(20))} "
                   f"(Trefferquote {best.hit_rate(20):.0%}).")
    return out


def _bars(counter: Counter, order: list, color: str) -> str:
    m = max(counter.values(), default=0) or 1
    cells = []
    for k in order:
        v = counter.get(k, 0)
        cells.append(f'<div class="bar"><div class="fill" style="height:{v / m * 100:.0f}%;background:{color}" title="{v}"></div>'
                     f'<span>{html.escape(str(k))}</span><b>{v}</b></div>')
    return f'<div class="bars">{"".join(cells)}</div>'


def _timing_html(tp, title: str) -> str:
    phases = ["Monatsanfang (1.–10.)", "Monatsmitte (11.–20.)", "Monatsende (21.+)"]
    parts = [f"<h3>{html.escape(title)}</h3><div class='grid'>"]
    for side, color, name in ((BUY, "var(--buy)", "Käufe"), (SELL, "var(--sell)", "Verkäufe")):
        parts.append(f"<div><h4>{name} nach Wochentag</h4>{_bars(tp.weekday[side], WEEKDAYS[:5], color)}</div>")
        parts.append(f"<div><h4>{name} nach Monat</h4>{_bars(tp.month[side], MONTHS, color)}</div>")
        parts.append(f"<div><h4>{name} im Monatsverlauf</h4>{_bars(tp.month_phase[side], phases, color)}</div>")
    if tp.filing_hour:
        hrs = sorted(tp.filing_hour)
        parts.append(f"<div><h4>Uhrzeit der Veröffentlichung (EDGAR)</h4>{_bars(tp.filing_hour, list(range(hrs[0], hrs[-1] + 1)), 'var(--acc)')}</div>")
    parts.append("</div>")
    return "".join(parts)


def _trader_row(s: TraderStats) -> str:
    n = summary_numbers(s)
    t = s.timing
    cells = [s.name, s.group, f"{s.buys} / {s.sells}", f"{s.buy_ratio:.0%}", money(n["avg_trade"]),
             t.top(t.weekday[BUY]) or "–", t.top(t.weekday[SELL]) or "–", t.top(t.quarter[BUY]) or "–",
             ", ".join(k for k, _ in s.tickers_bought.most_common(3)) or "–",
             "–" if n["median_delay"] is None else f"{n['median_delay']:.0f} T"]
    cells += [pct(s.avg_return(h)) for h in HORIZONS]
    return "<tr>" + "".join(f"<td>{html.escape(str(c))}</td>" for c in cells) + "</tr>"


CSS = """
:root{--bg:#fafaf7;--fg:#1d1d1f;--mut:#6b6b70;--card:#fff;--line:#e4e4e0;--buy:#1f9d55;--sell:#d64545;--acc:#3b6fd8}
@media (prefers-color-scheme:dark){:root{--bg:#141416;--fg:#ececee;--mut:#9a9aa2;--card:#1d1d21;--line:#2c2c32;--buy:#3cc47c;--sell:#ef6b6b;--acc:#6f9bff}}
body{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;margin:0;padding:24px 16px}
main{max-width:1150px;margin:auto}h1{margin:0 0 4px}.mut{color:var(--mut)}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 20px;margin:16px 0;overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:13px}td,th{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}
.bars{display:flex;gap:4px;align-items:flex-end;height:130px}.bar{flex:1;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;height:100%;font-size:10px}
.fill{width:100%;border-radius:3px 3px 0 0;min-height:1px}.bar span{color:var(--mut);margin-top:2px;white-space:nowrap}.bar b{font-weight:500}
.warn{border-left:4px solid var(--sell)}.hook li{margin:6px 0}.tag{display:inline-block;padding:1px 8px;border-radius:9px;background:var(--line);font-size:12px}
"""


def write_reports(res: dict, signals: list, bt: dict | None, out_dir: Path, demo: bool = False) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    traders = sorted(res["traders"].values(), key=lambda s: -(s.buys + s.sells))
    hk = hooks(res)

    head = ["Trader", "Gruppe", "Käufe / Verk.", "Kaufquote", "Ø Trade", "Kauf-Tag", "Verkauf-Tag",
            "Kauf-Quartal", "Top-Käufe", "Meldeverzug"] + [f"Ø nach {h} T" for h in HORIZONS]
    h = [f"<!doctype html><html lang='de'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
         f"<title>Trader-Tracker Report</title><style>{CSS}</style></head><body><main>",
         f"<h1>Trader-Tracker {'<span class=tag>DEMO – fiktive Daten</span>' if demo else ''}</h1>"
         f"<p class='mut'>{res['n']} Trades · {len(traders)} Trader · erstellt {stamp}</p>",
         "<div class='card warn'><b>Keine Anlageberatung.</b> Die Daten stammen aus Pflichtmeldungen und sind verzögert "
         "(Form 4: ~2 Tage, 13F: bis 45 Tage nach Quartalsende). 13F-Trades haben kein genaues Datum und fließen "
         "daher nicht in die Wochentags-Analyse ein. Vergangene Muster garantieren nichts.</div>"]
    if hk:
        h.append("<div class='card hook'><h2>🎬 TikTok-Hooks</h2><ul>" + "".join(f"<li>{html.escape(x)}</li>" for x in hk) + "</ul></div>")
    h.append("<div class='card'><h2>Trader-Übersicht</h2><table><tr>" + "".join(f"<th>{c}</th>" for c in head) + "</tr>"
             + "".join(_trader_row(s) for s in traders) + "</table>"
             "<p class='mut'>Ø nach X T = durchschnittliche Kursentwicklung X Handelstage nach Veröffentlichung eines Kaufs.</p></div>")
    h.append("<div class='card'>" + _timing_html(res["overall"], "Timing aller Trader (nur Trades mit genauem Datum)") + "</div>")
    if signals:
        h.append("<div class='card'><h2>Aktuelle Signale (Paper-Trading)</h2><table><tr><th>Aktie</th><th>Score</th><th>Bekannt seit</th><th>Begründung</th></tr>"
                 + "".join(f"<tr><td>{html.escape(s.label)}</td><td>{s.score}</td><td>{s.available}</td><td style='white-space:normal'>{html.escape(' · '.join(s.reasons))}</td></tr>" for s in signals[:15])
                 + "</table></div>")
    else:
        h.append("<div class='card'><h2>Aktuelle Signale (Paper-Trading)</h2><p class='mut'>Gerade kein Signal: "
                 "In den letzten 120 Tagen haben nicht genug verschiedene Profis dieselbe Aktie gekauft.</p></div>")
    if res["clusters"]:
        h.append("<div class='card'><h2>Insider-Cluster</h2><table><tr><th>Aktie</th><th>Zeitraum</th><th>Insider</th><th>Volumen</th></tr>"
                 + "".join(f"<tr><td>{c['ticker']}</td><td>{c['start']} – {c['end']}</td><td style='white-space:normal'>{html.escape(', '.join(c['insiders']))}</td><td>{money(c['value'])}</td></tr>" for c in res["clusters"][:10])
                 + "</table></div>")
    if bt and bt.get("n"):
        h.append(f"<div class='card'><h2>Backtest: Signale kopieren</h2><p>{bt['n']} simulierte Käufe, je {bt['hold_days']} Handelstage gehalten: "
                 f"Ø Rendite <b>{pct(bt['avg'])}</b>, Trefferquote <b>{bt['win_rate']:.0%}</b>, "
                 f"vs. {bt['benchmark']}: <b>{pct(bt['avg_excess'])}</b>. Ohne Gebühren/Steuern.</p></div>")
    for s in traders[:8]:
        if sum(s.timing.weekday[BUY].values()) + sum(s.timing.weekday[SELL].values()) >= 4:
            h.append("<div class='card'>" + _timing_html(s.timing, f"Timing: {s.name}") + "</div>")
    h.append("</main></body></html>")
    html_path = out_dir / "report.html"
    html_path.write_text("".join(h), encoding="utf-8")

    md = [f"# Trader-Tracker Report{' (DEMO – fiktive Daten)' if demo else ''}", f"_{res['n']} Trades · erstellt {stamp}_", "",
          "> Keine Anlageberatung. Daten sind verzögert; 13F-Trades haben kein genaues Datum.", ""]
    if hk:
        md += ["## TikTok-Hooks", *[f"- {x}" for x in hk], ""]
    md += ["## Trader", "| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for s in traders:
        n = summary_numbers(s)
        t = s.timing
        md.append("| " + " | ".join([s.name, s.group, f"{s.buys}/{s.sells}", f"{s.buy_ratio:.0%}", money(n["avg_trade"]),
                                     t.top(t.weekday[BUY]) or "–", t.top(t.weekday[SELL]) or "–", t.top(t.quarter[BUY]) or "–",
                                     ", ".join(k for k, _ in s.tickers_bought.most_common(3)) or "–",
                                     "–" if n["median_delay"] is None else f"{n['median_delay']:.0f} T",
                                     *[pct(s.avg_return(x)) for x in HORIZONS]]) + " |")
    if signals:
        md += ["", "## Signale", *[f"- **{s.label}** (Score {s.score}, seit {s.available}): {' · '.join(s.reasons)}" for s in signals[:15]]]
    if bt and bt.get("n"):
        md += ["", f"## Backtest\n{bt['n']} Trades, Ø {pct(bt['avg'])}, Trefferquote {bt['win_rate']:.0%}, vs. {bt['benchmark']} {pct(bt['avg_excess'])}"]
    md_path = out_dir / "report.md"
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")
    return html_path, md_path
