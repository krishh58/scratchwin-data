"""Ohio Lottery — JWT auth + REST API. Updated daily ~6am."""
import os
import requests
import re

AUTH_URL = "https://authapi-solutions.ohiolottery.com/1.0/Authentication/Login"
DATA_URL = "https://api-solutions.ohiolottery.com/1.0/Games/ScratchOffs/ScratchOffGame/GetFullPrizesRemainingList"
GAMES_URL = "https://api-solutions.ohiolottery.com/1.0/Games/ScratchOffs/ScratchOffGame/GetAllGames"
HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.ohiolottery.com/"}

_OH_USER = os.environ.get("OH_USERNAME", "mobilepublic@mtllc.com")
_OH_PASS = os.environ.get("OH_PASSWORD", "R7V5Sz8@")


def _token() -> str:
    resp = requests.post(AUTH_URL, json={"userName": _OH_USER, "password": _OH_PASS}, headers=HEADERS, timeout=15)
    return resp.json()["data"]["token"]


def _parse_odds(odds_str: str) -> float | None:
    """Parse '1 in 2.87', '1:3.13', '1in 4.02' -> float ratio."""
    nums = re.findall(r"\d+\.?\d*", str(odds_str))
    if len(nums) >= 2:
        try:
            return float(nums[-1])
        except ValueError:
            pass
    return None


def scrape() -> list[dict]:
    token = _token()
    auth_headers = {**HEADERS, "Authorization": f"Bearer {token}"}

    # Fetch prize tiers (current remaining counts)
    prizes = requests.get(DATA_URL, headers=auth_headers, timeout=20).json()["data"]

    # Fetch game metadata (includes oddsOfWinning for each game)
    all_games_raw = requests.get(GAMES_URL, headers=auth_headers, timeout=20).json()["data"]

    # Build odds map and image map: gameNumber (str) -> value
    odds_map: dict[str, float] = {}
    image_map: dict[str, str] = {}
    for games_list in all_games_raw.values():
        for g in games_list:
            ratio = _parse_odds(g.get("oddsOfWinning", ""))
            if ratio:
                odds_map[str(g["gameNumber"])] = ratio
            raw_url = g.get("gameGraphicThumbURL") or g.get("gameGraphicURL") or ""
            if raw_url:
                image_map[str(g["gameNumber"])] = (
                    "https://www.ohiolottery.com" + raw_url
                    if raw_url.startswith("/") else raw_url
                )

    tickets = []
    for g in prizes:
        tiers = []
        for t in g.get("prizeRemainingValues", []):
            prize = int(t["prizeValue"])
            remaining = int(t["prizesLeft"])
            total = int(t.get("totalPrizes", 0))
            if prize > 0:
                tiers.append({"prize": prize, "remaining": remaining, "total": total})

        tiers.sort(key=lambda t: t["prize"], reverse=True)
        if not tiers:
            continue

        gnum = str(g["gameCode"])
        odds_ratio = odds_map.get(gnum)

        if odds_ratio:
            total_winners = sum(t["total"] for t in tiers)
            remaining_winners = sum(t["remaining"] for t in tiers)
            total_tickets = int(total_winners * odds_ratio)
            remaining_tickets = int(remaining_winners * odds_ratio)
        else:
            total_tickets = 0
            remaining_tickets = 0

        image_url = image_map.get(gnum)
        tickets.append({
            "name": g["gameName"].strip(),
            "price": float(g["ticketPrice"]),
            "totalTickets": total_tickets,
            "remainingTickets": remaining_tickets,
            "gameNumber": gnum,
            "tiers": tiers,
            **({"imageUrl": image_url} if image_url else {}),
        })

    return tickets
