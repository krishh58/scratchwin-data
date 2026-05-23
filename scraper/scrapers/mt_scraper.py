"""Montana Lottery — scratch game prize/odds tables (12-page paginated listing).
MT does not publish remaining prize counts; total counts are estimated from
odds and industry-typical ticket print runs. remainingTickets = totalTickets
(full-game odds shown, not depleted remaining).
"""
import re
import time
import requests
from bs4 import BeautifulSoup

_BASE = "https://montanalottery.com"
_PAGE_URL = f"{_BASE}/scratch-games/?e-page-eeedf9c={{page}}"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120"}
_MAX_PAGES = 15

# Typical total ticket print runs by price (industry averages)
_TICKET_ESTIMATE = {1: 300_000, 2: 500_000, 3: 600_000, 5: 1_000_000,
                    10: 1_500_000, 20: 2_000_000, 30: 2_500_000, 50: 3_000_000}


def _parse_odds(s: str) -> float:
    """Parse '1:74,160.00' → 74160.0"""
    m = re.search(r"1\s*[:]\s*([\d,]+(?:\.\d+)?)", s)
    if not m:
        return 0.0
    return float(m.group(1).replace(",", ""))


def _parse_price(s: str) -> float:
    m = re.search(r"\$([\d.]+)", s)
    return float(m.group(1)) if m else 0.0


def _parse_money(s: str) -> int:
    s = s.replace(",", "").replace("$", "").strip()
    m = re.search(r"\d+", s)
    return int(m.group(0)) if m else 0


def _scrape_page(page_num: int) -> list[dict]:
    url = _PAGE_URL.format(page=page_num) if page_num > 1 else f"{_BASE}/scratch-games/"
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    games = []
    # Each game block: h2 heading with "$Price GameName", followed by optional h3 "Overall Odds 1:X", then table
    headings = soup.find_all("h2")
    for h2 in headings:
        heading_text = h2.get_text(strip=True)
        price = _parse_price(heading_text)
        if price <= 0:
            continue

        # Strip price from name
        name = re.sub(r"^\s*\$[\d.]+\s*", "", heading_text).strip()
        if not name:
            continue

        # Find the table that follows this heading
        table = h2.find_next("table")
        if not table:
            continue

        # Estimate total tickets
        price_int = int(price)
        total_n = _TICKET_ESTIMATE.get(price_int, int(price_int * 150_000))

        # Parse prize rows: WIN | PRIZE | ODDS
        tiers = []
        for row in table.find_all("tr")[1:]:
            cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
            if len(cells) < 3:
                continue
            prize = _parse_money(cells[1])  # PRIZE column
            odds_denom = _parse_odds(cells[2])  # ODDS column
            if prize <= 0 or odds_denom <= 0:
                continue
            count = max(1, round(total_n / odds_denom))
            tiers.append({"prize": prize, "remaining": count, "total": count})

        if not tiers:
            continue

        tiers.sort(key=lambda t: t["prize"], reverse=True)

        games.append({
            "name": name,
            "price": price,
            "totalTickets": total_n,
            "remainingTickets": total_n,
            "gameNumber": "",
            "tiers": tiers,
        })

    return games


def scrape() -> list[dict]:
    all_games = []
    seen_names: set[str] = set()

    for page in range(1, _MAX_PAGES + 1):
        try:
            games = _scrape_page(page)
            if not games:
                break
            for g in games:
                if g["name"] not in seen_names:
                    seen_names.add(g["name"])
                    all_games.append(g)
            time.sleep(0.5)
        except Exception as e:
            print(f"[MT] Page {page} error: {e}")
            break

    return all_games
