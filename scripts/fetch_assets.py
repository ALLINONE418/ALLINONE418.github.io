import json
import os
import time
import requests
from datetime import datetime, timezone, timedelta

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


def fetch_yahoo_all():
    import yfinance as yf
    results = {}
    tickers = [a["ticker"] for a in ASSETS]

    print(f"  Downloading history for {len(tickers)} tickers...")
    # 一次性下载3年周线数据
    try:
        hist = yf.download(
            tickers, period="3y", interval="1wk",
            group_by="ticker", auto_adjust=True,
            progress=False, timeout=30
        )
    except Exception as e:
        print(f"  yf.download error: {e}")
        hist = None

    for asset in ASSETS:
        ticker = asset["ticker"]
        try:
            tk = yf.Ticker(ticker)
            info = tk.fast_info
            price    = getattr(info, "last_price", None)
            prev     = getattr(info, "previous_close", None)
            high52   = getattr(info, "year_high", None)
            low52    = getattr(info, "year_low", None)
            chg_24h  = ((price - prev) / prev * 100) if price and prev and prev != 0 else None

            # 从历史数据取各时间节点价格
            chg_6m = chg_1y = chg_3y = None
            if hist is not None and price:
                try:
                    if len(tickers) > 1:
                        col = hist["Close"][ticker] if "Close" in hist.columns.get_level_values(0) else hist[ticker]["Close"]
                    else:
                        col = hist["Close"]
                    col = col.dropna()
                    now = datetime.now(timezone.utc)
                    def price_ago(days):
                        target = now - timedelta(days=days)
                        # pandas datetime比较
                        import pandas as pd
                        target_pd = pd.Timestamp(target).tz_localize(None)
                        col_naive = col.copy()
                        if col_naive.index.tz is not None:
                            col_naive.index = col_naive.index.tz_localize(None)
                        idx = (col_naive.index - target_pd).abs().argmin()
                        return float(col_naive.iloc[idx])
                    def calc(past):
                        return (price - past) / past * 100 if past and past != 0 else None
                    chg_6m = calc(price_ago(182))
                    chg_1y = calc(price_ago(365))
                    chg_3y = calc(price_ago(1095))
                except Exception as e2:
                    print(f"    history parse error {ticker}: {e2}")

            results[ticker] = {
                "price": price, "chg_24h": chg_24h,
                "chg_6m": chg_6m, "chg_1y": chg_1y, "chg_3y": chg_3y,
                "high52": high52, "low52": low52,
            }
            icon = "✅" if price else "⚠️"
            c24 = f"{chg_24h:+.2f}%" if chg_24h is not None else "N/A"
            c1y = f"{chg_1y:+.1f}%" if chg_1y is not None else "N/A"
            print(f"  {icon} {asset['name']:20s} {str(price or 'N/A'):>12s}  24h:{c24}  1y:{c1y}")
        except Exception as e:
            print(f"  ⚠️  {asset['name']:20s} error: {e}")
            results[ticker] = {"price": None, "chg_24h": None, "chg_6m": None,
                               "chg_1y": None, "chg_3y": None, "high52": None, "low52": None}
    return results


