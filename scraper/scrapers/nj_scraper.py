"""New Jersey Lottery — REST API (no auth required)."""
import requests

API_URL = "https://www.njlottery.com/api/v1/instant-games/games/"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.njlottery.com/",
}


def scrape() -> list[dict]:
    resp = requests.get(
        API_URL,
        params={"size": 1000, "validationStatus": "ACTIVE"},
        headers=HEADERS,
        timeout=20,
    )
    games = resp.json().get("games", [])

    tickets = []
    for g in games:
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
        game_id = str(g["gameId"])
        padded = game_id.zfill(5)
        image_url = f"https://www.njlottery.com/content/dam/portal/images/instant-games/{padded}/ticket.png"
        if tiers:
            tickets.append({
                "name": g["gameName"].strip(),
                "price": price,
                "totalTickets": g.get("totalTicketsPrinted", 0) or 0,
                "remainingTickets": 0,
                "gameNumber": game_id,
                "tiers": tiers,
                "imageUrl": image_url,
            })

    return tickets
