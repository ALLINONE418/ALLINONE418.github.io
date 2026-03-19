import json
import os
import requests
from datetime import datetime, timezone
import time

YAHOO_ASSETS = [
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


def fetch_yahoo_chart(ticker, session):
    """用 chart API 抓单个 ticker，最稳定"""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        resp = session.get(url, params={"interval": "1d", "range": "5d"}, timeout=12)
        if resp.status_code != 200:
            url2 = f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}"
            resp = session.get(url2, params={"interval": "1d", "range": "5d"}, timeout=12)
        if resp.status_code != 200:
            return None
        data = resp.json()
        result = data.get("chart", {}).get("result", [])
        if not result:
            return None
        meta = result[0].get("meta", {})
        price = meta.get("regularMarketPrice")
        prev  = meta.get("chartPreviousClose") or meta.get("previousClose")
        chg_pct = ((price - prev) / prev * 100) if price and prev and prev != 0 else None
        return {
            "price":   price,
            "chg_pct": chg_pct,
            "high52":  meta.get("fiftyTwoWeekHigh"),
            "low52":   meta.get("fiftyTwoWeekLow"),
        }
    except Exception as e:
        print(f"    chart error {ticker}: {e}")
        return None


def fetch_yahoo_all(assets):
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/122.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://finance.yahoo.com/",
    })
    # 先访问一次主页拿 cookie
    try:
        session.get("https://finance.yahoo.com/", timeout=8)
        time.sleep(0.5)
    except:
        pass

    results = {}
    for asset in assets:
        ticker = asset["ticker"]
        time.sleep(0.2)
        data = fetch_yahoo_chart(ticker, session)
        if data and data.get("price"):
            results[ticker] = data
            icon = "✅"
        else:
            icon = "⚠️"
        price_display = f"{data['price']:.2f}" if data and data.get("price") else "N/A"
        print(f"  {icon} {asset['name']:20s} {price_display}")
    return results


def fetch_coingecko():
    ids = ",".join([a["cg_id"] for a in CRYPTO_ASSETS])
    url = (f"https://api.coingecko.com/api/v3/simple/price"
           f"?ids={ids}&vs_currencies=usd&include_24hr_change=true")
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        return resp.json()
    except Exception as e:
        print(f"CoinGecko error: {e}")
        return {}


def fmt_price(val, section):
    if val is None: return "N/A"
    if section == "bonds":  return f"{val:.2f}%"
    if section == "fx":     return f"{val:.4f}" if val < 10 else f"{val:.3f}"
    if val > 10000:         return f"{val:,.0f}"
    if val > 100:           return f"{val:,.2f}"
    return f"{val:.4f}"


def fmt_change(chg_pct, section):
    if chg_pct is None: return "N/A", True
    up   = chg_pct >= 0
    sign = "+" if up else ""
    if section == "bonds":
        bp = round(chg_pct * 100)
        s  = "+" if bp >= 0 else ""
        return f"{s}{bp}bp", up
    return f"{sign}{chg_pct:.2f}%", up


def build_item(asset, yahoo_data):
    d       = yahoo_data.get(asset["ticker"], {})
    price   = d.get("price")
    chg_pct = d.get("chg_pct")
    high52  = d.get("high52")
    low52   = d.get("low52")
    sec     = asset["section"]
    price_str   = fmt_price(price, sec)
    chg_str, up = fmt_change(chg_pct, sec)
    range52 = (f"{fmt_price(low52, sec)} – {fmt_price(high52, sec)}"
               if high52 and low52 else "N/A")
    return {"key": asset["key"], "name": asset["name"], "sub": asset["sub"],
            "price": price_str, "chg": chg_str, "up": up, "range52": range52,
            "raw_price": price, "raw_chg_pct": chg_pct}


def fetch_assets():
    now = datetime.now(timezone.utc)
    print(f"Fetching assets at {now.isoformat()}\n")

    print("=== Yahoo Finance (chart API) ===")
    yahoo_data = fetch_yahoo_all(YAHOO_ASSETS)

    print("\n=== CoinGecko ===")
    cg_data = fetch_coingecko()

    sections = {
        "equities":    {"title": "Equities 股票",   "items": []},
        "bonds":       {"title": "Bonds 债券",       "items": []},
        "commodities": {"title": "Commodities 商品", "items": []},
        "crypto":      {"title": "Crypto 加密货币",  "items": []},
        "fx":          {"title": "FX 外汇",          "items": []},
    }

    for asset in YAHOO_ASSETS:
        sections[asset["section"]]["items"].append(build_item(asset, yahoo_data))

    for asset in CRYPTO_ASSETS:
        cg      = cg_data.get(asset["cg_id"], {})
        price   = cg.get("usd")
        chg_pct = cg.get("usd_24h_change")
        up      = (chg_pct or 0) >= 0
        sign    = "+" if up else ""
        if price is None:       price_str = "N/A"
        elif price >= 1000:     price_str = f"${price:,.0f}"
        elif price >= 1:        price_str = f"${price:.2f}"
        else:                   price_str = f"${price:.4f}"
        chg_str = f"{sign}{chg_pct:.2f}%" if chg_pct is not None else "N/A"
        icon = "✅" if price else "⚠️"
        print(f"  {icon} {asset['name']:20s} {price_str}")
        sections["crypto"]["items"].append({
            "key": asset["key"], "name": asset["name"], "sub": asset["sub"],
            "price": price_str, "chg": chg_str, "up": up, "range52": "N/A",
            "raw_price": price, "raw_chg_pct": chg_pct,
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
