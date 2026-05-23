"""Michigan Lottery — GraphQL API (direct POST, no session required)."""
import requests

API_URL = "https://www.michiganlottery.com/api"
HEADERS = {
    "Content-Type": "application/json",
    "Referer": "https://www.michiganlottery.com/",
    "Origin": "https://www.michiganlottery.com",
    "User-Agent": "Mozilla/5.0",
}

PRIZES_QUERY = """
{
  getRetailTopPrizesRemainingByGameType(gameType: "INSTANT") {
    cms_game_igt_id
    game_name
    prizesRemainingData {
      prize_amount
      prizes_remaining
      starting_amount
    }
  }
}
"""

GAMES_QUERY = """
{
  getCMSGames(removeHiddenGames: false) {
    name
    igtId
    canBuyInStore
    isInstantGame
    displayedTicketPrice
    logoUrl
  }
}
"""


def _parse_price(price_str: str) -> float:
    try:
        return float(price_str.replace("$", "").replace(",", "").strip())
    except (ValueError, AttributeError):
        return 0.0


def scrape() -> list[dict]:
    prizes_resp = requests.post(API_URL, json={"query": PRIZES_QUERY, "variables": None}, headers=HEADERS, timeout=30)
    prizes_data = prizes_resp.json().get("data", {}).get("getRetailTopPrizesRemainingByGameType", [])

    games_resp = requests.post(API_URL, json={"query": GAMES_QUERY, "variables": None}, headers=HEADERS, timeout=30)
    games_data = games_resp.json().get("data", {}).get("getCMSGames", [])

    # Build metadata lookup: igtId -> {name, price, imageUrl}
    meta = {}
    for g in games_data:
        if g.get("canBuyInStore") and g.get("isInstantGame"):
            igt_id = g.get("igtId")
            price = _parse_price(g.get("displayedTicketPrice") or "0")
            if igt_id and price > 0:
                logo = g.get("logoUrl") or ""
                image_url = ("https:" + logo) if logo.startswith("//") else (logo or None)
                meta[str(igt_id)] = {"name": g["name"].strip(), "price": price, "imageUrl": image_url}

    tickets = []
    for game in prizes_data:
        igt_id = str(game.get("cms_game_igt_id", ""))
        if igt_id not in meta:
            continue

        tiers = []
        for t in game.get("prizesRemainingData", []):
            prize = int(t.get("prize_amount", 0))
            remaining = int(t.get("prizes_remaining", 0))
            total = int(t.get("starting_amount", 0))
            if prize > 0 and total > 0:
                tiers.append({"prize": prize, "remaining": remaining, "total": total})

        tiers.sort(key=lambda t: t["prize"], reverse=True)
        if tiers:
            info = meta[igt_id]
            entry: dict = {
                "name": info["name"],
                "price": info["price"],
                "totalTickets": 0,
                "remainingTickets": 0,
                "gameNumber": igt_id,
                "tiers": tiers,
            }
            if info.get("imageUrl"):
                entry["imageUrl"] = info["imageUrl"]
            tickets.append(entry)

    return tickets
