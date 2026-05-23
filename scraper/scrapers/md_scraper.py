"""Maryland Lottery — WordPress AJAX POST, returns all games + full tier data in one call."""
import re
import requests
from bs4 import BeautifulSoup

URL = "https://www.mdlottery.com/wp-admin/admin-ajax.php"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.mdlottery.com/games/scratch-offs/",
    "Content-Type": "application/x-www-form-urlencoded",
    "X-Requested-With": "XMLHttpRequest",
}


def _parse_money(text: str) -> int:
    return int(re.sub(r"[^\d]", "", text) or "0")


def scrape() -> list[dict]:
    resp = requests.post(
        URL,
        data={"action": "jquery_shortcode", "shortcode": "scratch_offs", "atts": "{}"},
        headers=HEADERS,
        timeout=30,
    )
    soup = BeautifulSoup(resp.text, "html.parser")

    tickets = []
    for li in soup.find_all("li", class_="ticket"):
        name_tag = li.find(class_="name")
        price_tag = li.find(class_="price")
        game_num_tag = li.find(class_="gamenumber")

        name = name_tag.get_text(strip=True) if name_tag else ""
        price = float(_parse_money(price_tag.get_text(strip=True)) or 0) if price_tag else 0.0
        game_num = re.sub(r"[^\d]", "", game_num_tag.get_text(strip=True)) if game_num_tag else ""

        if not name or price <= 0:
            continue

        # Prize table is in hidden div: #prize_details_{id}
        game_id = li.get("id", "").replace("ticket_", "")
        prize_div = li.find("div", id=f"prize_details_{game_id}")

        tiers = []
        if prize_div:
            table = prize_div.find("table")
            if table:
                hdrs = [th.get_text(strip=True).lower() for th in table.find_all("th")]
                # Columns: Prize Amount | Start | Remaining
                prize_idx = next((i for i, h in enumerate(hdrs) if "prize" in h or "amount" in h), 0)
                total_idx = next((i for i, h in enumerate(hdrs) if "start" in h or "total" in h), 1)
                rem_idx = next((i for i, h in enumerate(hdrs) if "remaining" in h), 2)

                for row in table.find_all("tr")[1:]:
                    cols = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
                    if len(cols) < 2:
                        continue
                    prize = _parse_money(cols[prize_idx])
                    total = _parse_money(cols[total_idx]) if total_idx < len(cols) else 0
                    remaining = _parse_money(cols[rem_idx]) if rem_idx < len(cols) else 0
                    if prize > 0 and total > 0:
                        tiers.append({"prize": prize, "remaining": remaining, "total": total})

        tiers.sort(key=lambda t: t["prize"], reverse=True)
        if tiers:
            img_tag = li.find("img", src=re.compile(r"wp-content"))
            image_url = img_tag["src"] if img_tag else None
            # Prefer _FRONT_ image if multiple exist (avoid _BACK_ or _SCRATCHED_)
            for img in li.find_all("img", src=re.compile(r"wp-content")):
                src = img.get("src", "")
                if "_FRONT_" in src or "_front_" in src:
                    image_url = src
                    break
            entry = {
                "name": name,
                "price": price,
                "totalTickets": 0,
                "remainingTickets": 0,
                "gameNumber": game_num or game_id,
                "tiers": tiers,
            }
            if image_url:
                entry["imageUrl"] = image_url
            tickets.append(entry)

    return tickets
