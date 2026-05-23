"""New Hampshire Lottery — Gambyt REST API. Full tier data (startingCount/remainingCount)."""
import re
import requests
from collections import defaultdict

BASE = "https://prod.game-data.gambytservices.com"
API_KEY = "1c4c69db-274c-4f59-95c5-3211cd74e9d8"
HEADERS = {"User-Agent": "Mozilla/5.0", "X-API-Key": API_KEY}
NH_PRIZES_URL = "https://www.nhlottery.com/Scratch-Tickets/Prizes-Remaining"
NH_WEB_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"}


def _fetch_image_map() -> dict[str, str]:
    """Scrape NH prizes page for Contentful image URLs keyed by NH game number."""
    try:
        r = requests.get(NH_PRIZES_URL, headers=NH_WEB_HEADERS, timeout=20)
        all_urls = re.findall(r'"imageUrl"\s*:\s*"(https://images\.ctfassets\.net/[^"]+)"', r.text)
        img_map: dict[str, str] = {}
        for url in all_urls:
            # Match NH-XXXX or NH_XXXX in filename portion
            m = re.search(r'[/]NH[-_](\d{4})[^/]*\.(?:jpg|jpeg|gif|png)', url, re.I)
            if m:
                gnum = m.group(1)
                if gnum not in img_map:
                    img_map[gnum] = url
        return img_map
    except Exception:
        return {}


def scrape() -> list[dict]:
    img_map = _fetch_image_map()
    games = requests.get(f"{BASE}/v1/instant-games", headers=HEADERS, timeout=15).json()
    prizes_raw = requests.get(f"{BASE}/v1/instant-game/prizes-remaining", headers=HEADERS, timeout=15).json()["prizesRemaining"]

    # Group prize tiers by game ID
    prizes_by_game = defaultdict(list)
    for p in prizes_raw:
        prizes_by_game[p["instantGameId"]].append(p)

    # Only retail scratch tickets
    retail_scratch = [g for g in games if g["salesChannel"] == "RETAIL" and g["gameType"] == "SCRATCH"]

    tickets = []
    for g in retail_scratch:
        gprizes = prizes_by_game.get(g["id"], [])
        if not gprizes:
            continue

        price_cents = g["ticketCostOptionsInCents"][0] if g["ticketCostOptionsInCents"] else 0
        if not price_cents:
            continue
        price = price_cents / 100.0

        tiers = []
        for p in gprizes:
            prize = int(p["prizeAmountInDollars"])
            total = int(p["startingCount"])
            remaining = int(p["remainingCount"])
            if prize > 0:
                tiers.append({"prize": prize, "remaining": remaining, "total": total})

        tiers.sort(key=lambda t: t["prize"], reverse=True)
        if not tiers:
            continue

        game_id = g.get("gameId", "")
        entry: dict = {
            "name": g["name"],
            "price": price,
            "totalTickets": 0,
            "remainingTickets": 0,
            "gameNumber": game_id,
            "tiers": tiers,
        }
        if game_id in img_map:
            entry["imageUrl"] = img_map[game_id]
        tickets.append(entry)

    return tickets
