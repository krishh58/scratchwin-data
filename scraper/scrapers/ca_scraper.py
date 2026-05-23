"""California Lottery — public REST API, no auth."""
import requests

DATA_URL = "https://www.calottery.com/api/games/scratchers"
HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.calottery.com/"}


def scrape() -> list[dict]:
    games = requests.get(DATA_URL, headers=HEADERS, timeout=20).json().get("games", [])
    tickets = []
    for g in games:
        tiers = []
        for t in g.get("prizeTiers", []):
            prize = int(t.get("value", 0))
            total = int(t.get("totalNumberOfPrizes", 0))
            cashed = int(t.get("numberOfPrizesCashed", 0))
            remaining = total - cashed
            if prize > 0 and remaining >= 0:
                tiers.append({"prize": prize, "remaining": remaining, "total": total})

        tiers.sort(key=lambda t: t["prize"], reverse=True)
        image_url = g.get("unScratchedImage") or g.get("cardImage") or None
        if tiers:
            tickets.append({
                "name": g.get("name", "").strip(),
                "price": float(g.get("price", 0)),
                "totalTickets": 0,
                "remainingTickets": 0,
                "gameNumber": str(g.get("gameNumber", "")),
                "tiers": tiers,
                **({"imageUrl": image_url} if image_url else {}),
            })
    return tickets
