from datetime import datetime, timezone

import pytest

from memecoin_bot import report
from memecoin_bot.analysis import (Candidate, Deep, analyze, evm_security, ohlcv_metrics, prefilter, solana_security,
                                   whale_flow)
from memecoin_bot.demo import NOW_S, TOKENS, demo_scanner
from memecoin_bot.scanner import load_config
from memecoin_bot.scenarios import price_impact_pct, scenario
from memecoin_bot.sources import Http
from memecoin_bot.telegram_bot import Bot, parse_allowed

CFG = load_config()


@pytest.fixture(scope="module")
def demo_result():
    return demo_scanner(CFG).scan()


# ------------------------------------------------------------------------------------------- Scan Ende-zu-Ende

def test_demo_scan_picks_clean_favorite(demo_result):
    fav = demo_result.favorite(CFG["recommend"]["min_score"])
    assert fav is not None and fav.cand.symbol == "GOODCAT"
    assert [a.cand.symbol for a in demo_result.top][:2] == ["GOODCAT", "BASEBRO"]


def test_demo_scan_excludes_every_trap(demo_result):
    reasons = {a.cand.symbol: " ".join(a.red_flags) for a in demo_result.excluded}
    assert "Mint-Authority" in reasons["RUGDOG"]
    assert "HONEYPOT" in reasons["HONEYBEE"]
    assert "Wash-Trading" in reasons["WASHAPE"]
    assert "Zu jung" in reasons["BABYPUMP"]
    checked = {a.cand.symbol for a in demo_result.analyses}
    assert "NVDAc" not in checked          # tokenisierte Aktie, kein Meme
    assert "BIGDOGE" not in checked        # Market Cap zu groß
    assert demo_result.biggest_meme.symbol == "BIGDOGE"


def test_demo_market_prices(demo_result):
    m = demo_result.market
    assert m.native_usd["solana"] == pytest.approx(73.4)
    assert m.eur_usd == pytest.approx(1.16) and m.eur_usd_live


def test_check_single_token_without_chain():
    a, market = demo_scanner(CFG).check(TOKENS["BASEBRO"]["address"])
    assert a.cand.chain == "base" and not a.excluded
    a, _ = demo_scanner(CFG).check(TOKENS["RUGDOG"]["address"])
    assert a.excluded
    assert demo_scanner(CFG).check("So1111111111111111111111111111111111unknown") is None


# ------------------------------------------------------------------------------------------- Kennzahlen

def test_ohlcv_metrics_trend_and_change():
    day = 86_400
    rows = [[i * day, 1, 1.1, 0.9, c, v] for i, (c, v) in enumerate(zip(
        [1, 1, 1, 1, 1, 1, 1, 1.5, 1.8, 2.0], [100] * 7 + [300, 300, 300]))]
    m = ohlcv_metrics(rows)
    assert m["vol_trend"] == pytest.approx(3.0)
    assert m["chg7d"] == pytest.approx(1.0)
    assert m["swing_low"] == 1


def test_whale_flow_counts_big_trades():
    t = [{"kind": "buy", "volume_in_usd": "6000", "tx_from_address": "a"},
         {"kind": "buy", "volume_in_usd": "1000", "tx_from_address": "a"},
         {"kind": "sell", "volume_in_usd": "2000", "tx_from_address": "b"}]
    w = whale_flow(t)
    assert w["buy_usd"] == 7000 and w["sell_usd"] == 2000
    assert w["buyers"] == 1 and w["big_buys"] == 1 and w["big_sells"] == 0
    assert w["buy_share"] == pytest.approx(7 / 9)


def test_solana_security_ignores_pool_and_finds_cluster():
    supply = 1_000_000 * 10**6
    rc = {"token": {"supply": supply}, "mintAuthority": None, "freezeAuthority": None,
          "topHolders": [{"owner": "POOL", "pct": 30}, {"owner": "w1", "pct": 4}, {"owner": "w2", "pct": 3}],
          "insiderNetworks": [{"size": 4, "currentHolding": supply * 0.3}, {"size": 900, "currentHolding": supply}],
          "markets": [{"lp": {"lpLockedPct": 100}}], "knownAccounts": {}}
    s = solana_security(rc, {"POOL"})
    assert s["top1"] == 4 and s["top10"] == 7
    assert s["insider_cluster_pct"] == pytest.approx(30)
    assert s["bot_network_size"] == 900


