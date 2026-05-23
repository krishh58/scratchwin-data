"""Washington Lottery — full per-tier data embedded as JSON in HTML page."""
import json
import re
import requests
from bs4 import BeautifulSoup

URL = "https://www.walottery.com/Scratch/Explorer.aspx"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.walottery.com/",
}


def scrape() -> list[dict]:
    resp = requests.get(URL, headers=HEADERS, timeout=20)
    soup = BeautifulSoup(resp.text, "html.parser")

    data = None
    for script in soup.find_all("script"):
        text = script.string or ""
        m = re.search(r"WaLottery\.Scratch\.data\s*=\s*\{[^;]*all:\s*JSON\.parse\('(.+?)'\)", text, re.DOTALL)
        if m:
            raw = m.group(1).replace("\\'", "'")
            data = json.loads(raw)
            break

    if not data:
        return []

    tickets = []
    for g in data.get("Games", []):
        name = g.get("GameName", "").strip()
        price = float(g.get("Cost", 0) or 0)
        game_id = str(g.get("Id", ""))
        if not name or price <= 0:
            continue

        tiers = []
        for t in g.get("Prizes", []):
            prize = int(re.sub(r"[^\d]", "", str(t.get("PrizeAmount", 0) or 0)) or 0)
            total = int(re.sub(r"[^\d]", "", str(t.get("TotalPrizesNumber", 0) or 0)) or 0)
            remaining = int(re.sub(r"[^\d]", "", str(t.get("PrizesRemainingNumber", 0) or 0)) or 0)
            if prize > 0 and total > 0:
                tiers.append({"prize": prize, "remaining": remaining, "total": total})

        tiers.sort(key=lambda t: t["prize"], reverse=True)
        image_url = g.get("UnscratchedImageUrl") or g.get("GridImageUrl") or None
        if tiers:
            tickets.append({
                "name": name,
                "price": price,
                "totalTickets": int(re.sub(r"[^\d]", "", str(g.get("TicketsPrinted", 0) or 0)) or 0),
                "remainingTickets": 0,
                "gameNumber": game_id,
                "tiers": tiers,
                **({"imageUrl": image_url} if image_url else {}),
            })

    return tickets
