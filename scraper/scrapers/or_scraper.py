"""Oregon Lottery — Scratch-its remaining top prizes (Playwright required).
Oregon serves a Next.js SPA — all URLs return the same JS shell with no data.
Each game page renders "X of Y top prizes remaining" once JS loads.
Requires: pip install playwright && playwright install chromium
"""
import re
import time
import json as jsonlib

_BASE = "https://www.oregonlottery.org"
_GAMES_URL = f"{_BASE}/games/scratch-its/"


def _parse_money(s: str) -> int:
    s = s.replace("$", "").replace(",", "").strip()
    m = re.search(r"\d+", s)
    return int(m.group(0)) if m else 0


def _clean_price(s: str) -> float:
    m = re.search(r"\$([\d.]+)", s)
    return float(m.group(1)) if m else 0.0


def scrape() -> list[dict]:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
        )
        page = ctx.new_page()

        # Intercept API calls to capture game data fed into the SPA
        game_data_captured = []

        def handle_response(response):
            url = response.url
            if "game" in url.lower() or "scratch" in url.lower() or "prize" in url.lower():
                try:
                    ct = response.headers.get("content-type", "")
                    if "json" in ct:
                        data = response.json()
                        game_data_captured.append({"url": url, "data": data})
                except Exception:
                    pass

        page.on("response", handle_response)

        try:
            page.goto(_GAMES_URL, timeout=45000, wait_until="networkidle")
            time.sleep(4)

            # Check if API calls captured data
            if game_data_captured:
                browser.close()
                return _parse_api_data(game_data_captured)

            # Otherwise extract game links from rendered DOM
            game_links = page.evaluate("""() => {
                const links = [];
                document.querySelectorAll('a[href*="/games/scratch-its/"]').forEach(a => {
                    const href = a.getAttribute('href');
                    if (href && !href.endsWith('/scratch-its/') && !href.includes('#')) {
                        links.push(href);
                    }
                });
                return [...new Set(links)];
            }""")

            if not game_links:
                browser.close()
                return []

            tickets = []
            for href in game_links[:80]:  # cap at 80 active games
                url = href if href.startswith("http") else f"{_BASE}{href}"
                try:
                    page.goto(url, timeout=30000, wait_until="networkidle")
                    time.sleep(2)

                    data = page.evaluate("""() => {
                        const result = {};

                        // Game name — h1 or title
                        const h1 = document.querySelector('h1');
                        result.name = h1 ? h1.innerText.trim() : '';

                        // Price — look for $ pattern near "price" text
                        const bodyText = document.body.innerText;
                        const priceM = bodyText.match(/\\$([\\d.]+)\\s*(ticket|each|per)/i);
                        result.price_str = priceM ? priceM[0] : '';

                        // Top prizes remaining — "X of Y top prizes remain" pattern
                        const remM = bodyText.match(/(\\d+)\\s+of\\s+(\\d+)\\s+top\\s+prizes?\\s+remain/i);
                        if (remM) {
                            result.top_remaining = parseInt(remM[1]);
                            result.top_total = parseInt(remM[2]);
                        }

                        // Also look for prize table
                        const tables = document.querySelectorAll('table');
                        if (tables.length > 0) {
                            const rows = [];
                            tables[0].querySelectorAll('tr').forEach(tr => {
                                const cells = [];
                                tr.querySelectorAll('td,th').forEach(c => cells.push(c.innerText.trim()));
                                if (cells.length >= 2) rows.push(cells);
                            });
                            result.table_rows = rows;
                        }

                        // Prize amount in page meta or hero
                        const prizeTags = document.querySelectorAll('[class*="prize"],[class*="top-prize"],[data-prize]');
                        prizeTags.forEach(el => {
                            if (!result.top_prize_str) result.top_prize_str = el.innerText.trim();
                        });

                        return result;
                    }""")

                    name = data.get("name", "").strip()
                    if not name:
                        continue

                    price = _clean_price(data.get("price_str", ""))
                    if price <= 0:
                        # Try slug-based price hint
                        slug = url.rstrip("/").split("/")[-1]
                        # Can't determine price from slug alone
                        continue

                    top_remaining = data.get("top_remaining", 0)
                    top_total = data.get("top_total", top_remaining)

                    # Parse prize amount
                    top_prize = _parse_money(data.get("top_prize_str", ""))

                    # Try from table rows
                    tiers = []
                    for row in (data.get("table_rows") or []):
                        if len(row) >= 2:
                            prize = _parse_money(row[0])
                            if prize > 0:
                                total = _parse_money(row[-1]) if len(row) >= 3 else 0
                                rem = _parse_money(row[-2]) if len(row) >= 4 else total
                                tiers.append({"prize": prize, "remaining": rem, "total": total})

                    if not tiers and top_prize > 0:
                        tiers = [{"prize": top_prize, "remaining": top_remaining, "total": top_total}]

                    if not tiers:
                        continue

                    tiers.sort(key=lambda x: x["prize"], reverse=True)
                    top = tiers[0]
                    if top["prize"] > 0 and top["total"] > 0 and price > 0:
                        total_tickets = int((top["prize"] * top["total"]) / (0.65 * price))
                        rem_tickets = int(total_tickets * top["remaining"] / top["total"]) if top["total"] else 0
                    else:
                        total_tickets = 0
                        rem_tickets = 0

                    # Game number from URL slug or page
                    slug = url.rstrip("/").split("/")[-1]

                    tickets.append({
                        "name": name,
                        "price": price,
                        "totalTickets": total_tickets,
                        "remainingTickets": rem_tickets,
                        "gameNumber": slug,
                        "tiers": tiers,
                    })

                except Exception as e:
                    print(f"[OR] Error on {url}: {e}")

        finally:
            browser.close()

    return tickets


def _parse_api_data(captures: list[dict]) -> list[dict]:
    """Parse any JSON API responses intercepted during page load."""
    tickets = []
    for cap in captures:
        data = cap["data"]
        if isinstance(data, list):
            for item in data:
                t = _item_to_ticket(item)
                if t:
                    tickets.append(t)
        elif isinstance(data, dict):
            # might be paginated: {"data": [...]}
            items = data.get("data") or data.get("games") or data.get("items") or []
            for item in items:
                t = _item_to_ticket(item)
                if t:
                    tickets.append(t)
    return tickets


def _item_to_ticket(item: dict) -> dict | None:
    if not isinstance(item, dict):
        return None
    name = item.get("name") or item.get("title") or item.get("gameName") or ""
    price = item.get("price") or item.get("ticketPrice") or 0
    game_num = str(item.get("gameNumber") or item.get("id") or "")
    tiers = []
    for tier_key in ("tiers", "prizes", "prizeTiers"):
        if tier_key in item and isinstance(item[tier_key], list):
            for t in item[tier_key]:
                prize = t.get("prize") or t.get("amount") or 0
                rem = t.get("remaining") or t.get("prizesRemaining") or 0
                total = t.get("total") or t.get("totalPrizes") or rem
                if prize > 0:
                    tiers.append({"prize": prize, "remaining": rem, "total": total})
    if not name or not tiers:
        return None
    tiers.sort(key=lambda x: x["prize"], reverse=True)
    return {
        "name": str(name),
        "price": float(price),
        "totalTickets": 0,
        "remainingTickets": 0,
        "gameNumber": game_num,
        "tiers": tiers,
    }


if __name__ == "__main__":
    tickets = scrape()
    import json
    print(f"OR: {len(tickets)} games")
    print(json.dumps(tickets[:2], indent=2))