def test_evm_security_flags():
    gp = {"is_honeypot": "0", "buy_tax": "0.1", "sell_tax": "0", "owner_address": "0xabc", "is_mintable": "1",
          "is_open_source": "1", "lp_holders": [{"address": "0x1", "percent": "0.3", "is_locked": 1}],
          "holders": [{"address": "0x2", "percent": "0.2", "is_contract": 0}]}
    s = evm_security(gp, {"honeypotResult": {"isHoneypot": False}, "summary": {"flags": []}})
    assert s["buy_tax"] == pytest.approx(10) and s["mintable"] and not s["owner_renounced"]
    assert s["lp_locked_pct"] == pytest.approx(30) and s["top1"] == pytest.approx(20)


def _cand(**kw):
    base = dict(chain="base", address="0x" + "1" * 40, symbol="TST", name="Test", pair="0x" + "2" * 40, dex="uniswap",
                quote="WETH", price=0.001, mcap=2e6, fdv=2e6, liquidity=2e5, liq_main=2e5, vol24=5e5, vol6=1e5,
                vol1=2e4, pc1=1, pc6=2, pc24=5, buys24=100, sells24=90, age_days=30)
    base.update(kw)
    return Candidate(**base)


def test_prefilter_and_red_flags():
    f = CFG["filters"]
    assert prefilter(_cand(mcap=50_000), f) == "Market Cap zu klein"
    assert prefilter(_cand(liquidity=10_000), f) == "zu wenig Liquidität"
    assert prefilter(_cand(), f) is None
    gp = {"is_honeypot": "0", "buy_tax": "0", "sell_tax": "0.2", "owner_address": "", "is_open_source": "1"}
    a = analyze(_cand(), Deep(goplus=gp), CFG)
    assert any("Steuer 20 %" in r for r in a.red_flags)
    a = analyze(_cand(pc24=900), Deep(goplus={**gp, "sell_tax": "0"}), CFG)
    assert any("Bereits explodiert" in r for r in a.red_flags)


# ------------------------------------------------------------------------------------------- Szenarien

def test_scenarios_include_costs_and_losses():
    assert price_impact_pct(1000, 2_000_000) < 0.11
    s = scenario(100, 1e6, 1e9, {"onramp_pct": 2, "swap_pct": 1, "exit_slippage_pct": 0.5}, 1.0, [5, 10])
    assert s.invested_eur == pytest.approx(97, abs=0.1)
    assert s.outcomes["5x"] == pytest.approx(97 * 5 * 0.985, rel=1e-3)
    assert s.outcomes["Rug-Pull"] == 0 and s.outcomes["−90 %"] < 10
    assert s.mcap_needed[10] == 1e7
    thin = scenario(1000, 1e6, 60_000, {"onramp_pct": 2, "swap_pct": 1, "exit_slippage_pct": 0.5}, 1.0, [5])
    assert thin.entry_cost_pct > 5  # dünne Liquidität -> spürbare Slippage


# ------------------------------------------------------------------------------------------- Report

