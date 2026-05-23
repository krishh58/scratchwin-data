"""Delaware Lottery — top-prizes-remaining table (top prize tier only)."""
import re
import requests
from bs4 import BeautifulSoup

URL = "https://www.delottery.com/Instant-Games/Top-Prizes-Remaining"
LIST_URL = "https://www.delottery.com/Instant-Games"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120"}


def _parse_money(s: str) -> int:
    m = re.search(r"[\d,]+", s)
    return int(m.group(0).replace(",", "")) if m else 0


def _build_image_map(soup: BeautifulSoup) -> dict[str, str]:
    img_map: dict[str, str] = {}
    base = "https://www.delottery.com"
    for img in soup.find_all("img", srcset=re.compile(r"/Content/images/instant-lottery/")):
        srcset = img.get("srcset", "")
        m_path = re.search(r"(/Content/images/instant-lottery/[^\s?]+)", srcset)
        if not m_path:
            continue
        path = m_path.group(1)
        fname = path.split("/")[-1]
        # Extract first digit sequence from filename as game number
        m_num = re.search(r"\d+", fname)
        if m_num:
            gnum = m_num.group(0)
            if gnum not in img_map:
                img_map[gnum] = base + path
    return img_map


def scrape() -> list[dict]:
    list_r = requests.get(LIST_URL, headers=HEADERS, timeout=20)
    list_soup = BeautifulSoup(list_r.text, "html.parser")
    img_map = _build_image_map(list_soup)

    r = requests.get(URL, headers=HEADERS, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    table = soup.find("table")
    if not table:
        return []

    # Header: Game Number | Game Name | Dollar Amount | Top Prize | Total Top Prizes | Prizes Remaining
    rows = table.find_all("tr")[1:]
    tickets = []
    seen: set[str] = set()

    for row in rows:
        cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
        if len(cells) < 6:
            continue

        game_num = cells[0].rstrip("*")  # asterisk = game ending soon
        name = cells[1]
        price_str = cells[2]
        prize_str = cells[3]
        total_str = cells[4]
        remaining_str = cells[5]

        if game_num in seen:
            continue
        seen.add(game_num)

        price_m = re.search(r"\$([\d.]+)", price_str)
        price = float(price_m.group(1)) if price_m else _parse_money(price_str)
        if price <= 0:
            continue

        prize = _parse_money(prize_str)
        total = _parse_money(total_str)
        remaining = _parse_money(remaining_str)
        if prize <= 0:
            continue

        tiers = [{"prize": prize, "remaining": remaining, "total": total}]

        # Estimate ticket counts
        if prize > 0 and total > 0 and price > 0:
            total_tickets = int((prize * total) / (0.65 * price))
            remaining_tickets = int(total_tickets * remaining / total) if total > 0 else 0
        else:
            total_tickets = 0
            remaining_tickets = 0

        entry = {
            "name": name,
            "price": float(price),
            "totalTickets": total_tickets,
            "remainingTickets": remaining_tickets,
            "gameNumber": game_num,
            "tiers": tiers,
        }
        if game_num in img_map:
            entry["imageUrl"] = img_map[game_num]
        tickets.append(entry)

    return tickets
