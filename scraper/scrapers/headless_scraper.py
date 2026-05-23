"""
Headless Playwright scraper for JS-rendered state lottery sites.
Intercepts XHR/fetch network calls to capture internal API responses,
then falls back to DOM parsing if no API is found.
"""

import json
import re
import asyncio
from playwright.async_api import async_playwright, Page, Response


# --- Ohio ---
async def scrape_oh(page: Page, intercepts: list) -> list[dict]:
    tickets = []
    try:
        await page.goto("https://www.ohiolottery.com/Games/ScratchOffs/Prizes-Remaining", timeout=30000)
        await page.wait_for_load_state("networkidle", timeout=20000)

        # Try to get data from intercepted API calls first
        for data in intercepts:
            if isinstance(data, list) and len(data) > 0:
                first = data[0]
                if isinstance(first, dict) and any(k in first for k in ["gameName", "name", "GameName"]):
                    return _parse_oh_api(data)

        # DOM fallback — Ohio prizes remaining table
        rows = await page.query_selector_all("table tr, .prizes-remaining tr, .game-row")
        current_game = None

        for row in rows:
            cells = await row.query_selector_all("td, th")
            if not cells:
                continue
            texts = [await c.inner_text() for c in cells]
            texts = [t.strip() for t in texts if t.strip()]

            # Game header row
            if len(texts) == 1 and texts[0]:
                if current_game and current_game["tiers"]:
                    tickets.append(current_game)
                current_game = {"name": texts[0], "price": 0, "totalTickets": 0,
                                "remainingTickets": 0, "gameNumber": "", "tiers": []}
            # Prize row: $Amount  Count remaining
            elif current_game and len(texts) >= 2:
                try:
                    prize = int(re.sub(r"[^\d]", "", texts[0]))
                    remaining = int(re.sub(r"[^\d]", "", texts[1]))
                    if prize > 0:
                        current_game["tiers"].append({"prize": prize, "remaining": remaining})
                except ValueError:
                    pass

        if current_game and current_game["tiers"]:
            tickets.append(current_game)

    except Exception as e:
        print(f"  [OH] Error: {e}")

    return tickets


def _parse_oh_api(data: list) -> list[dict]:
    tickets = []
    games = {}
    for item in data:
        try:
            name = item.get("gameName") or item.get("name") or item.get("GameName", "")
            game_num = str(item.get("gameNumber") or item.get("gameNum") or item.get("GameNumber", ""))
            price = float(item.get("price") or item.get("ticketPrice") or 0)
            prize = int(re.sub(r"[^\d]", "", str(item.get("prizeAmount") or item.get("prize") or 0)))
            remaining = int(item.get("remaining") or item.get("prizesRemaining") or 0)
            remaining_tickets = int(item.get("remainingTickets") or item.get("ticketsRemaining") or 0)

            if game_num not in games:
                games[game_num] = {"name": name, "price": price, "totalTickets": 0,
                                   "remainingTickets": remaining_tickets,
                                   "gameNumber": game_num, "tiers": []}
            if prize > 0:
                games[game_num]["tiers"].append({"prize": prize, "remaining": remaining})
        except Exception:
            continue

    for g in games.values():
        g["tiers"].sort(key=lambda t: t["prize"], reverse=True)
        if g["tiers"]:
            tickets.append(g)
    return tickets


# --- Florida ---
async def scrape_fl(page: Page, intercepts: list) -> list[dict]:
    tickets = []
    try:
        await page.goto("https://www.floridalottery.com/games/scratch-offs", timeout=30000)
        await page.wait_for_load_state("networkidle", timeout=20000)

        for data in intercepts:
            if isinstance(data, list) and len(data) > 0:
                first = data[0]
                if isinstance(first, dict) and any(k in first for k in ["gameName", "name", "ticketPrice"]):
                    return _generic_parse(data)

        # DOM: FL groups by price, prizes on individual game pages
        game_links = await page.query_selector_all("a[href*='scratch-off'], .game-card a, .ticket-card a")
        print(f"  [FL] Found {len(game_links)} game links — need per-game scrape")

    except Exception as e:
        print(f"  [FL] Error: {e}")

    return tickets


# --- California ---
async def scrape_ca(page: Page, intercepts: list) -> list[dict]:
    tickets = []
    try:
        await page.goto("https://www.calottery.com/scratch", timeout=30000)
        await page.wait_for_load_state("networkidle", timeout=20000)

        # CA has a "Top Prizes Remaining" section
        await page.click("text=Top Prizes Remaining", timeout=5000)
        await page.wait_for_load_state("networkidle", timeout=10000)

        for data in intercepts:
            if isinstance(data, list) and len(data) > 0:
                return _generic_parse(data)

        rows = await page.query_selector_all("table tr")
        current_game = None
        for row in rows:
            cells = await row.query_selector_all("td")
            texts = [await c.inner_text() for c in cells]
            texts = [t.strip() for t in texts if t.strip()]
            if len(texts) >= 4:
                try:
                    name = texts[0]
                    price = float(re.sub(r"[^\d.]", "", texts[1]))
                    prize = int(re.sub(r"[^\d]", "", texts[2]))
                    remaining = int(re.sub(r"[^\d]", "", texts[3]))
                    if name and price > 0 and prize > 0:
                        # CA top-prizes table: one row per game, one top prize tier
                        tickets.append({
                            "name": name, "price": price,
                            "totalTickets": 0, "remainingTickets": 0,
                            "gameNumber": "",
                            "tiers": [{"prize": prize, "remaining": remaining}]
                        })
                except ValueError:
                    pass

    except Exception as e:
        print(f"  [CA] Error: {e}")

    return tickets