def test_detail_message_has_all_sections(demo_result):
    fav = demo_result.favorite(CFG["recommend"]["min_score"])
    text = report.detail(fav, CFG, demo_result.market, demo_result.biggest_meme)
    for marker in ("1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "💶 Szenarien", fav.cand.address, "Trust Wallet"):
        assert marker in text
    assert all(len(p) <= 4096 for p in report.split_message(text))


def test_html_is_escaped():
    c = _cand(symbol="<b>X</b>", name="A & B")
    assert "&lt;b&gt;X" in report.token_title(c)


def test_number_formatting():
    assert report.usd(6_870_000) == "6,87 Mio. $"
    assert report.eur(1911) == "1.911 €"
    assert report.price(0.000636) == "0,000636 $"


# ------------------------------------------------------------------------------------------- Telegram

class FakeAPI:
    def __init__(self):
        self.sent = []

    def send(self, chat_id, text):
        self.sent.append((chat_id, text))


def _msg(text, chat=42):
    return {"update_id": 1, "message": {"text": text, "chat": {"id": chat}}}


def test_bot_blocks_strangers_and_shows_chat_id():
    api = FakeAPI()
    bot = Bot(api, demo_scanner(CFG), allowed={42})
    bot.handle(_msg("/scan", chat=7))
    assert "7" in api.sent[-1][1] and "privat" in api.sent[-1][1]
    assert bot.jobs.empty()


def test_bot_scan_check_and_invest_flow():
    api = FakeAPI()
    bot = Bot(api, demo_scanner(CFG), allowed={42})
    bot.handle(_msg("/hilfe"))
    assert "/scan" in api.sent[-1][1]
    bot.handle(_msg("/scan@MeinBot solana"))
    bot.jobs.get().run()
    texts = "\n".join(t for _, t in api.sent)
    assert "GOODCAT" in texts and "⭐ Favorit" in texts and "BASEBRO" not in texts  # nur Solana gescannt
    bot.handle(_msg("/invest 250"))
    bot.jobs.get().run()
    assert "250 €" in api.sent[-1][1]
    bot.handle(_msg(TOKENS["RUGDOG"]["address"]))  # nackte Adresse = /check
    bot.jobs.get().run()
    assert "Finger weg" in api.sent[-1][1]
    bot.handle(_msg("/check kaputt"))
    assert "Bitte so" in api.sent[-1][1]


def test_parse_allowed():
    assert parse_allowed("123, -456", None, "789") == {123, -456, 789}


# ------------------------------------------------------------------------------------------- HTTP

class FakeResp:
    def __init__(self, status, data=None):
        self.status_code, self._data = status, data

    def json(self):
        return self._data


class FakeSession:
    def __init__(self, responses):
        self.responses, self.calls, self.headers = list(responses), 0, {}

    def get(self, url, timeout=None):
        self.calls += 1
        return self.responses.pop(0)


def test_http_backs_off_on_429_and_caches():
    sleeps = []
    sess = FakeSession([FakeResp(429), FakeResp(429), FakeResp(200, {"ok": 1})])
    http = Http(session=sess, sleep=sleeps.append)
    url = "https://api.geckoterminal.com/api/v2/x"
    assert http.get_json(url) == {"ok": 1}
    assert sess.calls == 3 and http.interval["api.geckoterminal.com"] > 2.1
    assert http.get_json(url) == {"ok": 1} and sess.calls == 3  # aus dem Cache
    assert Http(session=FakeSession([FakeResp(404)]), sleep=sleeps.append).get_json(url) is None


def test_demo_clock_is_fixed():
    assert datetime.fromtimestamp(NOW_S, timezone.utc).year == 2026


def test_telegram_api_splits_and_falls_back_to_plain_text():
    from memecoin_bot.telegram_bot import TelegramAPI

    class Sess:
        def __init__(self):
            self.posts = []

        def post(self, url, json=None, timeout=None):
            self.posts.append((url.rsplit("/", 1)[1], json))
            ok = not (json.get("parse_mode") == "HTML" and "<broken" in json["text"])
            return FakeResp(200, {"ok": ok, "result": {}, "description": "can't parse entities"})

    s = Sess()
    api = TelegramAPI("TOKEN", session=s)
    api.send(1, "\n".join(["Zeile " * 50] * 40))  # ~12.000 Zeichen
    assert len(s.posts) >= 3 and all(len(p[1]["text"]) <= 4096 for p in s.posts)
    s.posts.clear()
    api.send(1, "<b>ok</b> <broken")
    assert [p[1].get("parse_mode") for p in s.posts] == ["HTML", None]


def test_stop_level_never_below_minus_50_percent():
    day = 86_400
    # junger Token: Starttag sehr billig, dann +100x -> Stop darf nicht beim Starttags-Preis liegen
    rows = [[i * day, 1, 1, 1, c, 100] for i, c in enumerate([0.00001, 0.0005, 0.0009, 0.001])]
    c = _cand(chain="solana", price=0.001, mcap=1e6)
    a = analyze(c, Deep(ohlcv=rows, rugcheck={"token": {"supply": 1}, "score_normalised": 1}), CFG)
    conds = " ".join(report.conditions_block(a, CFG))
    assert "−50 % Stop-Loss" in conds and "0,000500 $" in conds


def test_48h_run_up_counts_as_overextended():
    day = 86_400
    flat = [[i * day, 1, 1, 1, 1.0, 100] for i in range(10)]
    pumped = flat[:-2] + [[8 * day, 1, 1, 1, 2.0, 100], [9 * day, 1, 1, 1, 3.0, 100]]
    gp = {"is_honeypot": "0", "buy_tax": "0", "sell_tax": "0", "owner_address": "", "is_open_source": "1"}
    calm = analyze(_cand(price=1.0), Deep(ohlcv=flat, goplus=gp), CFG)
    hot = analyze(_cand(price=3.0), Deep(ohlcv=pumped, goplus=gp), CFG)
    assert hot.components["not_extended"] < calm.components["not_extended"]
    assert any("nicht hinterherkaufen" in w for w in hot.warnings)


def test_launchpad_creator_is_warning_not_red_flag():
    gp = {"is_honeypot": "0", "buy_tax": "0", "sell_tax": "0", "owner_address": "", "is_open_source": "1",
          "creator_address": "0xfac", "creator_percent": "1.000000",
          "holders": [{"address": "0xfac", "percent": "0.8", "is_contract": 1},
                      {"address": "0x1", "percent": "0.02", "is_contract": 0}]}
    a = analyze(_cand(), Deep(goplus=gp), CFG)
    assert not any("Ersteller" in r for r in a.red_flags)
    assert any("Launchpad" in w for w in a.warnings)
