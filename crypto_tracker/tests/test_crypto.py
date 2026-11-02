from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from crypto_tracker.analysis import analyze, build_profile, holding_times, sentiment
from crypto_tracker.demo import make_demo
from crypto_tracker.hyperliquid import (CandleCache, HyperliquidClient, forward_return, parse_leaderboard,
                                        rank_traders)
from crypto_tracker.models import (CLOSE_LONG, OPEN_LONG, OPEN_SHORT, Fill, Order, Position, TraderInfo,
                                   action_from_dir, aggregate, dt_to_ms)
from crypto_tracker.paper import PaperBook
from crypto_tracker.report import write_reports
from crypto_tracker.signals import backtest, consensus

T0 = datetime(2026, 3, 2, 14, 0, tzinfo=timezone.utc)  # Montag 15 Uhr in Berlin
ADDR = "0xabc0000000000000000000000000000000000001"


def api_fill(t, coin="BTC", side="B", px="100", sz="1", dir_="Open Long", pnl="0", oid=1, tid=1, start="0"):
    return {"coin": coin, "px": px, "sz": sz, "side": side, "time": dt_to_ms(t), "startPosition": start, "dir": dir_,
            "closedPnl": pnl, "hash": "0x", "oid": oid, "crossed": True, "fee": "0.01", "tid": tid, "feeToken": "USDC"}


class FakeResp:
    def __init__(self, data, status=200):
        self.data, self.status_code = data, status

    def json(self):
        return self.data

    def raise_for_status(self):
        pass


class FakeSession:
    def __init__(self, handler):
        self.handler, self.calls = handler, []

    def post(self, url, json=None, timeout=None):
        self.calls.append(json)
        return FakeResp(self.handler(json))

    def get(self, url, timeout=None):
        return FakeResp(self.handler({"type": "GET", "url": url}))


def test_action_mapping():
    assert action_from_dir("Open Long", "B") == OPEN_LONG
    assert action_from_dir("Long > Short", "A") == OPEN_SHORT
    assert action_from_dir("Liquidated Isolated Long", "A") == CLOSE_LONG


def test_fill_from_api_and_aggregate():
    fs = [Fill.from_api(ADDR, api_fill(T0, px="100", sz="1", tid=1)),
          Fill.from_api(ADDR, api_fill(T0 + timedelta(seconds=1), px="102", sz="1", tid=2, start="1"))]
    (o,) = aggregate(fs)
    assert o.action == OPEN_LONG and o.sz == 2 and o.px == 101 and o.n_fills == 2


def test_fills_pagination(tmp_path):
    pages = [[api_fill(T0 + timedelta(minutes=i), tid=i, oid=i) for i in range(2000)],
             [api_fill(T0 + timedelta(minutes=3000), tid=9999, oid=9999)]]
    sess = FakeSession(lambda p: pages.pop(0))
    c = HyperliquidClient(tmp_path, min_interval=0, session=sess)
    fills = c.fills(ADDR, T0 - timedelta(days=1))
    assert len(fills) == 2001
    assert sess.calls[1]["startTime"] == dt_to_ms(T0 + timedelta(minutes=1999)) + 1


def test_positions_and_mids(tmp_path):
    state = {"marginSummary": {"accountValue": "50000"}, "assetPositions": [
        {"type": "oneWay", "position": {"coin": "ETH", "szi": "-2.5", "entryPx": "3000", "positionValue": "7600",
                                        "unrealizedPnl": "-100", "leverage": {"type": "cross", "value": 10}}}]}
    c = HyperliquidClient(tmp_path, 0, FakeSession(lambda p: state if p["type"] == "clearinghouseState" else {"ETH": "3040"}))
    acct, pos = c.positions(ADDR)
    assert acct == 50000 and pos[0].size == -2.5 and pos[0].leverage == 10 and not pos[0].is_long
    assert c.mids() == {"ETH": 3040.0}


