"""New York Lottery — NY Open Data JSON API. No auth."""
import requests
import re

NY_API = "https://data.ny.gov/resource/nzqa-7unk.json"
HEADERS = {"Accept": "application/json"}


def scrape() -> list[dict]:
    resp = requests.get(NY_API, headers=HEADERS, params={"$limit": 5000}, timeout=20)
    raw = resp.json()

    games: dict[str, dict] = {}
    for row in raw:
        try:
            game_num = str(row.get("game_number", "")).strip()
            if not game_num:
                continue

            if game_num not in games:
                games[game_num] = {
                    "name": row.get("game_name", "Unknown").strip(),
                    "price": 0.0,
                    "totalTickets": 0,
                    "remainingTickets": 0,
                    "gameNumber": game_num,
                    "tiers": [],
                }

            prize_str = re.sub(r"[^\d.]", "", str(row.get("prize_amount", "0")))
            prize = int(float(prize_str)) if prize_str else 0
            remaining = int(row.get("unpaid", 0) or 0)

            total = int(row.get("total", 0) or 0)
            if prize > 0:
                games[game_num]["tiers"].append({"prize": prize, "remaining": remaining, "total": total})

        except Exception:
            continue

    tickets = []
    for game in games.values():
        if game["tiers"]:
            game["tiers"].sort(key=lambda t: t["prize"], reverse=True)
            # Infer price from lowest prize tier as proxy (NY API doesn't include ticket price)
            game["price"] = float(game["tiers"][-1]["prize"]) if game["tiers"] else 1.0
            gnum = game["gameNumber"]
            game["imageUrl"] = f"https://www.nylottery.com/sites/default/files/games/{gnum}.jpg"
            tickets.append(game)

    return tickets
