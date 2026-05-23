"""South Carolina Lottery — prizes remaining table (top prize + total remaining value)."""
import re
import requests
from bs4 import BeautifulSoup
import urllib3

urllib3.disable_warnings()

URL = "https://www.sceducationlottery.com/Games/PrizesRemaining"
IMG_BASE = "https://www.sceducationlottery.com/Images/games/instantgames4x4"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120"}


def _parse_money(s: str) -> int:
    m = re.search(r"[\d,]+", s.replace("$", ""))
    return int(m.group(0).replace(",", "")) if m else 0


def scrape() -> list[dict]:
    r = requests.get(URL, headers=HEADERS, verify=False, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    table = soup.find("table")
    if not table:
        return []

    # Header: Game Name | Ticket Price | Start of Game | Top Prize | Remaining Top Prizes |
    #         Estimated Value of Remaining Prizes | Last Day to Sell | Last Day to Claim
    rows = table.find_all("tr")[1:]
    tickets = []

    for row in rows:
        cells = [c.get_text(separator=" ", strip=True) for c in row.find_all(["td", "th"])]
        if len(cells) < 6:
            continue

        raw_name = cells[0]
        # Skip games that are no longer available
        if "no longer available" in raw_name.lower():
            continue

        # Extract game number from "(#XXXX)" or "(# XXXX)"
        game_m = re.search(r"\(#\s*(\d+)\s*\)", raw_name)
        game_num = game_m.group(1) if game_m else ""
        name = re.sub(r"\s*\(#\s*\d+\s*\)\s*", "", raw_name).strip()

        price_m = re.search(r"\$([\d.]+)", cells[1])
        price = float(price_m.group(1)) if price_m else 0.0
        if price <= 0:
            continue

        top_prize = _parse_money(cells[3])
        remaining_top = _parse_money(cells[4])
        remaining_pool = _parse_money(cells[5])

        if top_prize <= 0:
            continue

        tiers = [{"prize": top_prize, "remaining": remaining_top, "total": remaining_top}]

        # Estimate ticket counts from remaining prize pool and 65% payout rate
        if remaining_pool > 0 and price > 0:
            # remaining_pool ≈ remainingTickets * price * 0.65
            remaining_tickets = int(remaining_pool / (0.65 * price))
            # Assume ~50% sold on average to estimate total (rough)
            total_tickets = remaining_tickets * 2
        else:
            total_tickets = 0
            remaining_tickets = 0

        entry = {
            "name": name,
            "price": price,
            "totalTickets": total_tickets,
            "remainingTickets": remaining_tickets,
            "gameNumber": game_num,
            "tiers": tiers,
        }
        if game_num:
            entry["imageUrl"] = f"{IMG_BASE}/{game_num}.jpg"
        tickets.append(entry)

    return tickets
