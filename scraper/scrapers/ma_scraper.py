"""Massachusetts Lottery — clean REST API, full per-tier prize data."""
import requests

GAMES_URL = "https://www.masslottery.com/api/v1/games"
TIERS_URL = "https://www.masslottery.com/api/v1/instant-game-prizes"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.masslottery.com/",
}


def scrape() -> list[dict]:
    games_resp = requests.get(GAMES_URL, headers=HEADERS, timeout=20)
    all_games = games_resp.json()

    scratch_games = [g for g in all_games if g.get("gameType") == "Scratch"]

    tickets = []
    for g in scratch_games:
        game_id = g.get("id") or g.get("massGameID")
        price = float(g.get("price", 0) or 0)
        if not game_id or price <= 0:
            continue

        try:
            tiers_resp = requests.get(
                TIERS_URL,
                params={"gameID": game_id},
                headers=HEADERS,
                timeout=20,
            )
            data = tiers_resp.json()
        except Exception:
            continue

        prize_tiers = data.get("prizeTiers", [])
        tiers = []
        for t in prize_tiers:
            prize = int(t.get("prizeAmount", 0) or 0)
            total = int(t.get("totalPrizes", 0) or 0)
            remaining = int(t.get("prizesRemaining", 0) or 0)
            if prize > 0 and total > 0:
                tiers.append({"prize": prize, "remaining": remaining, "total": total})

        tiers.sort(key=lambda t: t["prize"], reverse=True)
        icon = g.get("icon") or {}
        raw_url = icon.get("url", "") if isinstance(icon, dict) else ""
        image_url = ("https:" + raw_url) if raw_url.startswith("//") else (raw_url or None)
        if tiers:
            tickets.append({
                "name": (g.get("name") or data.get("gameName", "")).strip(),
                "price": price,
                "totalTickets": 0,
                "remainingTickets": 0,
                "gameNumber": str(game_id),
                "tiers": tiers,
                **({"imageUrl": image_url} if image_url else {}),
            })

    return tickets
