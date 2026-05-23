"""New Mexico Lottery — all games on single scratchers page, full tier data."""
import re
import requests
from bs4 import BeautifulSoup

URL = "https://www.nmlottery.com/games/scratchers/"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120"}


def _parse_money(s: str) -> int:
    m = re.search(r"[\d,]+", s)
    return int(m.group(0).replace(",", "")) if m else 0


def _build_image_map(html: str) -> dict[str, str]:
    """Extract game_number → WP image URL from page HTML."""
    img_map: dict[str, str] = {}
    for url in re.findall(r'https://www\.nmlottery\.com/wp-content/uploads/[^\s"\'<>]+\.jpg', html):
        m = re.search(r'/(\d{3,4})(?:-\d+)?\.jpg$', url)
        if m:
            gnum = m.group(1)
            if gnum not in img_map:
                img_map[gnum] = url
    return img_map


def scrape() -> list[dict]:
    r = requests.get(URL, headers=HEADERS, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    img_map = _build_image_map(r.text)

    tickets = []
    for container in soup.find_all("div", class_="scratcher-content"):
        try:
            name_el = container.find(["h2", "h3"])
            name = name_el.get_text(strip=True) if name_el else None
            if not name:
                continue

            price_el = container.find("p", class_="price")
            if not price_el:
                continue
            price_m = re.search(r"\$([\d.]+)", price_el.get_text(strip=True))
            price = float(price_m.group(1)) if price_m else 0.0
            if price <= 0:
                continue

            game_num_el = container.find("p", class_="game-number")
            game_num = ""
            if game_num_el:
                m = re.search(r"(\d+)", game_num_el.get_text(strip=True))
                game_num = m.group(1) if m else ""

            table = container.find("table")
            if not table:
                continue

            tiers = []
            for row in table.find_all("tr")[1:]:
                cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
                if len(cells) < 4:
                    continue
                prize = _parse_money(cells[0])
                total = _parse_money(cells[2])
                remaining = _parse_money(cells[3])
                if prize > 0:
                    tiers.append({"prize": prize, "remaining": remaining, "total": total})

            tiers.sort(key=lambda t: t["prize"], reverse=True)
            if not tiers:
                continue

            total_prizes = sum(t["total"] for t in tiers)
            remaining_prizes = sum(t["remaining"] for t in tiers)
            total_prize_value = sum(t["prize"] * t["total"] for t in tiers)

            if total_prize_value > 0 and price > 0:
                total_tickets = int(total_prize_value / (0.65 * price))
                remaining_tickets = int(total_tickets * remaining_prizes / total_prizes) if total_prizes > 0 else 0
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
            if game_num and game_num in img_map:
                entry["imageUrl"] = img_map[game_num]
            tickets.append(entry)

        except Exception as e:
            print(f"[NM] Game parse error: {e}")

    return tickets
