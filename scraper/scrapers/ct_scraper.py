"""Connecticut Lottery — per-game HTML scraping. Full tier data + real ticket counts."""
import re
import time
import requests
from bs4 import BeautifulSoup

BASE = "https://www.ctlottery.org"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120"}


def _parse_money(s: str) -> int:
    return int(re.sub(r"[^\d]", "", s))


def scrape() -> list[dict]:
    r = requests.get(f"{BASE}/ScratchGames", headers=HEADERS, timeout=15)
    r.raise_for_status()

    game_ids = re.findall(r"DisplayGameFromPage\((\d+)\)", r.text)
    game_ids = list(dict.fromkeys(game_ids))  # deduplicate, preserve order

    tickets = []
    for gid in game_ids:
        try:
            dr = requests.get(f"{BASE}/ScratchGames/{gid}", headers=HEADERS, timeout=15)
            dr.raise_for_status()
            soup = BeautifulSoup(dr.text, "html.parser")

            tables = soup.find_all("table")
            if len(tables) < 2:
                continue

            # Table 1: game info
            info = {}
            for row in tables[0].find_all("tr"):
                cells = row.find_all("td")
                if len(cells) == 2:
                    key = cells[0].get_text(strip=True).rstrip(":")
                    val = cells[1].get_text(strip=True)
                    info[key] = val

            name_tag = soup.find("h2")
            name = name_tag.get_text(strip=True) if name_tag else f"Game {gid}"

            price_str = info.get("Ticket Price", "")
            if not price_str:
                continue
            price = float(_parse_money(price_str))

            total_tickets_str = info.get("Total # of Tickets", "0")
            total_tickets = int(re.sub(r"[^\d]", "", total_tickets_str)) if total_tickets_str else 0

            # Table 2: prize tiers
            tiers = []
            for row in tables[1].find_all("tr")[1:]:  # skip header
                cells = row.find_all("td")
                if len(cells) < 3:
                    continue
                prize_str = cells[0].get_text(strip=True)
                total_str = cells[1].get_text(strip=True)
                unclaimed_str = cells[2].get_text(strip=True)
                if not prize_str or not prize_str[0].isdigit() and prize_str[0] != "$":
                    continue
                prize = _parse_money(prize_str)
                total = int(re.sub(r"[^\d]", "", total_str)) if total_str else 0
                remaining = int(re.sub(r"[^\d]", "", unclaimed_str)) if unclaimed_str else 0
                if prize > 0:
                    tiers.append({"prize": prize, "remaining": remaining, "total": total})

            tiers.sort(key=lambda t: t["prize"], reverse=True)
            if not tiers:
                continue

            # Estimate remainingTickets from prize ratio if we have totalTickets
            total_prizes = sum(t["total"] for t in tiers)
            remaining_prizes = sum(t["remaining"] for t in tiers)
            if total_tickets > 0 and total_prizes > 0:
                remaining_tickets = int(total_tickets * remaining_prizes / total_prizes)
            else:
                remaining_tickets = 0

            tickets.append({
                "name": name,
                "price": price,
                "totalTickets": total_tickets,
                "remainingTickets": remaining_tickets,
                "gameNumber": gid,
                "tiers": tiers,
                "imageUrl": f"https://www.ctlottery.org/Content/images/Scratch/{gid}.jpg",
            })
            time.sleep(0.5)

        except Exception as e:
            print(f"[CT] Game {gid} failed: {e}")

    return tickets
