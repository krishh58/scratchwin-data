"""Arizona Lottery — cloudscraper for game list, public REST API for prize data."""
import re
import time
import requests
import cloudscraper
from bs4 import BeautifulSoup

SITE_BASE = "https://www.arizonalottery.com"
API_BASE = "https://api.arizonalottery.com/v2"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120",
    "Origin": SITE_BASE,
    "Referer": SITE_BASE + "/",
}


def scrape() -> list[dict]:
    # Use cloudscraper to get game list (Cloudflare-protected HTML)
    cs = cloudscraper.create_scraper()
    r = cs.get(f"{SITE_BASE}/scratchers/", timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # Extract unique game numbers from href="/scratchers/1537-game-name/"
    game_nums = list(dict.fromkeys([
        m.group(1)
        for a in soup.find_all("a", href=True)
        for m in [re.search(r"/scratchers/(\d+)", a["href"])]
        if m
    ]))

    tickets = []
    for gnum in game_nums:
        try:
            dr = requests.get(f"{API_BASE}/scratchers/{gnum}", headers=HEADERS, timeout=15)
            if dr.status_code != 200:
                continue
            g = dr.json()


            price = float(g.get("ticketValue", 0))
            if not price:
                continue

            tiers = []
            for t in g.get("prizeTiers", []):
                if t.get("isOther"):
                    continue
                prize = int(t["prizeAmount"])
                remaining = int(t["count"])
                total = int(t["totalCount"])
                if prize > 0:
                    tiers.append({"prize": prize, "remaining": remaining, "total": total})

            tiers.sort(key=lambda t: t["prize"], reverse=True)
            if not tiers:
                continue

            tickets.append({
                "name": g["gameName"],
                "price": price,
                "totalTickets": 0,
                "remainingTickets": 0,
                "gameNumber": str(g["gameNum"]),
                "tiers": tiers,
            })
            time.sleep(0.3)

        except Exception as e:
            print(f"[AZ] Game {gnum} failed: {e}")

    return tickets
