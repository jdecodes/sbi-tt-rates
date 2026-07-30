import pytest

from sbi_tt_rates import core

SAMPLE_CSV = """DATE,PDF FILE,TT BUY,TT SELL,BILL BUY,BILL SELL,FOREX TRAVEL CARD BUY,
FOREX TRAVEL CARD SELL,CN BUY,CN SELL
2021-02-10 10:00,https://example.com/a.pdf,72.48,73.33,72.42,73.48,71.80,73.70,71.50,73.80
2021-02-17 10:00,https://example.com/b.pdf,72.52,73.37,72.46,73.52,71.80,73.75,71.50,73.90
2021-02-18 10:00,https://example.com/c.pdf,72.30,73.15,72.24,73.30,71.60,73.50,71.30,73.60
2021-02-22 10:00,https://example.com/d.pdf,71.95,72.80,71.89,72.95,71.30,73.15,71.00,73.30
2020-01-04 09:00,https://example.com/e.pdf,0.00,0.00,71.29,72.34,70.70,72.55,70.40,72.70
"""


def test_parse_csv_skips_dirty_rows():
    parsed = core._parse_csv(SAMPLE_CSV)
    # the 0.00 row should be dropped
    assert len(parsed) == 4
    assert all(r["tt_buy"] > 0 for r in parsed)


def test_parse_csv_sorted_by_date():
    parsed = core._parse_csv(SAMPLE_CSV)
    dates = [r["date"] for r in parsed]
    assert dates == sorted(dates)


