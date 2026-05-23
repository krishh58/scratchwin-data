"""Nebraska Lottery — prizes-remaining page. Remaining-only (top prizes only)."""
import re
import requests
from bs4 import BeautifulSoup

URL = "https://nelottery.com/homeapp/scratch/prizesremaining/web"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120"}


def _parse_money(s: str) -> int:
    return int(re.sub(r"[^\d]", "", s)) if re.sub(r"[^\d]", "", s) else 0


def scrape() -> list[dict]:
    r = requests.get(URL, headers=HEADERS, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    tickets = []
    for block in soup.find_all("div", class_="gameBlock"):
        # Price
        price_el = block.find(class_="ballDollar")
        if not price_el:
            continue
        price = float(re.sub(r"[^\d.]", "", price_el.get_text(strip=True)))

        # Name and game number
        name_block = block.find(class_="nameBlock")
        if not name_block:
            continue
        spans = name_block.find_all("span")
        game_num = ""
        name = f"Game {price}"
        for sp in spans:
            txt = sp.get_text(strip=True)
            if txt.startswith("#"):
                game_num = txt[1:]
            elif sp.get("style") and "bold" in sp.get("style", ""):
                name = txt

        # Prize tiers from prizeRemBlock table
        table = block.find("table", class_="prizeRemBlock")
        if not table:
            continue

        tiers = []
        for row in table.find_all("tr", class_="prizesBlock"):
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
            prize = _parse_money(cells[0].get_text(strip=True))
            remaining = _parse_money(cells[1].get_text(strip=True))
            if prize > 0:
                tiers.append({"prize": prize, "remaining": remaining, "total": remaining})

        tiers.sort(key=lambda t: t["prize"], reverse=True)
        if tiers:
            entry = {
                "name": name,
                "price": price,
                "totalTickets": 0,
                "remainingTickets": 0,
                "gameNumber": game_num,
                "tiers": tiers,
            }
            if game_num:
                entry["imageUrl"] = f"https://nelottery.com/homeapp/static/shared/images/scratch/tiles/{game_num}_tile.jpg"
            tickets.append(entry)

    return tickets
