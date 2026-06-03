from pathlib import Path

import scripts.fetch_official_data as fetcher


def test_write_official_csvs_creates_analysis_inputs(tmp_path: Path):
    written = fetcher.write_official_csvs(tmp_path)

    assert {path.name for path in written} == {"attendance.csv", "facilities.csv", "population.csv"}
    assert "서울특별시" in (tmp_path / "attendance.csv").read_text(encoding="utf-8-sig")
    assert "facilities" in (tmp_path / "facilities.csv").read_text(encoding="utf-8-sig")
    assert "target_age_population" in (tmp_path / "population.csv").read_text(encoding="utf-8-sig")


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
