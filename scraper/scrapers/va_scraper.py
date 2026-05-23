"""Virginia Lottery — REST POST API (top prize remaining only, no per-tier breakdown)."""
import re
import requests

URL = "https://www.valottery.com/api/v1/scratchers"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.valottery.com/",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded",
}


def _parse_prize(text: str) -> int:
    text = str(text).strip().upper()
    if "M" in text:
        num = float(re.sub(r"[^\d.]", "", text.split("M")[0]) or 0)
        return int(num * 1_000_000)
    if "K" in text:
        num = float(re.sub(r"[^\d.]", "", text.split("K")[0]) or 0)
        return int(num * 1_000)
    return int(re.sub(r"[^\d]", "", text) or "0")


def scrape() -> list[dict]:
    tickets = []
    seen = set()
    page = 1

    while True:
        resp = requests.post(
            URL,
            data={"page": page, "pageSize": 20},
            headers=HEADERS,
            timeout=20,
        )
        data = resp.json()
        games = data.get("data", data.get("Games", data.get("games", data if isinstance(data, list) else [])))

        if not games:
            break

        for g in games:
            game_id = str(g.get("GameID") or g.get("gameId") or g.get("Id") or "")
            if not game_id or game_id in seen:
                continue
            seen.add(game_id)

            name = (g.get("Title") or g.get("GameName") or "").strip()
            price_raw = g.get("TicketPrice") or g.get("Cost") or 0
            price = float(re.sub(r"[^\d.]", "", str(price_raw)) or 0)
            top_prize = _parse_prize(str(g.get("TopPrize") or g.get("topPrize") or "0"))
            remaining = int(g.get("PayoutNumber") or g.get("prizesRemaining") or 0)

            if not name or price <= 0 or top_prize <= 0:
                continue

            # VA only gives top-prize remaining — model as single tier
            # total is unknown so set equal to remaining (EV will show 100% for top tier)
            tiers = [{"prize": top_prize, "remaining": remaining, "total": max(remaining, 1)}]

            image_url = g.get("RolloverImageUrl") or None

            tickets.append({
                "name": name,
                "price": price,
                "totalTickets": 0,
                "remainingTickets": 0,
                "gameNumber": game_id,
                "tiers": tiers,
                **({"imageUrl": image_url} if image_url else {}),
            })

        total_pages = data.get("totalPages", 1) if isinstance(data, dict) else 1
        if page >= total_pages:
            break
        page += 1

    return tickets
