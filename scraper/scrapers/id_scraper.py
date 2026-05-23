"""Idaho Lottery — prizes-remaining page. Remaining-only (no totals published)."""
import re
import requests
from bs4 import BeautifulSoup

URL = "https://www.idaholottery.com/games/scratch?view=remaining_prizes"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120"}


def scrape() -> list[dict]:
    r = requests.get(URL, headers=HEADERS, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    tickets = []
    for li in soup.find_all("li", class_="game"):
        content = li.find("div", class_="game__content")
        if not content:
            continue

        # Game ID and image from data-game-id + game__image background-image style
        game_id = li.get("data-game-id", "")
        image_url = None
        img_div = li.find("div", class_="game__image")
        if img_div:
            style = img_div.get("style", "")
            m = re.search(r"url\(['\"]?(https?://[^'\")\s]+)['\"]?\)", style)
            if m:
                # Strip query string (VersionId cache param)
                image_url = m.group(1).split("?")[0]

        # Game name from heading
        heading = content.find(["h2", "h3", "h4", "h5"])
        if not heading:
            continue
        name = heading.get_text(strip=True)

        # Price from game__info-price span
        price_el = content.find(class_="game__info-price")
        if not price_el:
            continue
        price_str = re.sub(r"[^\d.]", "", price_el.get_text(strip=True))
        if not price_str:
            continue
        price = float(price_str)

        # Prize tiers from scratch-prizes table (remaining only)
        table = content.find("table", class_="scratch-prizes")
        if not table:
            continue

        tiers = []
        for row in table.find_all("tr")[1:]:
            prize_el = row.find(class_="prizes-prize")
            rem_el = row.find(class_="prizes-remaining")
            if not prize_el or not rem_el:
                continue
            prize = int(re.sub(r"[^\d]", "", prize_el.get_text(strip=True)))
            remaining = int(re.sub(r"[^\d]", "", rem_el.get_text(strip=True)) or "0")
            if prize > 0:
                tiers.append({"prize": prize, "remaining": remaining, "total": remaining})

        tiers.sort(key=lambda t: t["prize"], reverse=True)
        if tiers:
            entry = {
                "name": name,
                "price": price,
                "totalTickets": 0,
                "remainingTickets": 0,
                "gameNumber": game_id,
                "tiers": tiers,
            }
            if image_url:
                entry["imageUrl"] = image_url
            tickets.append(entry)

    return tickets
