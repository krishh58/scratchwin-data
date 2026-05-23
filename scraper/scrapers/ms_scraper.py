"""Mississippi Lottery — per-game HTML. Full tier data (Original + Remaining Prize Count)."""
import re
import time
import requests
from bs4 import BeautifulSoup

BASE = "https://www.mslottery.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120"}


def _parse_money(s: str) -> int:
    return int(re.sub(r"[^\d]", "", s)) if re.sub(r"[^\d]", "", s) else 0


def scrape() -> list[dict]:
    r = requests.get(f"{BASE}/instantgames/", headers=HEADERS, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # Collect unique game URLs
    game_urls = list(dict.fromkeys([
        a["href"] for a in soup.find_all("a", href=True)
        if "/instantgames/" in a["href"] and len(a["href"]) > len(f"{BASE}/instantgames/")
    ]))

    tickets = []
    for url in game_urls:
        try:
            dr = requests.get(url, headers=HEADERS, timeout=15)
            dr.raise_for_status()
            dsoup = BeautifulSoup(dr.text, "html.parser")

            tables = dsoup.find_all("table")
            if len(tables) < 2:
                continue

            # Table 0: game info (Ticket Price, Top Prize, Overall Odds, Game Number)
            info = {}
            for row in tables[0].find_all("tr"):
                cells = row.find_all("td")
                if len(cells) == 2:
                    info[cells[0].get_text(strip=True)] = cells[1].get_text(strip=True)

            price_str = info.get("Ticket Price", "")
            if not price_str:
                continue
            price = float(_parse_money(price_str))
            game_num = info.get("Game Number", "")

            # Game name from h1/h2
            name_tag = dsoup.find("h1") or dsoup.find("h2")
            name = name_tag.get_text(strip=True) if name_tag else url.split("/")[-2].replace("-", " ").title()

            # Table 1: prize tiers (Prize Value | Original Prize Count | Remaining Prize Count)
            tiers = []
            rows = tables[1].find_all("tr")
            # Skip header rows (th elements)
            for row in rows:
                cells = row.find_all(["td", "th"])
                if not cells or cells[0].name == "th":
                    continue
                if len(cells) < 3:
                    continue
                prize = _parse_money(cells[0].get_text(strip=True))
                total = _parse_money(cells[1].get_text(strip=True))
                remaining = _parse_money(cells[2].get_text(strip=True))
                if prize > 0 and total > 0:
                    tiers.append({"prize": prize, "remaining": remaining, "total": total})

            tiers.sort(key=lambda t: t["prize"], reverse=True)
            if tiers:
                tickets.append({
                    "name": name,
                    "price": price,
                    "totalTickets": 0,
                    "remainingTickets": 0,
                    "gameNumber": game_num,
                    "tiers": tiers,
                })
            time.sleep(0.5)

        except Exception as e:
            print(f"[MS] {url} failed: {e}")

    return tickets
