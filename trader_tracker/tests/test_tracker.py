from datetime import date, datetime, timedelta

from trader_tracker.analysis import analyze, insider_clusters
from trader_tracker.csv_import import import_csv
from trader_tracker.demo import make_demo
from trader_tracker.f13 import diff_holdings, parse_info_table
from trader_tracker.form4 import parse_form4
from trader_tracker.models import BUY, SELL, Trade
from trader_tracker.prices import StaticPrices, forward_return
from trader_tracker.report import money, write_reports
from trader_tracker.signals import backtest, build_signals

FORM4 = """<?xml version="1.0"?>
<ownershipDocument>
 <issuer><issuerCik>1</issuerCik><issuerName>Acme Corp</issuerName><issuerTradingSymbol>acme</issuerTradingSymbol></issuer>
 <reportingOwner><reportingOwnerId><rptOwnerName>DOE JANE</rptOwnerName></reportingOwnerId>
  <reportingOwnerRelationship><isOfficer>1</isOfficer><officerTitle>CEO</officerTitle></reportingOwnerRelationship></reportingOwner>
 <nonDerivativeTable>
  <nonDerivativeTransaction><transactionDate><value>2025-03-04</value></transactionDate>
   <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
   <transactionAmounts><transactionShares><value>1000</value></transactionShares>
   <transactionPricePerShare><value>12.5</value></transactionPricePerShare></transactionAmounts></nonDerivativeTransaction>
  <nonDerivativeTransaction><transactionDate><value>2025-03-05</value></transactionDate>
   <transactionCoding><transactionCode>M</transactionCode></transactionCoding>
   <transactionAmounts><transactionShares><value>50</value></transactionShares></transactionAmounts></nonDerivativeTransaction>
 </nonDerivativeTable>
</ownershipDocument>"""

INFO = """<informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">
<infoTable><nameOfIssuer>APPLE INC</nameOfIssuer><cusip>037833100</cusip><value>{a}</value>
<shrsOrPrnAmt><sshPrnamt>{an}</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt></infoTable>
{extra}</informationTable>"""


def test_parse_form4_only_open_market():
    t = parse_form4(FORM4, datetime(2025, 3, 6, 16, 30))
    assert len(t) == 1
    assert (t[0].ticker, t[0].side, t[0].value, t[0].trader) == ("ACME", BUY, 12500, "Doe Jane (CEO)")
    assert t[0].filing_delay_days == 2


def test_13f_diff():
    q1 = parse_info_table(INFO.format(a=1000, an=100, extra=""))
    q2 = parse_info_table(INFO.format(a=3000, an=200, extra="<infoTable><nameOfIssuer>X</nameOfIssuer><cusip>999</cusip>"
                                      "<value>10</value><shrsOrPrnAmt><sshPrnamt>1</sshPrnamt></shrsOrPrnAmt></infoTable>"))
    tr = diff_holdings(q1, q2, "Fund", date(2025, 6, 30), None, "Superinvestor")
    notes = sorted(t.note for t in tr)
    assert notes == ["Aufgestockt +100%", "Neue Position"]
    assert all(t.date_precision == "quarter" for t in tr)
    sold = diff_holdings(q2, q1, "Fund", date(2025, 9, 30), None, "S")
    assert {t.note for t in sold} == {"Reduziert -50%", "Komplett verkauft"}


def test_csv_import(tmp_path):
    f = tmp_path / "c.csv"
    f.write_text("trader,ticker,side,trade_date,value\nX,nvda,Kauf,15.01.2025,\"$15,000\"\nY,AAPL,sale,2025-01-16,\n")
    t = import_csv(f)
    assert [(x.ticker, x.side, x.value) for x in t] == [("NVDA", BUY, 15000.0), ("AAPL", SELL, None)]


def test_timing_excludes_quarter_precision():
    trades = [Trade("A", "T", BUY, date(2025, 3, 4), "form4"),  # Dienstag
              Trade("F", "T", BUY, date(2025, 3, 31), "13f", date_precision="quarter")]
    res = analyze(trades)
    assert dict(res["overall"].weekday[BUY]) == {"Di": 1}


def test_no_lookahead_in_signals():
    d = date(2025, 1, 10)
    trades = [Trade(n, "T", BUY, d, "form4", group="Insider", filed_at=datetime(2025, 1, 20)) for n in "AB"]
    assert build_signals(trades, as_of=date(2025, 1, 15)) == []
    assert build_signals(trades, as_of=date(2025, 1, 21))[0].ticker == "T"
    assert insider_clusters(trades)[0]["insiders"] == ["A", "B"]


def test_forward_return():
    s = [(date(2025, 1, 1) + timedelta(days=i), 100 + i) for i in range(10)]
    assert abs(forward_return(s, date(2025, 1, 1), 5) - 0.05) < 1e-9
    assert forward_return(s, date(2025, 1, 8), 5) is None


def test_demo_end_to_end(tmp_path):
    trades, prices = make_demo()
    p = StaticPrices(prices)
    res = analyze(trades, p)
    h, m = write_reports(res, build_signals(trades), backtest(trades, p), tmp_path, demo=True)
    assert "DEMO" in h.read_text() and "TikTok-Hooks" in m.read_text()


def test_money():
    assert money(1_234_000) == "1,2 Mio. $"
    assert money(950) == "950 $"
