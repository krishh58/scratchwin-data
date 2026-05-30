"""
ScratchWin daily scraper runner.
Runs all state scrapers and writes output/{STATE_CODE}.json
Deploy this on a VPS or GitHub Actions cron — run once daily.

Usage:
    python run_scrapers.py              # all states
    python run_scrapers.py OH NY TX     # specific states
"""

import json
import sys
import time
from pathlib import Path
from datetime import datetime

# State scraper registry
# key = 2-letter state code, value = (module_name, scrape_fn)
SCRAPERS = {
    "OH": "scrapers.oh_scraper",
    "CA": "scrapers.ca_scraper",
    "NY": "scrapers.ny_scraper",
    "FL": "scrapers.fl_scraper",
    "LA": "scrapers.la_scraper",
    "TX": "scrapers.tx_scraper",
    "NJ": "scrapers.nj_scraper",
    "MI": "scrapers.mi_scraper",
    "GA": "scrapers.ga_scraper",
    "PA": "scrapers.pa_scraper",
    "NC": "scrapers.nc_scraper",
    "MA": "scrapers.ma_scraper",
    "WA": "scrapers.wa_scraper",
    "VA": "scrapers.va_scraper",
    "CO": "scrapers.co_scraper",
    "MO": "scrapers.mo_scraper",
    "IL": "scrapers.il_scraper",
    "IN": "scrapers.in_scraper",
    "KY": "scrapers.ky_scraper",
    "OK": "scrapers.ok_scraper",
    "MD": "scrapers.md_scraper",
    "CT": "scrapers.ct_scraper",
    "ID": "scrapers.id_scraper",
    "NH": "scrapers.nh_scraper",
    "NE": "scrapers.ne_scraper",
    "MS": "scrapers.ms_scraper",
    "AZ": "scrapers.az_scraper",
    "AR": "scrapers.ar_scraper",
    "ME": "scrapers.me_scraper",
    "VT": "scrapers.vt_scraper",
    "WI": "scrapers.wi_scraper",
    "IA": "scrapers.ia_scraper",
    "NM": "scrapers.nm_scraper",
    "DE": "scrapers.de_scraper",
    "SC": "scrapers.sc_scraper",
    # Playwright-required states (headless browser)
    "TN": "scrapers.tn_scraper",
    "OR": "scrapers.or_scraper",
    # requests-based
    "MN": "scrapers.mn_scraper",
    "MT": "scrapers.mt_scraper",
    "WV": "scrapers.wv_scraper",
}

OUTPUT_DIR = Path(__file__).parent / "output"


def run_state(code: str, module_name: str) -> bool:
    import importlib
    print(f"[{code}] Scraping...")
    try:
        mod = importlib.import_module(module_name)
        tickets = mod.scrape()

        if not tickets:
            print(f"[{code}] WARNING: No tickets returned")
            return False

        out_path = OUTPUT_DIR / f"{code.lower()}.json"
        with open(out_path, "w") as f:
            json.dump(tickets, f, indent=2)

        print(f"[{code}] OK — {len(tickets)} games → {out_path}")
        return True

    except Exception as e:
        print(f"[{code}] FAILED: {e}")
        return False


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    states = sys.argv[1:] if len(sys.argv) > 1 else list(SCRAPERS.keys())
    states = [s.upper() for s in states]

    results = {}
    for code in states:
        if code not in SCRAPERS:
            print(f"[{code}] No scraper registered — skipping")
            continue
        results[code] = run_state(code, SCRAPERS[code])
        time.sleep(2)  # be polite between requests

    # Write manifest
    manifest = {
        "updated": datetime.utcnow().isoformat() + "Z",
        "states": {k: ("ok" if v else "failed") for k, v in results.items()},
    }
    with open(OUTPUT_DIR / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    ok = sum(results.values())
    print(f"\nDone: {ok}/{len(results)} states successful")


if __name__ == "__main__":
    main()