def fetch_coingecko():
    results = {}
    ids = ",".join([a["cg_id"] for a in CRYPTO_ASSETS])
    try:
        resp = requests.get(
            f"https://api.coingecko.com/api/v3/simple/price"
            f"?ids={ids}&vs_currencies=usd&include_24hr_change=true&include_7d_change=true",
            headers={"User-Agent": "Mozilla/5.0"}, timeout=15
        )
        data = resp.json()
        for asset in CRYPTO_ASSETS:
            cg = data.get(asset["cg_id"], {})
            results[asset["cg_id"]] = {
                "price": cg.get("usd"), "chg_24h": cg.get("usd_24h_change"),
                "chg_6m": None, "chg_1y": None, "chg_3y": None,
            }
    except Exception as e:
        print(f"  CoinGecko simple error: {e}")

    # 逐个补 6m/1y/3y
    for asset in CRYPTO_ASSETS:
        cg_id = asset["cg_id"]
        try:
            time.sleep(1.5)
            resp2 = requests.get(
                f"https://api.coingecko.com/api/v3/coins/{cg_id}/market_chart",
                params={"vs_currency": "usd", "days": "1095", "interval": "weekly"},
                headers={"User-Agent": "Mozilla/5.0"}, timeout=20
            )
            if resp2.status_code == 200:
                prices = resp2.json().get("prices", [])
                current = results.get(cg_id, {}).get("price")
                if prices and current:
                    now_ms = time.time() * 1000
                    def cg_price_ago(days):
                        target = now_ms - days * 86400 * 1000
                        best, diff = None, float('inf')
                        for ts, p in prices:
                            if abs(ts - target) < diff:
                                diff = abs(ts - target); best = p
                        return best
                    def cg_chg(past):
                        return (current - past) / past * 100 if past and past != 0 else None
                    if cg_id not in results:
                        results[cg_id] = {}
                    results[cg_id]["chg_6m"] = cg_chg(cg_price_ago(182))
                    results[cg_id]["chg_1y"] = cg_chg(cg_price_ago(365))
                    results[cg_id]["chg_3y"] = cg_chg(cg_price_ago(1095))
                    c1y = results[cg_id]['chg_1y']
                    print(f"  ✅ {asset['name']:20s} 1y:{c1y:+.1f}%" if c1y else f"  ✅ {asset['name']}")
        except Exception as e:
            print(f"  CoinGecko history error {cg_id}: {e}")
    return results


def fmt_price(val, section):
    if val is None: return "N/A"
    if section == "bonds": return f"{val:.2f}%"
    if section == "fx":    return f"{val:.4f}" if val < 10 else f"{val:.3f}"
    if val > 10000:        return f"{val:,.0f}"
    if val > 100:          return f"{val:,.2f}"
    return f"{val:.4f}"

def fmt_chg(val, section):
    if val is None: return "N/A"
    if section == "bonds":
        bp = round(val * 100); s = "+" if bp >= 0 else ""
        return f"{s}{bp}bp"
    s = "+" if val >= 0 else ""
    return f"{s}{val:.2f}%"


def fetch_assets():
    now = datetime.now(timezone.utc)
    print(f"Fetching assets at {now.isoformat()}\n")

    print("=== Yahoo Finance (yfinance) ===")
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
        price  = d.get("price")
        high52 = d.get("high52")
        low52  = d.get("low52")
        range52 = (f"{fmt_price(low52, sec)} – {fmt_price(high52, sec)}"
                   if high52 and low52 else "N/A")
        sections[sec]["items"].append({
            "key": asset["key"], "name": asset["name"], "sub": asset["sub"],
            "price":  fmt_price(price, sec),
            "chg":    fmt_chg(d.get("chg_24h"), sec), "up":    (d.get("chg_24h") or 0) >= 0,
            "chg_6m": fmt_chg(d.get("chg_6m"),  sec), "up_6m": (d.get("chg_6m")  or 0) >= 0,
            "chg_1y": fmt_chg(d.get("chg_1y"),  sec), "up_1y": (d.get("chg_1y")  or 0) >= 0,
            "chg_3y": fmt_chg(d.get("chg_3y"),  sec), "up_3y": (d.get("chg_3y")  or 0) >= 0,
            "range52": range52, "raw_price": price,
        })

    for asset in CRYPTO_ASSETS:
        cg    = cg_data.get(asset["cg_id"], {})
        price = cg.get("price")
        if price is None:   ps = "N/A"
        elif price >= 1000: ps = f"${price:,.0f}"
        elif price >= 1:    ps = f"${price:.2f}"
        else:               ps = f"${price:.4f}"
        def cf(val):
            if val is None: return "N/A"
            return f"+{val:.2f}%" if val >= 0 else f"{val:.2f}%"
        sections["crypto"]["items"].append({
            "key": asset["key"], "name": asset["name"], "sub": asset["sub"],
            "price": ps,
            "chg":    cf(cg.get("chg_24h")), "up":    (cg.get("chg_24h") or 0) >= 0,
            "chg_6m": cf(cg.get("chg_6m")),  "up_6m": (cg.get("chg_6m")  or 0) >= 0,
            "chg_1y": cf(cg.get("chg_1y")),  "up_1y": (cg.get("chg_1y")  or 0) >= 0,
            "chg_3y": cf(cg.get("chg_3y")),  "up_3y": (cg.get("chg_3y")  or 0) >= 0,
            "range52": "N/A", "raw_price": price,
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
