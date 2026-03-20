import json
import os
import requests
from datetime import datetime, timezone
import time

ASSETS = [
    {"key": "sp500",   "ticker": "^GSPC",    "name": "S&P 500",    "sub": "USA",          "section": "equities"},
    {"key": "nasdaq",  "ticker": "^IXIC",    "name": "NASDAQ",     "sub": "USA Tech",     "section": "equities"},
    {"key": "nikkei",  "ticker": "^N225",    "name": "Nikkei 225", "sub": "Japan",        "section": "equities"},
    {"key": "csi1000", "ticker": "000852.SS","name": "CSI 1000",   "sub": "China",        "section": "equities"},
    {"key": "hsi",     "ticker": "^HSI",     "name": "Hang Seng",  "sub": "Hong Kong",    "section": "equities"},
    {"key": "dax",     "ticker": "^GDAXI",   "name": "DAX",        "sub": "Germany",      "section": "equities"},
    {"key": "ust10",   "ticker": "^TNX",     "name": "US 10Y Yield","sub": "Treasury",    "section": "bonds"},
    {"key": "ust2",    "ticker": "^IRX",     "name": "US 13W Yield","sub": "Treasury",    "section": "bonds"},
    {"key": "gold",    "ticker": "GC=F",     "name": "Gold",       "sub": "XAU/USD",      "section": "commodities"},
    {"key": "silver",  "ticker": "SI=F",     "name": "Silver",     "sub": "XAG/USD",      "section": "commodities"},
    {"key": "wti",     "ticker": "CL=F",     "name": "WTI Crude",  "sub": "Oil",          "section": "commodities"},
    {"key": "brent",   "ticker": "BZ=F",     "name": "Brent Crude","sub": "Oil",          "section": "commodities"},
    {"key": "copper",  "ticker": "HG=F",     "name": "Copper",     "sub": "LME",          "section": "commodities"},
    {"key": "natgas",  "ticker": "NG=F",     "name": "Natural Gas","sub": "NYMEX",        "section": "commodities"},
    {"key": "eurusd",  "ticker": "EURUSD=X", "name": "EUR/USD",    "sub": "Euro / Dollar","section": "fx"},
    {"key": "usdjpy",  "ticker": "JPY=X",    "name": "USD/JPY",    "sub": "Dollar / Yen", "section": "fx"},
    {"key": "gbpusd",  "ticker": "GBPUSD=X", "name": "GBP/USD",    "sub": "Cable",        "section": "fx"},
    {"key": "dxy",     "ticker": "DX-Y.NYB", "name": "DXY",        "sub": "Dollar Index", "section": "fx"},
    {"key": "usdcny",  "ticker": "CNY=X",    "name": "USD/CNY",    "sub": "Offshore CNH", "section": "fx"},
    {"key": "usdchf",  "ticker": "CHFUSD=X", "name": "USD/CHF",    "sub": "Swissie",      "section": "fx"},
]

CRYPTO_ASSETS = [
    {"key": "btc",  "cg_id": "bitcoin",     "name": "Bitcoin",  "sub": "BTC/USD"},
    {"key": "eth",  "cg_id": "ethereum",    "name": "Ethereum", "sub": "ETH/USD"},
    {"key": "sol",  "cg_id": "solana",      "name": "Solana",   "sub": "SOL/USD"},
    {"key": "bnb",  "cg_id": "binancecoin", "name": "BNB",      "sub": "BNB/USD"},
    {"key": "xrp",  "cg_id": "ripple",      "name": "XRP",      "sub": "XRP/USD"},
]


def fetch_ticker_data(ticker, session):
    """用 yfinance chart API 抓取价格 + 3年历史"""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        params = {"interval": "1wk", "range": "3y"}
        resp = session.get(url, params=params, timeout=15)
        if resp.status_code != 200:
            url2 = f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}"
            resp = session.get(url2, params=params, timeout=15)
        if resp.status_code != 200:
            return None

        data = resp.json()
        result = data.get("chart", {}).get("result", [])
        if not result:
            return None

        meta = result[0].get("meta", {})
        timestamps = result[0].get("timestamp", [])
        closes = result[0].get("indicators", {}).get("adjclose", [{}])[0].get("adjclose", [])

        if not closes:
            closes = result[0].get("indicators", {}).get("quote", [{}])[0].get("close", [])

        current = meta.get("regularMarketPrice")
        prev_close = meta.get("chartPreviousClose") or meta.get("previousClose")
        high52 = meta.get("fiftyTwoWeekHigh")
        low52 = meta.get("fiftyTwoWeekLow")

        # 计算各时间段涨跌幅
        now_ts = time.time()
        def find_price_ago(days):
            target_ts = now_ts - days * 86400
            best_price = None
            best_diff = float('inf')
            for ts, price in zip(timestamps, closes):
                if ts and price and abs(ts - target_ts) < best_diff:
                    best_diff = abs(ts - target_ts)
                    best_price = price
            return best_price

        price_6m = find_price_ago(182)
        price_1y = find_price_ago(365)
        price_3y = find_price_ago(1095)

        def calc_chg(past_price):
            if current and past_price and past_price != 0:
                return (current - past_price) / past_price * 100
            return None

        chg_24h = ((current - prev_close) / prev_close * 100) if current and prev_close and prev_close != 0 else None

        return {
            "price":    current,
            "chg_24h":  chg_24h,
            "chg_6m":   calc_chg(price_6m),
            "chg_1y":   calc_chg(price_1y),
            "chg_3y":   calc_chg(price_3y),
            "high52":   high52,
            "low52":    low52,
        }
    except Exception as e:
        print(f"    error {ticker}: {e}")
        return None


