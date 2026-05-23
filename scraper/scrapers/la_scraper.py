"""Louisiana Lottery — JS-rendered HTML via Playwright."""
from time import sleep
import re
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

BASE_URL = "https://louisianalottery.com"
GAME_LIST_URL = f"{BASE_URL}/top-prizes-remaining/"


def _parse_int(text: str) -> int:
    return int(re.sub(r"[^\d]", "", text) or "0")


def _get_html(browser, url: str) -> str:
    page = browser.new_page()
    try:
        page.goto(url, timeout=25000, wait_until="networkidle")
        page.wait_for_timeout(1500)
        return page.content()
    finally:
        page.close()


def scrape() -> list[dict]:
    games = []
    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        try:
            # Step 1: game list
            html = _get_html(browser, GAME_LIST_URL)
            soup = BeautifulSoup(html, "html.parser")
            table = soup.find("table")
            if not table:
                return []

            rows = table.find_all("tr")[1:]  # skip header
            game_entries = []
            for row in rows:
                cells = row.find_all("td")
                if len(cells) < 7:
                    continue
                link = row.find("a")
                if not link:
                    continue
                game_entries.append({
                    "game_num": cells[1].get_text(strip=True),
                    "price": float(_parse_int(cells[2].get_text(strip=True))),
                    "name": cells[3].get_text(strip=True),
                    "url": link["href"],
                })

            # Step 2: detail pages
            for entry in game_entries:
                try:
                    dhtml = _get_html(browser, entry["url"])
                    dsoup = BeautifulSoup(dhtml, "html.parser")
                    dtable = dsoup.find("table")
                    if not dtable:
                        continue

                    tiers = []
                    for drow in dtable.find_all("tr")[1:]:
                        dcells = drow.find_all("td")
                        if len(dcells) < 5:
                            continue
                        prize = _parse_int(dcells[0].get_text())
                        total = _parse_int(dcells[2].get_text())
                        remaining = _parse_int(dcells[4].get_text())
                        if prize > 0 and total > 0:
                            tiers.append({"prize": prize, "remaining": remaining, "total": total})

                    if tiers:
                        tiers.sort(key=lambda t: t["prize"], reverse=True)
                        games.append({
                            "name": entry["name"],
                            "price": entry["price"],
                            "totalTickets": 0,
                            "remainingTickets": 0,
                            "gameNumber": entry["game_num"],
                            "tiers": tiers,
                        })
                except Exception:
                    continue
        finally:
            browser.close()

    return games
