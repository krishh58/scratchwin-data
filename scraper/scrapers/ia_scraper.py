"""Iowa Lottery — single prizes-remaining page, full tier data with claimed/unclaimed."""
import re
import requests
import cloudscraper
from bs4 import BeautifulSoup

URL = "https://www.ialottery.com/Pages/Games/RemainingPrizes.aspx"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120"}


def _parse_money(s: str) -> int:
    m = re.search(r"[\d,]+", s)
    return int(m.group(0).replace(",", "")) if m else 0


def scrape() -> list[dict]:
    scraper = cloudscraper.create_scraper()
    r = scraper.get(URL, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    table = soup.find("table")
    if not table:
        return []

    rows = table.find_all("tr")[1:]  # skip header

    # Group rows by game name
    games: dict[str, dict] = {}
    order: list[str] = []

    for row in rows:
        cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
        if len(cells) < 6:
            continue

        raw_name = cells[0]
        game_type = cells[1]
        if game_type != "Scratch":
            continue

        price_str = cells[2]
        prize_str = cells[3]
        claimed_str = cells[4]
        unclaimed_str = cells[5]

        # Extract game number from name like "$100 STACKED  (788)"
        m_num = re.search(r"\((\d+)\)", raw_name)
        game_num = m_num.group(1) if m_num else raw_name
        name = re.sub(r"\s*\(\d+\)\s*$", "", raw_name).strip()

        price = float(re.search(r"[\d.]+", price_str).group()) if re.search(r"\d", price_str) else 0.0
        prize = _parse_money(prize_str)
        claimed = int(re.sub(r"[^\d]", "", claimed_str)) if re.search(r"\d", claimed_str) else 0
        unclaimed = int(re.sub(r"[^\d]", "", unclaimed_str)) if re.search(r"\d", unclaimed_str) else 0
        total = claimed + unclaimed

        if prize <= 0 or price <= 0:
            continue

        if game_num not in games:
            games[game_num] = {
                "name": name,
                "price": price,
                "gameNumber": game_num,
                "tiers": [],
            }
            order.append(game_num)

        games[game_num]["tiers"].append({
            "prize": prize,
            "remaining": unclaimed,
            "total": total,
        })

    tickets = []
    for game_num in order:
        g = games[game_num]
        tiers = sorted(g["tiers"], key=lambda t: t["prize"], reverse=True)
        if not tiers:
            continue

        total_prizes = sum(t["total"] for t in tiers)
        remaining_prizes = sum(t["remaining"] for t in tiers)
        total_prize_value = sum(t["prize"] * t["total"] for t in tiers)
        price = g["price"]

        if total_prize_value > 0 and price > 0:
            total_tickets = int(total_prize_value / (0.65 * price))
            remaining_tickets = int(total_tickets * remaining_prizes / total_prizes) if total_prizes > 0 else 0
        else:
            total_tickets = 0
            remaining_tickets = 0

        tickets.append({
            "name": g["name"],
            "price": price,
            "totalTickets": total_tickets,
            "remainingTickets": remaining_tickets,
            "gameNumber": game_num,
            "tiers": tiers,
        })

    return tickets