def test_get_rate_exact_match(monkeypatch, tmp_path):
    monkeypatch.setattr(core, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(core, "_download_csv", lambda ccy: SAMPLE_CSV)

    result = core.get_rate("2021-02-18", currency="USD", rate_type="tt_buy")
    assert result.exact_match is True
    assert result.actual_date == "2021-02-18"
    assert result.rate == 72.30


def test_get_rate_falls_back_to_nearest_prior(monkeypatch, tmp_path):
    monkeypatch.setattr(core, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(core, "_download_csv", lambda ccy: SAMPLE_CSV)

    # 2021-02-20 is a Saturday, no data -> should fall back to 2021-02-18
    result = core.get_rate("2021-02-20", currency="USD", rate_type="tt_buy")
    assert result.exact_match is False
    assert result.actual_date == "2021-02-18"
    assert result.rate == 72.30


def test_get_rate_sell_rate(monkeypatch, tmp_path):
    monkeypatch.setattr(core, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(core, "_download_csv", lambda ccy: SAMPLE_CSV)

    result = core.get_rate("2021-02-18", currency="USD", rate_type="tt_sell")
    assert result.rate == 73.15


def test_get_rate_invalid_rate_type(monkeypatch, tmp_path):
    monkeypatch.setattr(core, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(core, "_download_csv", lambda ccy: SAMPLE_CSV)

    with pytest.raises(ValueError):
        core.get_rate("2021-02-18", rate_type="mid")


def test_get_rate_no_data_before_target(monkeypatch, tmp_path):
    monkeypatch.setattr(core, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(core, "_download_csv", lambda ccy: SAMPLE_CSV)

    with pytest.raises(ValueError, match="Earliest available date is 2021-02-10"):
        core.get_rate("2019-01-01")


def test_cache_reused_for_date_already_covered(monkeypatch, tmp_path):
    """Asking for an older date than what's cached should NOT hit the network."""
    monkeypatch.setattr(core, "CACHE_DIR", tmp_path)

    call_count = {"n": 0}

    def fake_download(ccy):
        call_count["n"] += 1
        return SAMPLE_CSV

    monkeypatch.setattr(core, "_download_csv", fake_download)

    core.get_rate("2021-02-22", currency="USD")  # first call -> downloads, caches
    assert call_count["n"] == 1

    core.get_rate("2021-02-18", currency="USD")  # older date, already covered
    assert call_count["n"] == 1  # still 1 -> no re-download


def test_cache_refreshed_for_date_beyond_cache(monkeypatch, tmp_path):
    """Asking for a date newer than the cache's latest entry SHOULD re-download."""
    monkeypatch.setattr(core, "CACHE_DIR", tmp_path)

    call_count = {"n": 0}

    def fake_download(ccy):
        call_count["n"] += 1
        return SAMPLE_CSV  # latest cached date will be 2021-02-22

    monkeypatch.setattr(core, "_download_csv", fake_download)

    core.get_rate("2021-02-18", currency="USD")  # first call -> downloads, caches
    assert call_count["n"] == 1

    core.get_rate("2021-02-25", currency="USD")  # beyond cache's latest date (02-22)
    assert call_count["n"] == 2  # re-downloaded


def test_force_refresh_always_redownloads(monkeypatch, tmp_path):
    monkeypatch.setattr(core, "CACHE_DIR", tmp_path)

    call_count = {"n": 0}

    def fake_download(ccy):
        call_count["n"] += 1
        return SAMPLE_CSV

    monkeypatch.setattr(core, "_download_csv", fake_download)

    core.fetch_rates("USD")
    core.fetch_rates("USD", force_refresh=True)
    assert call_count["n"] == 2


def test_get_rate_rejects_non_zero_padded_date(monkeypatch, tmp_path):
    monkeypatch.setattr(core, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(core, "_download_csv", lambda ccy: SAMPLE_CSV)

    with pytest.raises(ValueError, match="Invalid date format"):
        core.get_rate("2021-2-18")  # not zero-padded


def test_get_rate_rejects_wrong_separator(monkeypatch, tmp_path):
    monkeypatch.setattr(core, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(core, "_download_csv", lambda ccy: SAMPLE_CSV)

    with pytest.raises(ValueError, match="Invalid date format"):
        core.get_rate("2021/02/18")


def test_get_rate_rejects_impossible_calendar_date(monkeypatch, tmp_path):
    monkeypatch.setattr(core, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(core, "_download_csv", lambda ccy: SAMPLE_CSV)

    with pytest.raises(ValueError, match="not a real calendar date"):
        core.get_rate("2021-02-30")  # Feb 30 doesn't exist


def test_get_rate_rejects_non_string_non_date(monkeypatch, tmp_path):
    monkeypatch.setattr(core, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(core, "_download_csv", lambda ccy: SAMPLE_CSV)

    with pytest.raises(TypeError):
        core.get_rate(20210218)  # int, not str or date


def test_get_rate_accepts_date_object(monkeypatch, tmp_path):
    from datetime import date as date_cls

    monkeypatch.setattr(core, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(core, "_download_csv", lambda ccy: SAMPLE_CSV)

    result = core.get_rate(date_cls(2021, 2, 18))
    assert result.rate == 72.30
    assert result.requested_date == "2021-02-18"


def test_supported_currencies_returns_sorted_list():
    result = core.supported_currencies()
    assert result == sorted(result)
    assert "USD" in result
    assert "EUR" in result
    assert len(result) == 31


def test_get_rate_rejects_unsupported_currency(monkeypatch, tmp_path):
    monkeypatch.setattr(core, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(core, "_download_csv", lambda ccy: SAMPLE_CSV)

    with pytest.raises(ValueError, match="Unsupported currency"):
        core.get_rate("2021-02-18", currency="XYZ")


def test_get_rate_currency_is_case_insensitive(monkeypatch, tmp_path):
    monkeypatch.setattr(core, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(core, "_download_csv", lambda ccy: SAMPLE_CSV)

    result = core.get_rate("2021-02-18", currency="usd")
    assert result.rate == 72.30


def test_unsupported_currency_never_hits_network(monkeypatch, tmp_path):
    """Validation should fail before any download is attempted."""
    monkeypatch.setattr(core, "CACHE_DIR", tmp_path)

    def fail_if_called(ccy):
        raise AssertionError("Should not attempt download for invalid currency")

    monkeypatch.setattr(core, "_download_csv", fail_if_called)

    with pytest.raises(ValueError, match="Unsupported currency"):
        core.get_rate("2021-02-18", currency="XYZ")


@pytest.mark.network
def test_live_fetch_real_upstream(tmp_path, monkeypatch):
    """Real network call against the actual upstream repo. Slower; confirms
    the schema hasn't changed upstream."""
    monkeypatch.setattr(core, "CACHE_DIR", tmp_path)
    rates = core.fetch_rates("USD", force_refresh=True)
    assert len(rates) > 1000
    assert "tt_buy" in rates[0]
