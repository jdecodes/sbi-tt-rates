# sbi-tt-rates

Lookup historical SBI TT (Telegraphic Transfer) buy/sell forex rates, with
automatic fallback to the nearest prior trading day when a date has no
published rate (weekends, holidays, no-publish days).

> **⚠️ Disclaimer:** This is an **unofficial, community-maintained** package.
> It is **not affiliated with, endorsed by, or sourced directly from the
> State Bank of India**. Data is pulled from a third-party open-source
> archive (see below), which itself scrapes publicly published SBI rate
> sheets, it is **not a live or guaranteed-accurate feed**. Rates may be
> missing, delayed, or wrong due to upstream parsing errors or gaps.
> **Use at your own risk.** Always cross-check against an official SBI
> source before relying on this for tax filings, compliance, or any
> financial decision.

Data source: [sahilgupta/sbi-fx-ratekeeper](https://github.com/sahilgupta/sbi-fx-ratekeeper)
(not affiliated with SBI or the upstream repo author this package is a
thin, cached wrapper around that repo's published CSVs).

## Install

```bash
pip install sbi-tt-rates
```

```markdown
[![PyPI version](https://img.shields.io/pypi/v/sbi-tt-rates.svg)](https://pypi.org/project/sbi-tt-rates/)

## Usage

```python
from sbi_tt_rates import get_rate

result = get_rate("2021-02-20", currency="USD", rate_type="tt_buy")
print(result)
# RateResult(requested_date='2021-02-20', actual_date='2021-02-18',
#            exact_match=False, rate=72.3, rate_type='tt_buy')

inr_value = 10_000 * result.rate
```

- `rate_type`: `"tt_buy"` or `"tt_sell"`
- `exact_match` tells you whether the requested date had a published rate,
  or whether it fell back to the nearest prior trading day — useful to log
  if you're using this for tax/compliance purposes.
- Data is cached locally (`~/.cache/sbi_tt_rates/`), so
  repeated lookups don't re-download the CSV each call.

## Currencies

AED AUD BDT BHD CAD CHF CNY DKK EUR GBP HKD IDR JPY KES KRW KWD LKR MYR NOK NZD OMR PKR QAR RUB SAR SEK SGD THB TRY USD ZAR
SBI_REFERENCE_RATES_<Currency> on 
https://github.com/sahilgupta/sbi-fx-ratekeeper

## License

MIT
