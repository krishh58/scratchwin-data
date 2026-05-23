"""Pennsylvania Lottery — HTML table (all games + top-6 tiers on one page)."""
import re
import requests
from bs4 import BeautifulSoup

URL = "https://www.palottery.pa.gov/Scratch-Offs/Prizes-Remaining.aspx"
IMG_BASE = "https://www.palottery.state.pa.us/PaLotteryWebSite/media/Scratch-Offs-Section/Onserts/Scratch-Offs"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.palottery.pa.gov/",
}


def _make_img_slug(name: str) -> str:
    s = re.sub(r'[®™©]', '', name)
    s = s.replace('&', 'and')
    s = re.sub(r'[\s_/]+', '-', s.strip())
    s = re.sub(r'[^\w$-]', '', s)
    return s


def _parse_money(text: str) -> int:
    return int(re.sub(r"[^\d]", "", text) or "0")


def scrape() -> list[dict]:
    resp = requests.get(URL, headers=HEADERS, timeout=30)
    soup = BeautifulSoup(resp.text, "html.parser")

    table = soup.find("table")
    if not table:
        return []

    tickets = []
    for row in table.find_all("tr")[1:]:
        cells = [c.get_text(separator=" ", strip=True) for c in row.find_all(["td", "th"])]
        if len(cells) < 5:
            continue

        # Columns: Game # | Game Name | Price | Top 6 Prizes | Wins Remaining
        raw_num = re.sub(r"[^\d]", "", cells[0])
        game_num = raw_num
        name = re.sub(r"\s*Available on iLottery\s*", "", cells[1]).strip()
        price_str = cells[2]
        prizes_str = cells[3]  # e.g. "$2,500 $500 $100 $50 $20 $10"
        remaining_str = cells[4]  # e.g. "18 116 710 1,256 37,007 87,138"

        price = float(_parse_money(price_str))
        if price <= 0 or not game_num or not name:
            continue

        prize_amounts = [_parse_money(p) for p in re.findall(r"\$[\d,]+", prizes_str)]
        remaining_counts = [_parse_money(r) for r in re.split(r"\s+", remaining_str.strip()) if r]

        tiers = []
        for prize, remaining in zip(prize_amounts, remaining_counts):
            if prize > 0:
                tiers.append({
                    "prize": prize,
                    "remaining": remaining,
                    "total": remaining,  # PA doesn't expose total; use remaining as floor
                })

        tiers.sort(key=lambda t: t["prize"], reverse=True)
        if tiers:
            slug = _make_img_slug(name)
            image_url = f"{IMG_BASE}/PA-{game_num}_{slug}_289x289-Onsert.jpg?ext=.jpg"
            tickets.append({
                "name": name,
                "price": price,
                "totalTickets": 0,
                "remainingTickets": 0,
                "gameNumber": game_num,
                "tiers": tiers,
                "imageUrl": image_url,
            })

    return tickets
