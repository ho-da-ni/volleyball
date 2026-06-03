from pathlib import Path

import scripts.fetch_official_data as fetcher


def test_write_official_csvs_creates_analysis_inputs(tmp_path: Path):
    written = fetcher.write_official_csvs(tmp_path)

    assert {path.name for path in written} == {"attendance.csv", "facilities.csv", "population.csv"}
    attendance_text = (tmp_path / "attendance.csv").read_text(encoding="utf-8-sig")
    facilities_text = (tmp_path / "facilities.csv").read_text(encoding="utf-8-sig")

    assert "sport,season,team,stadium" in attendance_text
    assert "spectator_basis" in attendance_text
    assert "최근 3년 평균 시즌 총관중" in attendance_text
    assert "우리카드" in attendance_text
    assert "배구 가능 실내체육시설" in facilities_text
    assert "indoor_facilities" not in facilities_text
    assert "adult_population" in (tmp_path / "population.csv").read_text(encoding="utf-8-sig")


def test_is_volleyball_possible_indoor_facility_filters_rows():
    assert fetcher.is_volleyball_possible_indoor_facility(
        {"indoor_outdoor": "실내", "facility_type": "다목적체육관", "available_sports": "배구, 농구"}
    )
    assert not fetcher.is_volleyball_possible_indoor_facility(
        {"indoor_outdoor": "실외", "facility_type": "축구장", "available_sports": "축구"}
    )


def test_download_official_sources_writes_mocked_response(tmp_path: Path, monkeypatch):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        @staticmethod
        def read():
            return b"official source"

    requested_urls = []

    def fake_urlopen(request, timeout):
        requested_urls.append(request.full_url)
        return FakeResponse()

    monkeypatch.setattr(fetcher, "urlopen", fake_urlopen)

    written = fetcher.download_official_sources(tmp_path, strict=True)

    assert len(written) == len(fetcher.OFFICIAL_SOURCES)
    assert requested_urls == [source.url for source in fetcher.OFFICIAL_SOURCES]
    assert all(path.read_bytes() == b"official source" for path in written)