def test_leaderboard_ranking_filters_market_makers():
    def row(addr, acct, pm, pa, roi, vlm):
        perf = {"pnl": str(pm), "roi": str(roi), "vlm": str(vlm)}
        return {"ethAddress": addr, "accountValue": str(acct), "displayName": None, "prize": 0,
                "windowPerformances": [["day", perf], ["week", perf], ["month", perf],
                                       ["allTime", {"pnl": str(pa), "roi": "1", "vlm": "1"}]]}
    rows = [row("0xgood1", 1e6, 1e5, 5e5, 0.1, 5e6), row("0xgood2", 5e5, 2e5, 1e6, 0.4, 1e7),
            row("0xmm", 1e6, 1e5, 1e6, 0.1, 9e9),          # Market-Maker: riesiger Umsatz
            row("0xsmall", 500, 400, 600, 0.8, 1e4),         # zu kleines Konto
            row("0xloser", 1e6, -1e5, 1e5, -0.1, 5e6)]       # Monat im Minus
    top = rank_traders(parse_leaderboard(rows), top=10)
    assert [t.address for t in top] == ["0xgood2", "0xgood1"]


def test_holding_time_and_profile():
    fills = [Fill(ADDR, "BTC", "B", 100, 1, T0, "Open Long", 0, 1, 1, 0, 0.0),
             Fill(ADDR, "BTC", "A", 110, 1, T0 + timedelta(hours=5), "Close Long", 10, 2, 2, 0, 1.0)]
    assert holding_times(fills) == [5.0]
    p = build_profile(ADDR, fills, None, ZoneInfo("Europe/Berlin"))
    assert p.hour_long == {15: 1} and p.wins == 1 and p.fav_weekday == "Mo" and p.median_hold == 5.0


def test_forward_return_and_copy_direction():
    series = [(T0 + timedelta(hours=i), 100 + i) for i in range(48)]
    assert abs(forward_return(series, T0 + timedelta(minutes=5), 4) - (105 / 101 - 1)) < 1e-12
    fills = [Fill(ADDR, "BTC", "A", 100, 1, T0, "Open Short", 0, 1, 1, 0, 0.0)]
    p = build_profile(ADDR, fills, None, ZoneInfo("UTC"), CandleCache(None, T0, T0, {"BTC": series}), 5)
    assert p.copy[4][0] < 0  # Short in steigendem Markt kopiert = Verlust


def test_consensus_no_lookahead():
    orders = [Order(f"0x{i}", "SOL", OPEN_LONG, T0 + timedelta(hours=i), 1, 1, 1000, 0, 0, 1) for i in range(3)]
    assert consensus(orders, T0 + timedelta(hours=1)) == []
    s = consensus(orders, T0 + timedelta(hours=3))
    assert s[0].coin == "SOL" and s[0].direction == 1 and len(s[0].traders) == 3


def test_sentiment():
    pos = [Position("a", "BTC", 1, 1, 300, 0, 5), Position("b", "BTC", -1, 1, 100, 0, 10)]
    (s,) = sentiment(pos)
    assert s["long_share"] == 0.75 and s["n_long"] == 1 and s["avg_lev"] == 7.5


def test_paper_book(tmp_path):
    b = PaperBook(tmp_path / "p.json", size_usd=100, fee_rate=0)
    b.on_order(Order(ADDR, "BTC", OPEN_LONG, T0, 100, 1, 100, 0, 0, 1), "X", {"BTC": 100})
    b.on_order(Order(ADDR, "BTC", CLOSE_LONG, T0, 110, 1, 110, 10, 0, 1), "X", {"BTC": 110})
    b.save()
    assert abs(PaperBook(tmp_path / "p.json").summary({})["realized"] - 10) < 1e-9


def test_demo_end_to_end(tmp_path):
    fills_by, infos, positions, prices = make_demo(days=40)
    cc = CandleCache(None, None, None, prices)
    res = analyze(fills_by, infos, "Europe/Berlin", cc, 5, positions)
    assert res["overall"].orders > 100
    bt = backtest(res["orders"], cc, min_traders=2)
    h, m = write_reports(res, [], bt, tmp_path, demo=True)
    assert "DEMO" in h.read_text() and "TikTok-Hooks" in m.read_text()
