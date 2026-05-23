"""Missouri Lottery — HTML scraping, full tier data (Total + Unclaimed per tier)."""
import re
import time
import requests
from bs4 import BeautifulSoup

LIST_URL = "https://www.molottery.com/scratchers-list.do"
DETAIL_URL = "https://www.molottery.com/scratchers.do"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://www.molottery.com/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
}


def _parse_money(text: str) -> int:
    return int(re.sub(r"[^\d]", "", text) or "0")


def _get_game_ids() -> list[str]:
    resp = requests.get(LIST_URL, headers=HEADERS, timeout=30)
    soup = BeautifulSoup(resp.text, "html.parser")
    ids = []
    seen = set()
    for a in soup.find_all("a", href=re.compile(r"game=\d+")):
        m = re.search(r"game=(\d+)", a["href"])
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            ids.append(m.group(1))
    return ids


def _scrape_game(game_id: str) -> dict | None:
    try:
        resp = requests.get(DETAIL_URL, params={"method": "d", "game": game_id}, headers=HEADERS, timeout=20)
        soup = BeautifulSoup(resp.text, "html.parser")

        # Name from h1/h2
        name = ""
        for tag in soup.find_all(["h1", "h2", "h3"]):
            t = tag.get_text(strip=True)
            if t and len(t) > 3 and "lottery" not in t.lower() and "scratcher" not in t.lower():
                name = t
                break

        # Price from page text
        price = 0.0
        price_m = re.search(r"Ticket Price[:\s]*\$?([\d.]+)", soup.get_text(), re.I)
        if price_m:
            price = float(price_m.group(1))
        else:
            # Try to find "$X ticket" or "Price: $X"
            price_m = re.search(r"\$(\d+(?:\.\d+)?)\s*(?:ticket|each)", soup.get_text(), re.I)
            if price_m:
                price = float(price_m.group(1))

        # Prize table: Prize Level | Total Prizes | Unclaimed Prizes
        table = None
        for t in soup.find_all("table"):
            hdrs = [th.get_text(strip=True).lower() for th in t.find_all("th")]
            if any("unclaimed" in h for h in hdrs):
                table = t
                break

        if not table:
            return None

        hdrs = [th.get_text(strip=True).lower() for th in table.find_all("th")]
        prize_idx = next((i for i, h in enumerate(hdrs) if "prize" in h or "level" in h), 0)
        total_idx = next((i for i, h in enumerate(hdrs) if "total" in h), None)
        unclaimed_idx = next((i for i, h in enumerate(hdrs) if "unclaimed" in h), None)

        if unclaimed_idx is None:
            return None

        tiers = []
        for row in table.find_all("tr")[1:]:
            cols = [c.get_text(separator=" ", strip=True) for c in row.find_all(["td", "th"])]
            if len(cols) < 2:
                continue
            prize = _parse_money(cols[prize_idx])
            total = _parse_money(cols[total_idx]) if total_idx is not None and total_idx < len(cols) else 0
            remaining = _parse_money(cols[unclaimed_idx]) if unclaimed_idx < len(cols) else 0
            if prize > 0 and total > 0:
                tiers.append({"prize": prize, "remaining": remaining, "total": total})

        tiers.sort(key=lambda t: t["prize"], reverse=True)
        if not tiers or not name:
            return None

        # If price still 0, try to infer from lowest prize (rough)
        if price <= 0:
            return None

        return {
            "name": name,
            "price": price,
            "totalTickets": 0,
            "remainingTickets": 0,
            "gameNumber": game_id,
            "tiers": tiers,
            "imageUrl": f"https://www.molottery.com/media/scratchers/tile/{game_id}.png",
        }
    except Exception:
        return None


def scrape() -> list[dict]:
    game_ids = _get_game_ids()
    tickets = []
    for game_id in game_ids:
        result = _scrape_game(game_id)
        if result:
            tickets.append(result)
        time.sleep(0.5)
    return tickets
