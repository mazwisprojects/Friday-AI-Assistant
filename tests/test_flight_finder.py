from actions import flight_finder


def test_flight_finder_requires_origin_and_destination():
    result = flight_finder.flight_finder({"origin": "", "destination": "NYC", "date": "2026-09-01"})

    assert "provide both origin and destination" in result.lower()


def test_flight_finder_requires_date():
    result = flight_finder.flight_finder({"origin": "LAX", "destination": "NYC", "date": ""})

    assert "provide a departure date" in result.lower()


def test_flight_finder_reports_search_failure(monkeypatch):
    def fake_search(*args, **kwargs):
        raise RuntimeError("network unreachable")

    monkeypatch.setattr(flight_finder, "_search_flights_browser", fake_search)

    result = flight_finder.flight_finder({
        "origin": "LAX",
        "destination": "NYC",
        "date": "2026-09-01",
    })

    assert "flight search failed" in result.lower()


def test_flight_finder_reports_when_no_data_retrieved(monkeypatch):
    monkeypatch.setattr(flight_finder, "_search_flights_browser", lambda *a, **k: (None, None))

    result = flight_finder.flight_finder({
        "origin": "LAX",
        "destination": "NYC",
        "date": "2026-09-01",
    })

    assert "could not retrieve flight data" in result.lower()