# --- Texas ---
async def scrape_tx(page: Page, intercepts: list) -> list[dict]:
    tickets = []
    try:
        await page.goto(
            "https://www.texaslottery.com/export/sites/lottery/Games/Scratch_Offs/index.html",
            timeout=30000
        )
        await page.wait_for_load_state("networkidle", timeout=20000)

        for data in intercepts:
            if isinstance(data, list) and len(data) > 0:
                return _generic_parse(data)

        # TX lists games by price tier — each game links to a detail page with prizes
        game_rows = await page.query_selector_all(".game-listing tr, table tr")
        for row in game_rows:
            cells = await row.query_selector_all("td")
            texts = [await c.inner_text() for c in cells]
            texts = [t.strip() for t in texts if t.strip()]
            if len(texts) >= 3:
                try:
                    name = texts[0]
                    price = float(re.sub(r"[^\d.]", "", texts[1]))
                    prize = int(re.sub(r"[^\d]", "", texts[2]))
                    remaining = int(re.sub(r"[^\d]", "", texts[3])) if len(texts) > 3 else 0
                    if name and price > 0:
                        tickets.append({
                            "name": name, "price": price,
                            "totalTickets": 0, "remainingTickets": 0,
                            "gameNumber": "",
                            "tiers": [{"prize": prize, "remaining": remaining}]
                        })
                except ValueError:
                    pass

    except Exception as e:
        print(f"  [TX] Error: {e}")

    return tickets


# --- Michigan ---
async def scrape_mi(page: Page, intercepts: list) -> list[dict]:
    tickets = []
    try:
        await page.goto("https://www.michiganlottery.com/games/instant-games", timeout=30000)
        await page.wait_for_load_state("networkidle", timeout=20000)

        for data in intercepts:
            if isinstance(data, list) and len(data) > 0:
                return _generic_parse(data)

    except Exception as e:
        print(f"  [MI] Error: {e}")

    return tickets


# --- Generic parser for common API response shapes ---
def _generic_parse(data: list) -> list[dict]:
    tickets = []
    games: dict = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            name = (item.get("gameName") or item.get("name") or item.get("GameName") or
                    item.get("game_name") or item.get("ticketName") or "Unknown").strip()
            game_num = str(item.get("gameNumber") or item.get("gameNum") or
                          item.get("game_number") or item.get("id") or "")
            price = float(item.get("price") or item.get("ticketPrice") or
                          item.get("ticket_price") or item.get("cost") or 0)
            prize_raw = (item.get("prizeAmount") or item.get("prize") or
                         item.get("prize_amount") or item.get("amount") or 0)
            prize = int(re.sub(r"[^\d]", "", str(prize_raw)) or "0")
            remaining_raw = (item.get("remaining") or item.get("prizesRemaining") or
                             item.get("prizes_remaining") or item.get("unpaid") or 0)
            remaining = int(remaining_raw or 0)
            remaining_tickets = int(item.get("remainingTickets") or
                                    item.get("tickets_remaining") or 0)

            key = game_num or name
            if key not in games:
                games[key] = {"name": name, "price": price, "totalTickets": 0,
                              "remainingTickets": remaining_tickets,
                              "gameNumber": game_num, "tiers": []}
            if prize > 0:
                games[key]["tiers"].append({"prize": prize, "remaining": remaining})
        except Exception:
            continue

    for g in games.values():
        g["tiers"].sort(key=lambda t: t["prize"], reverse=True)
        if g["tiers"] and g["price"] > 0:
            tickets.append(g)
    return tickets


# Scraper registry
SCRAPERS = {
    "OH": scrape_oh,
    "FL": scrape_fl,
    "CA": scrape_ca,
    "TX": scrape_tx,
    "MI": scrape_mi,
}


async def run_state(code: str, browser) -> list[dict]:
    scraper_fn = SCRAPERS.get(code)
    if not scraper_fn:
        return []

    intercepts = []
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    page = await context.new_page()

    # Intercept all JSON responses
    async def on_response(response: Response):
        try:
            if "json" in (response.headers.get("content-type") or ""):
                body = await response.json()
                if isinstance(body, (list, dict)):
                    intercepts.append(body)
        except Exception:
            pass

    page.on("response", on_response)

    try:
        result = await scraper_fn(page, intercepts)
        return result
    finally:
        await context.close()


async def scrape_all(states: list[str]) -> dict[str, list]:
    results = {}
    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        for code in states:
            print(f"[{code}] Scraping...")
            tickets = await run_state(code, browser)
            results[code] = tickets
            print(f"[{code}] {len(tickets)} games found")
            await asyncio.sleep(2)
        await browser.close()
    return results


def scrape(states: list[str] = None) -> dict[str, list]:
    if states is None:
        states = list(SCRAPERS.keys())
    return asyncio.run(scrape_all(states))
