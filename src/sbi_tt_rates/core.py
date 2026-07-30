"""
SBI TT rate lookup with nearest-prior-date fallback.

Data source: https://github.com/sahilgupta/sbi-fx-ratekeeper

DISCLAIMER: This is an unofficial, community-maintained package. It is NOT
affiliated with, endorsed by, or sourced directly from the State Bank of
India. Data is pulled from a third-party open-source archive which scrapes
publicly published SBI rate sheets — it is not a live or guaranteed-accurate
feed. Rates may be missing, delayed, or wrong. Use at your own risk. Always
cross-check against an official SBI source before relying on this for tax
filings, compliance, or any financial decision.
"""

from __future__ import annotations

import csv
import json
import re
import urllib.error
import urllib.request
from bisect import bisect_right
from dataclasses import dataclass
from datetime import date
from pathlib import Path

CSV_URL_TEMPLATE = (
    "https://raw.githubusercontent.com/sahilgupta/sbi-fx-ratekeeper/"
    "main/csv_files/SBI_REFERENCE_RATES_{ccy}.csv"
)

# Currencies confirmed available upstream (sahilgupta/sbi-fx-ratekeeper).
# This is a static list maintained alongside upstream, not fetched
# dynamically - keep it in sync if the upstream repo adds/drops currencies.
SUPPORTED_CURRENCIES = frozenset(
    {
        "AED",
        "AUD",
        "BDT",
        "BHD",
        "CAD",
        "CHF",
        "CNY",
        "DKK",
        "EUR",
        "GBP",
        "HKD",
        "IDR",
        "JPY",
        "KES",
        "KRW",
        "KWD",
        "LKR",
        "MYR",
        "NOK",
        "NZD",
        "OMR",
        "PKR",
        "QAR",
        "RUB",
        "SAR",
        "SEK",
        "SGD",
        "THB",
        "TRY",
        "USD",
        "ZAR",
    }
)

CACHE_DIR = Path.home() / ".cache" / "sbi_tt_rates"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _parse_date_input(value: str | date) -> date:
    """
    Enforce that dates are either a real datetime.date object, or a string
    strictly in 'YYYY-MM-DD' format (zero-padded, e.g. '2020-01-07' not
    '2020-1-7'). Raises a clear ValueError/TypeError instead of letting a
    raw strptime failure leak out.
    """
    if isinstance(value, date):
        return value

    if not isinstance(value, str):
        raise TypeError(
            f"target_date must be a string in 'YYYY-MM-DD' format or a "
            f"datetime.date object, got {type(value).__name__}"
        )

    if not _DATE_RE.match(value):
        raise ValueError(
            f"Invalid date format: {value!r}. Expected 'YYYY-MM-DD' (e.g. '2020-01-07')."
        )

    try:
        return date.fromisoformat(value)
    except ValueError as e:
        raise ValueError(f"Invalid date: {value!r} is not a real calendar date.") from e


@dataclass(frozen=True)
class RateResult:
    requested_date: str
    actual_date: str
    exact_match: bool
    rate: float
    rate_type: str


def supported_currencies() -> list[str]:
    """Return the sorted list of currency codes this package can look up."""
    return sorted(SUPPORTED_CURRENCIES)


def _validate_currency(currency: str) -> str:
    ccy = currency.upper()
    if ccy not in SUPPORTED_CURRENCIES:
        raise ValueError(
            f"Unsupported currency: {currency!r}. "
            f"Call supported_currencies() for the full list, or see "
            f"https://github.com/sahilgupta/sbi-fx-ratekeeper for what "
            f"the upstream data source publishes."
        )
    return ccy


def _cache_path(currency: str) -> Path:
    return CACHE_DIR / f"{currency.upper()}.json"


def _download_csv(currency: str) -> str:
    url = CSV_URL_TEMPLATE.format(ccy=currency.upper())
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return resp.read().decode()
    except urllib.error.HTTPError as e:
        raise ValueError(
            f"No data file found for currency '{currency}' (HTTP {e.code} from upstream repo)"
        ) from e
    except urllib.error.URLError as e:
        raise ConnectionError(f"Could not reach upstream data source ({url}): {e.reason}") from e


def _parse_csv(raw_text: str) -> list[dict]:
    rows = list(csv.DictReader(raw_text.splitlines()))
    parsed = []
    for r in rows:
        try:
            tt_buy = float(r["TT BUY"])
            tt_sell = float(r["TT SELL"])
        except (ValueError, KeyError):
            continue
        if tt_buy == 0.0 or tt_sell == 0.0:
            continue  # known dirty rows in early upstream data
        d = date.fromisoformat(r["DATE"].split()[0])
        parsed.append({"date": d.isoformat(), "tt_buy": tt_buy, "tt_sell": tt_sell})
    parsed.sort(key=lambda r: r["date"])
    return parsed


def fetch_rates(
    currency: str = "USD",
    force_refresh: bool = False,
    needed_date: str | None = None,
) -> list[dict]:
    """
    Return the sorted list of {date, tt_buy, tt_sell} for a currency.

    Uses a local disk cache (~/.cache/sbi_tt_rates/). Historical rates never
    change once published, so the cache is only refreshed when it can't
    possibly satisfy the request:
      - no cache file exists yet, or it's empty
      - `needed_date` is newer than the most recent date already cached
        (i.e. you're asking for a date the cache hasn't seen yet)
      - `force_refresh=True` is passed explicitly

    If `needed_date` is None or is <= the cache's latest date, the cache is
    trusted as-is and no network call is made, regardless of cache age.
    """
    currency = _validate_currency(currency)
    cache_file = _cache_path(currency)
    cached: list[dict] | None = None

    if cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text())
        except json.JSONDecodeError:
            cached = None  # corrupt cache file -> treat as no cache

    cache_covers_request = cached and (needed_date is None or needed_date <= cached[-1]["date"])

    if not force_refresh and cache_covers_request:
        return cached

    raw = _download_csv(currency)
    parsed = _parse_csv(raw)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(parsed))
    return parsed


def get_rate(
    target_date: str | date,
    currency: str = "USD",
    rate_type: str = "tt_buy",
) -> RateResult:
    """
    target_date: 'YYYY-MM-DD' string (strict, zero-padded) or a datetime.date
    rate_type: 'tt_buy' or 'tt_sell'

    Returns the rate for that exact date, or the nearest PRIOR trading day
    if no data exists for that date (weekends / holidays / no-publish days).
    """
    if rate_type not in ("tt_buy", "tt_sell"):
        raise ValueError("rate_type must be 'tt_buy' or 'tt_sell'")

    target = _parse_date_input(target_date)
    target_str = target.isoformat()

    rates = fetch_rates(currency, needed_date=target_str)
    dates = [date.fromisoformat(r["date"]) for r in rates]

    idx = bisect_right(dates, target) - 1
    if idx < 0:
        earliest = rates[0]["date"] if rates else None
        ccy_display = currency.upper()
        raise ValueError(
            f"No data available for {ccy_display} on or before {target_str}. "
            f"Earliest available date is {earliest}."
            if earliest
            else f"No data available for {ccy_display} at all."
        )

    match = rates[idx]
    return RateResult(
        requested_date=target_str,
        actual_date=match["date"],
        exact_match=(match["date"] == target_str),
        rate=match[rate_type],
        rate_type=rate_type,
    )
