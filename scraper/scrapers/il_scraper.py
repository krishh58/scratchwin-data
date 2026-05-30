"""Illinois Lottery — unpaid instant game prizes (Playwright required).
IL blocks plain HTTP with 403. Uses Playwright to load the prizes page.
Source: https://www.illinoislottery.com/about-the-games/unpaid-instant-games-prizes
"""
import re
import time

_PRIZES_URL = "https://www.illinoislottery.com/about-the-games/unpaid-instant-games-prizes"
_GAMES_URL  = "https://www.illinoislottery.com/games/scratch-offs"


def _parse_money(s: str) -> int:
    s = str(s).replace("$", "").replace(",", "").strip()
    m = re.search(r"\d+", s)
    return int(m.group(0)) if m else 0


def _clean_price(s: str) -> float:
    m = re.search(r"\$([\d.]+)", str(s))
    return float(m.group(1)) if m else 0.0


def _clean_int(s: str) -> int:
    s = str(s).replace(",", "").replace("$", "").strip()
    m = re.search(r"\d+", s)
    return int(m.group(0)) if m else 0


def scrape() -> list[dict]:
    from playwright.sync_api import sync_playwright
    from bs4 import BeautifulSoup

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
        )
        page = ctx.new_page()

        # Intercept any JSON API calls
        captured = []

        def handle_response(response):
            try:
                ct = response.headers.get("content-type", "")
                url = response.url
                if "json" in ct and any(k in url.lower() for k in ["game", "scratch", "prize", "instant"]):
                    data = response.json()
                    captured.append({"url": url, "data": data})
            except Exception:
                pass

        page.on("response", handle_response)

        try:
            page.goto(_PRIZES_URL, timeout=45000, wait_until="networkidle")
            time.sleep(4)

            if captured:
                browser.close()
                return _parse_captured(captured)

            # Wait for table to appear
            try:
                page.wait_for_selector("table", timeout=12000)
            except Exception:
                pass

            # Grab the largest table
            table_html = page.evaluate("""() => {
                const tables = document.querySelectorAll('table');
                let best = null, bestRows = 0;
                tables.forEach(t => {
                    const rows = t.querySelectorAll('tr').length;
                    if (rows > bestRows) { bestRows = rows; best = t; }
                });
                return best ? best.outerHTML : '';
            }""")

        finally:
            browser.close()

    if not table_html:
        return []

    soup = BeautifulSoup(table_html, "html.parser")
    rows = soup.find_all("tr")
    if len(rows) < 2:
        return []

    header = [th.get_text(strip=True).lower() for th in (rows[0].find_all("th") or rows[0].find_all("td"))]

    col_num   = next((i for i, h in enumerate(header) if "#" in h or "number" in h or "game #" in h), None)
    col_name  = next((i for i, h in enumerate(header) if "name" in h or "title" in h or "game name" in h), None)
    col_price = next((i for i, h in enumerate(header) if "price" in h or "cost" in h), None)
    col_prize = next((i for i, h in enumerate(header) if "prize" in h and "top" in h), None)
    if col_prize is None:
        col_prize = next((i for i, h in enumerate(header) if "prize" in h or "amount" in h), None)
    col_rem   = next((i for i, h in enumerate(header) if "remain" in h or "unclaim" in h or "left" in h), None)
    col_total = next((i for i, h in enumerate(header) if "total" in h or "printed" in h), None)

    tickets: dict[str, dict] = {}

    for row in rows[1:]:
        cells = [c.get_text(separator=" ", strip=True) for c in row.find_all(["td", "th"])]
        if len(cells) < 3:
            continue

        game_num  = cells[col_num].strip() if col_num is not None else ""
        name      = cells[col_name].strip() if col_name is not None else cells[0]
        price     = _clean_price(cells[col_price]) if col_price is not None else 0.0
        prize     = _clean_int(cells[col_prize]) if col_prize is not None else 0
        remaining = _clean_int(cells[col_rem]) if col_rem is not None else 0
        total     = _clean_int(cells[col_total]) if col_total is not None else remaining

        if not name or prize <= 0 or price <= 0:
            continue

        key = game_num or name
        if key not in tickets:
            tickets[key] = {
                "name": name,
                "price": price,
                "gameNumber": game_num,
                "tiers": [],
                "totalTickets": 0,
                "remainingTickets": 0,
            }
        tickets[key]["tiers"].append({
            "prize": prize,
            "remaining": remaining,
            "total": total if total > 0 else remaining,
        })

    result = []
    for t in tickets.values():
        if not t["tiers"]:
            continue
        t["tiers"].sort(key=lambda x: x["prize"], reverse=True)
        top = t["tiers"][0]
        if top["prize"] > 0 and top["total"] > 0 and t["price"] > 0:
            t["totalTickets"] = int((top["prize"] * top["total"]) / (0.65 * t["price"]))
            rem_frac = top["remaining"] / top["total"] if top["total"] > 0 else 0.5
            t["remainingTickets"] = int(t["totalTickets"] * rem_frac)
        result.append(t)

    return result


def _parse_captured(captured: list[dict]) -> list[dict]:
    tickets = []
    for cap in captured:
        data = cap["data"]
        items = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("data") or data.get("games") or data.get("items") or []
        for item in items:
            if not isinstance(item, dict):
                continue
            name  = item.get("name") or item.get("gameName") or item.get("title") or ""
            price = float(item.get("price") or item.get("ticketPrice") or 0)
            gnum  = str(item.get("gameNumber") or item.get("id") or "")
            tiers = []
            for tier_key in ("tiers", "prizes", "prizeTiers"):
                for t in (item.get(tier_key) or []):
                    prize = t.get("prize") or t.get("amount") or 0
                    rem   = t.get("remaining") or t.get("prizesRemaining") or 0
                    total = t.get("total") or t.get("totalPrizes") or rem
                    if prize > 0:
                        tiers.append({"prize": int(prize), "remaining": int(rem), "total": int(total)})
            if name and tiers:
                tiers.sort(key=lambda x: x["prize"], reverse=True)
                tickets.append({
                    "name": str(name), "price": price,
                    "totalTickets": 0, "remainingTickets": 0,
                    "gameNumber": gnum, "tiers": tiers,
                })
    return tickets


if __name__ == "__main__":
    import json
    tickets = scrape()
    print(f"IL: {len(tickets)} games")
    print(json.dumps(tickets[:2], indent=2))
