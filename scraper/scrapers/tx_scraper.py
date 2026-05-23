"""Texas Lottery — HTML table (server-side rendered, no JSON API)."""
import re
import requests
from bs4 import BeautifulSoup

URL = "https://www.texaslottery.com/export/sites/lottery/Games/Scratch_Offs/all.html"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"}


def _parse_int(text: str) -> int:
    return int(re.sub(r"[^\d]", "", text) or "0")


def scrape() -> list[dict]:
    resp = requests.get(URL, headers=HEADERS, timeout=20)
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table")
    if not table:
        return []

    rows = table.find_all("tr")[1:]  # skip header

    games: dict[str, dict] = {}
    current_game_num = None

    for row in rows:
        cells = row.find_all(["th", "td"])
        if not cells:
            continue

        cols = [c.get_text(strip=True) for c in cells]
        if len(cols) < 6:
            continue

        game_num = cols[0]
        if game_num:
            current_game_num = game_num
            price_str = cols[2]
            name = cols[4]
            games[current_game_num] = {
                "name": name,
                "price": float(_parse_int(price_str)),
                "gameNumber": game_num,
                "tiers": [],
            }

        if current_game_num is None:
            continue

        prize_str = cols[5] if len(cols) > 5 else ""
        total_str = cols[6] if len(cols) > 6 else ""
        claimed_str = cols[7] if len(cols) > 7 else ""

        prize = _parse_int(prize_str)
        total = _parse_int(total_str)
        claimed = _parse_int(claimed_str)
        remaining = max(0, total - claimed)

        if prize > 0 and total > 0:
            games[current_game_num]["tiers"].append({
                "prize": prize,
                "remaining": remaining,
                "total": total,
            })

    IMG_BASE = "https://www.texaslottery.com/export/sites/lottery/Images/scratchoffs"
    tickets = []
    for g in games.values():
        tiers = sorted(g["tiers"], key=lambda t: t["prize"], reverse=True)
        if tiers and g["price"] > 0:
            gnum = g["gameNumber"]
            entry = {
                "name": g["name"],
                "price": g["price"],
                "totalTickets": 0,
                "remainingTickets": 0,
                "gameNumber": gnum,
                "tiers": tiers,
                "imageUrl": f"{IMG_BASE}/{gnum}_img1.gif",
            }
            tickets.append(entry)

    return tickets
