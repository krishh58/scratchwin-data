"""Oklahoma Lottery — REST JSON API, full per-tier prize data in one call."""
import requests

URL = "https://www.lottery.ok.gov/scratchers/get"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.lottery.ok.gov/",
}


def scrape() -> list[dict]:
    resp = requests.get(URL, headers=HEADERS, timeout=20)
    data = resp.json()
    games = data.get("Games", data if isinstance(data, list) else [])

    tickets = []
    for g in games:
        if not g.get("IsActive", True):
            continue

        name = (g.get("Name") or "").strip()
        price = float(g.get("Price", 0) or 0)
        game_id = str(g.get("GameId", ""))

        if not name or price <= 0:
            continue

        tiers = []
        for t in g.get("Prizes", []):
            prize = int(t.get("PrizeAmount", 0) or 0)
            total = int(t.get("TotalPrizes", 0) or 0)
            remaining = int(t.get("RemainingPrizes", 0) or 0)
            if prize > 0 and total > 0:
                tiers.append({"prize": prize, "remaining": remaining, "total": total})

        tiers.sort(key=lambda t: t["prize"], reverse=True)
        if tiers:
            thumb_id = str(g.get("ThumbnailImage") or g.get("PrimaryImage") or game_id)
            entry = {
                "name": name,
                "price": price,
                "totalTickets": int(g.get("TicketsPrinted", 0) or 0),
                "remainingTickets": 0,
                "gameNumber": game_id,
                "tiers": tiers,
                "imageUrl": f"https://lottery.ok.gov/scratchers/image/{thumb_id}",
            }
            tickets.append(entry)

    return tickets
