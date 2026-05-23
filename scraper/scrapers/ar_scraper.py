"""Arkansas Lottery — per-game HTML scraping. Full tier data."""
import re
import time
import requests
import cloudscraper
from bs4 import BeautifulSoup

BASE = "https://www.myarkansaslottery.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120"}


def _parse_money(s: str) -> int:
    return int(float(re.sub(r"[^\d.]", "", s))) if re.search(r"\d", s) else 0


def _get_game_slugs() -> list[str]:
    scraper = cloudscraper.create_scraper()
    slugs: set[str] = set()
    skip = {"/games/instant", "/games/fastplay", "/games/cash-3", "/games/cash-4",
            "/games/powerball", "/games/mega-millions", "/games/lotto",
            "/games/natural-state-jackpot", "/games/lucky-for-life-0"}
    for page in range(10):
        url = f"{BASE}/games/instant?page={page}" if page else f"{BASE}/games/instant"
        try:
            r = scraper.get(url, timeout=20)
            soup = BeautifulSoup(r.text, "html.parser")
            links = [l["href"] for l in soup.find_all("a", href=re.compile(r"^/games/[a-z0-9-]+$"))]
            links = [l for l in links if l not in skip]
            new = set(links) - slugs
            if not new and page > 0:
                break
            slugs.update(new)
        except Exception as e:
            print(f"[AR] Page {page} failed: {e}")
            break
    return list(slugs)


def scrape() -> list[dict]:
    slugs = _get_game_slugs()
    tickets = []

    for slug in slugs:
        try:
            r = requests.get(f"{BASE}{slug}", headers=HEADERS, timeout=20)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")

            name_el = soup.find("h1")
            if not name_el:
                continue
            name = name_el.get_text(strip=True)

            # Price from "Ticket price:" label, value in next sibling
            price_label = soup.find(string=re.compile(r"Ticket price", re.I))
            if not price_label:
                continue
            price_parent = price_label.find_parent()
            price_sib = price_parent.find_next_sibling() if price_parent else None
            price_text = price_sib.get_text(strip=True) if price_sib else ""
            if not price_text:
                # fallback: check combined text
                m = re.search(r"Ticket price[:\s]+\$(\d+)", soup.get_text())
                price = float(m.group(1)) if m else 0.0
            else:
                m = re.search(r"\d+", price_text)
                price = float(m.group(0)) if m else 0.0
            if price <= 0:
                continue

            # Prize table: Tier Prize | Total | Remaining | ...
            table = soup.find("table")
            if not table:
                continue

            tiers = []
            for row in table.find_all("tr")[1:]:
                cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
                if len(cells) < 3:
                    continue
                prize = _parse_money(cells[0])
                total = _parse_money(cells[1]) if len(cells) > 1 else 0
                remaining = _parse_money(cells[2]) if len(cells) > 2 else 0
                if prize > 0:
                    tiers.append({"prize": prize, "remaining": remaining, "total": total})

            tiers.sort(key=lambda t: t["prize"], reverse=True)
            if not tiers:
                continue

            # Image: sites/default/files/instant/front/ar-{num}-front.jpg
            image_url = None
            img_el = soup.find("img", src=re.compile(r"/sites/default/files/instant/front/", re.I))
            if img_el:
                src = img_el.get("src", "")
                image_url = (BASE + src) if src.startswith("/") else src

            total_prizes = sum(t["total"] for t in tiers)
            remaining_prizes = sum(t["remaining"] for t in tiers)

            # Estimate ticket counts using 65% payout rate
            total_prize_value = sum(t["prize"] * t["total"] for t in tiers)
            if total_prize_value > 0 and price > 0:
                total_tickets = int(total_prize_value / (0.65 * price))
                remaining_tickets = int(total_tickets * (remaining_prizes / total_prizes)) if total_prizes > 0 else 0
            else:
                total_tickets = 0
                remaining_tickets = 0

            game_number = slug.lstrip("/games/")

            entry = {
                "name": name,
                "price": price,
                "totalTickets": total_tickets,
                "remainingTickets": remaining_tickets,
                "gameNumber": game_number,
                "tiers": tiers,
            }
            if image_url:
                entry["imageUrl"] = image_url
            tickets.append(entry)
            time.sleep(0.3)

        except Exception as e:
            print(f"[AR] {slug} failed: {e}")

    return tickets
