"""Colorado Lottery — HTML scrape, top prize remaining only (no per-tier breakdown)."""
import re
import time
import requests
from bs4 import BeautifulSoup

URL = "https://www.coloradolottery.com/en/games/scratch/"
BASE = "https://www.coloradolottery.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.coloradolottery.com/",
}


def _fetch_game_image(game_url: str) -> str | None:
    try:
        r = requests.get(game_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        img = soup.find("img", alt="Front")
        if img:
            return img.get("src") or None
    except Exception:
        pass
    return None


def _parse_money(text: str) -> int:
    return int(re.sub(r"[^\d]", "", text) or "0")


def scrape() -> list[dict]:
    resp = requests.get(URL, headers=HEADERS, timeout=20)
    soup = BeautifulSoup(resp.text, "html.parser")

    tickets = []
    for li in soup.find_all("li", class_=re.compile(r"^games_\d+")):
        name_tag = li.find(class_="title") or li.find("p", class_="title")
        price_tag = li.find(class_="price") or li.find("p", class_="price")
        hover = li.find(class_="hover")

        name = name_tag.get_text(strip=True) if name_tag else ""
        price = float(_parse_money(price_tag.get_text(strip=True))) if price_tag else 0.0

        if not name or price <= 0 or not hover:
            continue

        hover_text = hover.get_text(separator=" ", strip=True)
        top_prize_remaining = 0
        top_prize = 0

        rem_m = re.search(r"Top Prizes Remaining[:\s]*(\d[\d,]*)", hover_text, re.I)
        if rem_m:
            top_prize_remaining = _parse_money(rem_m.group(1))

        prize_m = re.search(r"Top Prize[:\s]*\$?([\d,]+)", hover_text, re.I)
        if prize_m:
            top_prize = _parse_money(prize_m.group(1))

        # Try to get game number from href
        link = li.find("a", href=True)
        game_num = ""
        game_href = ""
        if link:
            game_href = link["href"]
            if not game_href.startswith("http"):
                game_href = BASE + game_href
            m = re.search(r"-(\d{4,})[/-]?", link["href"])
            if m:
                game_num = m.group(1)

        if top_prize <= 0:
            continue

        tiers = [{"prize": top_prize, "remaining": top_prize_remaining, "total": max(top_prize_remaining, 1)}]

        image_url = _fetch_game_image(game_href) if game_href else None
        time.sleep(0.2)

        entry = {
            "name": name,
            "price": price,
            "totalTickets": 0,
            "remainingTickets": 0,
            "gameNumber": game_num,
            "tiers": tiers,
        }
        if image_url:
            entry["imageUrl"] = image_url
        tickets.append(entry)

    return tickets
