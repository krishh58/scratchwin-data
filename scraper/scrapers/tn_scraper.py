"""Tennessee Lottery — remaining top prizes table (Playwright required).
TN serves a Cloudflare JS challenge that blocks all plain HTTP scrapers.
Run via: python scrapers/tn_scraper.py (standalone test)
Requires: pip install playwright && playwright install chromium
"""
import re
import time

_PRIZES_URL = "https://tnlottery.com/remaining-prizes/"
_GAMES_URL  = "https://tnlottery.com/games/instant-games/"


def _parse_money(s: str) -> int:
    m = re.search(r"[\d,]+", s.replace("$", "").replace(",", "").strip())
    if not m:
        return 0
    return int(s.replace("$", "").replace(",", "").strip().split(".")[0].replace(",", "")) if s else 0


def _clean_price(s: str) -> float:
    m = re.search(r"\$([\d.]+)", s)
    return float(m.group(1)) if m else 0.0


def _clean_int(s: str) -> int:
    s = s.replace(",", "").replace("$", "").strip()
    m = re.search(r"\d+", s)
    return int(m.group(0)) if m else 0


def scrape() -> list[dict]:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )
        page = ctx.new_page()

        try:
            page.goto(_PRIZES_URL, timeout=45000, wait_until="networkidle")
            # Give JS extra time to render
            time.sleep(3)

            # Try to find a table on the page
            tables = page.query_selector_all("table")
            if not tables:
                # Try waiting for table explicitly
                try:
                    page.wait_for_selector("table", timeout=10000)
                    tables = page.query_selector_all("table")
                except Exception:
                    pass

            if not tables:
                browser.close()
                return []

            # Parse the first (or largest) table
            table_html = page.evaluate("""() => {
                const tables = document.querySelectorAll('table');
                let best = tables[0];
                let bestRows = 0;
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

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(table_html, "html.parser")
    rows = soup.find_all("tr")

    # Detect header to find column positions
    # Expected headers: Game #, Game Name, Ticket Price, Top Prize, Prizes Remaining
    # (exact names vary — find by keyword matching)
    header = [th.get_text(strip=True).lower() for th in (rows[0].find_all("th") or rows[0].find_all("td"))]

    col_num   = next((i for i, h in enumerate(header) if "number" in h or "game #" in h or "#" == h), None)
    col_name  = next((i for i, h in enumerate(header) if "name" in h), None)
    col_price = next((i for i, h in enumerate(header) if "price" in h or "cost" in h), None)
    col_prize = next((i for i, h in enumerate(header) if "top prize" in h or "prize amount" in h), None)
    col_rem   = next((i for i, h in enumerate(header) if "remain" in h or "unclaim" in h), None)

    tickets: dict[str, dict] = {}

    for row in rows[1:]:
        cells = [c.get_text(separator=" ", strip=True) for c in row.find_all(["td", "th"])]
        if len(cells) < 3:
            continue

        game_num = cells[col_num].strip() if col_num is not None else ""
        name     = cells[col_name].strip() if col_name is not None else cells[0]
        price    = _clean_price(cells[col_price]) if col_price is not None else 0.0
        prize    = _clean_int(cells[col_prize]) if col_prize is not None else 0
        remaining= _clean_int(cells[col_rem]) if col_rem is not None else 0

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
            "total": remaining,  # TN only reports remaining, not total issued
        })

    result = []
    for t in tickets.values():
        if not t["tiers"]:
            continue
        t["tiers"].sort(key=lambda x: x["prize"], reverse=True)
        top = t["tiers"][0]
        if top["prize"] > 0 and top["total"] > 0 and t["price"] > 0:
            t["totalTickets"] = int((top["prize"] * top["total"]) / (0.65 * t["price"]))
            t["remainingTickets"] = t["totalTickets"] // 2
        result.append(t)

    return result


if __name__ == "__main__":
    import json
    tickets = scrape()
    print(f"TN: {len(tickets)} games")
    print(json.dumps(tickets[:2], indent=2))
