"""Georgia Lottery — REST JSON API (paginated, values in cents)."""
import requests

BASE_URL = "https://www.galottery.com/api/v1/instant-games/games"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.galottery.com/",
}


def _fetch_page(start: int) -> dict:
    params = {"start-item": start} if start > 1 else {}
    resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=20)
    return resp.json()


def scrape() -> list[dict]:
    all_games = []

    data = _fetch_page(1)
    all_games.extend(data.get("games", []))

    next_items = data.get("nextItems", 0)
    start = 101
    while start <= next_items:
        data = _fetch_page(start)
        all_games.extend(data.get("games", []))
        start += 100

    tickets = []
    for g in all_games:
        if g.get("validationStatus") != "ACTIVE":
            continue

        price = g.get("ticketPrice", 0) / 100.0
        if price <= 0:
            continue

        tiers = []
        for t in g.get("prizeTiers", []):
            prize = int(t.get("prizeAmount", 0) / 100)
            total = int(t.get("winningTickets", 0))
            paid = int(t.get("paidTickets", 0))
            remaining = max(0, total - paid)
            if prize > 0 and total > 0:
                tiers.append({"prize": prize, "remaining": remaining, "total": total})

        tiers.sort(key=lambda t: t["prize"], reverse=True)
        game_num = str(g.get("gameId", ""))
        image_url = f"https://www.galottery.com/content/dam/portal/images/scratchers-games/{game_num}/ticket.png" if game_num else None
        if tiers:
            tickets.append({
                "name": g.get("gameName", "").strip(),
                "price": price,
                "totalTickets": 0,
                "remainingTickets": 0,
                "gameNumber": game_num,
                "tiers": tiers,
                **({"imageUrl": image_url} if image_url else {}),
            })

    return tickets
