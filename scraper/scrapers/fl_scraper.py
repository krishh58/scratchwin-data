"""Florida Lottery — Azure API, requires x-partner: web header only."""
import requests
import re

DATA_URL = "https://apim-website-prod-eastus.azure-api.net/scratchgamesapp/getscratchinfo"
AEM_URL = "https://www.flalottery.com/content/flalottery-web/us/en/games/scratch-offs.scratch-offs.json"
AEM_BASE = "https://www.flalottery.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://floridalottery.com/",
    "Origin": "https://floridalottery.com",
    "x-partner": "web",
}


def _build_image_map() -> dict[str, str]:
    try:
        r = requests.get(AEM_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        name_map = {}
        for g in r.json().get("data", []):
            norm = re.sub(r"[^A-Z0-9]", "", g.get("name", "").upper())
            path = g.get("teaserImage", "")
            if norm and path:
                name_map[norm] = AEM_BASE + path
        return name_map
    except Exception:
        return {}


def _parse_prize(text: str) -> int:
    return int(re.sub(r"[^\d]", "", str(text)) or "0")


def scrape() -> list[dict]:
    img_map = _build_image_map()
    resp = requests.get(DATA_URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    games = resp.json()

    tickets = []
    for g in games:
        tiers = []
        for t in g.get("OddsTiers", []):
            prize = _parse_prize(t.get("PrizeAmount", "0"))
            remaining = int(t.get("PrizesRemaining", 0) or 0)
            total = int(t.get("TotalPrizes", 0) or 0)
            if prize > 0:
                tiers.append({"prize": prize, "remaining": remaining, "total": total})

        tiers.sort(key=lambda t: t["prize"], reverse=True)
        if not tiers:
            continue

        name = g.get("GameName", "").strip()
        entry = {
            "name": name,
            "price": float(g.get("TicketPrice", 0)),
            "totalTickets": 0,
            "remainingTickets": 0,
            "gameNumber": str(g.get("Id", "")),
            "tiers": tiers,
        }
        norm = re.sub(r"[^A-Z0-9]", "", name.upper())
        if norm in img_map:
            entry["imageUrl"] = img_map[norm]
        tickets.append(entry)
    return tickets