def fetch_yahoo_all():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/122.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://finance.yahoo.com/",
    })
    try:
        session.get("https://finance.yahoo.com/", timeout=8)
        time.sleep(0.5)
    except:
        pass

    results = {}
    for asset in ASSETS:
        ticker = asset["ticker"]
        time.sleep(0.3)
        data = fetch_ticker_data(ticker, session)
        if data and data.get("price"):
            results[ticker] = data
            icon = "✅"
        else:
            icon = "⚠️"
        price_str = f"{data['price']:.2f}" if data and data.get("price") else "N/A"
        chg_str = f"{data['chg_24h']:+.2f}%" if data and data.get("chg_24h") is not None else ""
        print(f"  {icon} {asset['name']:20s} {price_str:>12s}  {chg_str}")
    return results


def fetch_coingecko():
    """CoinGecko：当前价格 + 24h/6m/1y/3y 涨跌幅"""
    results = {}
    ids = ",".join([a["cg_id"] for a in CRYPTO_ASSETS])

    # 当前价格 + 24h/7d/30d 变化
    url = (f"https://api.coingecko.com/api/v3/simple/price"
           f"?ids={ids}&vs_currencies=usd"
           f"&include_24hr_change=true&include_7d_change=true&include_30d_change=true")
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        data = resp.json()
        for asset in CRYPTO_ASSETS:
            cg = data.get(asset["cg_id"], {})
            results[asset["cg_id"]] = {
                "price":   cg.get("usd"),
                "chg_24h": cg.get("usd_24h_change"),
                "chg_7d":  cg.get("usd_7d_change"),
                "chg_30d": cg.get("usd_30d_change"),
                "chg_6m":  None,
                "chg_1y":  None,
                "chg_3y":  None,
            }
    except Exception as e:
        print(f"  CoinGecko simple/price error: {e}")

    # 用 market_chart 补充 6m/1y/3y（逐个查询，避免超限）
    for asset in CRYPTO_ASSETS:
        cg_id = asset["cg_id"]
        try:
            time.sleep(1.2)  # CoinGecko 免费版限速
            url2 = f"https://api.coingecko.com/api/v3/coins/{cg_id}/market_chart"
            resp2 = requests.get(url2, params={"vs_currency": "usd", "days": "1095", "interval": "weekly"},
                                 headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            if resp2.status_code == 200:
                hist = resp2.json().get("prices", [])
                if hist and cg_id in results and results[cg_id]["price"]:
                    current = results[cg_id]["price"]
                    now_ms = time.time() * 1000
                    def find_cg_price(days):
                        target = now_ms - days * 86400 * 1000
                        best, diff = None, float('inf')
                        for ts, p in hist:
                            if abs(ts - target) < diff:
                                diff = abs(ts - target)
                                best = p
                        return best
                    p6m = find_cg_price(182)
                    p1y = find_cg_price(365)
                    p3y = find_cg_price(1095)
                    def chg(past):
                        return (current - past) / past * 100 if past and past != 0 else None
                    results[cg_id]["chg_6m"] = chg(p6m)
                    results[cg_id]["chg_1y"] = chg(p1y)
                    results[cg_id]["chg_3y"] = chg(p3y)
                    print(f"  ✅ {asset['name']:20s} 6m={results[cg_id]['chg_6m']:+.1f}% 1y={results[cg_id]['chg_1y']:+.1f}%" if results[cg_id]['chg_6m'] else f"  ✅ {asset['name']}")
        except Exception as e:
            print(f"  CoinGecko market_chart error {cg_id}: {e}")

    return results


def fmt_price(val, section):
    if val is None: return "N/A"
    if section == "bonds": return f"{val:.2f}%"
    if section == "fx":    return f"{val:.4f}" if val < 10 else f"{val:.3f}"
    if val > 10000:        return f"{val:,.0f}"
    if val > 100:          return f"{val:,.2f}"
    return f"{val:.4f}"


def fmt_chg(val, section=None, is_bp=False):
    """格式化涨跌幅，债券用bp，其他用%"""
    if val is None: return "N/A"
    if section == "bonds":
        bp = round(val * 100)
        s = "+" if bp >= 0 else ""
        return f"{s}{bp}bp"
    up = val >= 0
    sign = "+" if up else ""
    return f"{sign}{val:.2f}%"


def fetch_assets():
    now = datetime.now(timezone.utc)
    print(f"Fetching assets at {now.isoformat()}\n")

    print("=== Yahoo Finance ===")
    yahoo_data = fetch_yahoo_all()

    print("\n=== CoinGecko ===")
    cg_data = fetch_coingecko()

    sections = {
        "equities":    {"title": "Equities 股票",   "items": []},
        "bonds":       {"title": "Bonds 债券",       "items": []},
        "commodities": {"title": "Commodities 商品", "items": []},
        "crypto":      {"title": "Crypto 加密货币",  "items": []},
        "fx":          {"title": "FX 外汇",          "items": []},
    }

    for asset in ASSETS:
        d   = yahoo_data.get(asset["ticker"], {})
        sec = asset["section"]
        price   = d.get("price")
        high52  = d.get("high52")
        low52   = d.get("low52")

        price_str = fmt_price(price, sec)
        chg_24h_str = fmt_chg(d.get("chg_24h"), sec)
        chg_6m_str  = fmt_chg(d.get("chg_6m"),  sec)
        chg_1y_str  = fmt_chg(d.get("chg_1y"),  sec)
        chg_3y_str  = fmt_chg(d.get("chg_3y"),  sec)
        up_24h = (d.get("chg_24h") or 0) >= 0

        range52 = (f"{fmt_price(low52, sec)} – {fmt_price(high52, sec)}"
                   if high52 and low52 else "N/A")

        sections[sec]["items"].append({
            "key": asset["key"], "name": asset["name"], "sub": asset["sub"],
            "price": price_str,
            "chg":    chg_24h_str, "up":    up_24h,
            "chg_6m": chg_6m_str,  "up_6m": (d.get("chg_6m") or 0) >= 0,
            "chg_1y": chg_1y_str,  "up_1y": (d.get("chg_1y") or 0) >= 0,
            "chg_3y": chg_3y_str,  "up_3y": (d.get("chg_3y") or 0) >= 0,
            "range52": range52,
            "raw_price": price,
        })

    for asset in CRYPTO_ASSETS:
        cg  = cg_data.get(asset["cg_id"], {})
        price   = cg.get("price")
        chg_24h = cg.get("chg_24h")
        up = (chg_24h or 0) >= 0
        sign = "+" if up else ""

        if price is None:   price_str = "N/A"
        elif price >= 1000: price_str = f"${price:,.0f}"
        elif price >= 1:    price_str = f"${price:.2f}"
        else:               price_str = f"${price:.4f}"

        def cg_fmt(val):
            if val is None: return "N/A"
            s = "+" if val >= 0 else ""
            return f"{s}{val:.2f}%"

        sections["crypto"]["items"].append({
            "key": asset["key"], "name": asset["name"], "sub": asset["sub"],
            "price": price_str,
            "chg":    cg_fmt(chg_24h),          "up":    up,
            "chg_6m": cg_fmt(cg.get("chg_6m")), "up_6m": (cg.get("chg_6m") or 0) >= 0,
            "chg_1y": cg_fmt(cg.get("chg_1y")), "up_1y": (cg.get("chg_1y") or 0) >= 0,
            "chg_3y": cg_fmt(cg.get("chg_3y")), "up_3y": (cg.get("chg_3y") or 0) >= 0,
            "range52": "N/A",
            "raw_price": price,
        })

    output = {
        "updated_at":      now.isoformat(),
        "updated_display": now.strftime("%b %d, %Y %H:%M UTC"),
        "sections": [sections["equities"], sections["bonds"],
                     sections["commodities"], sections["crypto"], sections["fx"]]
    }

    os.makedirs("data", exist_ok=True)
    with open("data/assets.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    total = sum(len(s["items"]) for s in output["sections"])
    ok    = sum(1 for s in output["sections"] for i in s["items"] if i["raw_price"])
    print(f"\n✅ Done: {ok}/{total} assets with live data")


if __name__ == "__main__":
    fetch_assets()
