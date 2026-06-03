from pathlib import Path
import sys
import types

import pytest

import src.volleyball_demand_analysis as vda
from src.volleyball_demand_analysis import (
    IndicatorWeights,
    assign_region_clusters,
    build_region_scores,
    min_max_scale,
    read_csv_rows,
    run_analysis,
    standardize_region_name,
    write_folium_map,
)


def test_standardize_region_name_maps_aliases():
    assert standardize_region_name("서울") == "서울특별시"
    assert standardize_region_name("강원도") == "강원특별자치도"
    assert standardize_region_name("제주") == "제주특별자치도"


def test_min_max_scale_supports_reverse_scoring():
    values = [10, 20, 30]
    assert min_max_scale(values) == [0.0, 50.0, 100.0]
    assert min_max_scale(values, reverse=True) == [100.0, 50.0, 0.0]


def test_build_region_scores_returns_sorted_scores():
    attendance = [
        {"region": "서울", "matches": 10, "spectators": 50_000},
        {"region": "부산", "matches": 1, "spectators": 2_000},
    ]
    facilities = [
        {"region": "서울특별시", "facilities": 80},
        {"region": "부산광역시", "facilities": 40},
    ]
    population = [
        {"region": "서울특별시", "population": 9_400_000, "adult_population": 2_300_000},
        {"region": "부산광역시", "population": 3_300_000, "adult_population": 700_000},
    ]

    scores = build_region_scores(attendance, facilities, population)

    assert scores[0]["potential_demand_score"] >= scores[1]["potential_demand_score"]
    assert {row["region"] for row in scores} >= {"서울특별시", "부산광역시"}
    assert all(0 <= row["potential_demand_score"] <= 100 for row in scores)


def test_aggregate_scores_filter_non_volleyball_attendance():
    scores = build_region_scores(
        attendance_rows=[
            {"region": "서울", "sport": "배구", "matches": 2, "spectators": 1000},
            {"region": "서울", "sport": "농구", "matches": 99, "spectators": 99999},
        ],
        facility_rows=[{"region": "서울", "facilities": 10}],
        population_rows=[{"region": "서울", "population": 1000000, "adult_population": 800000}],
    )

    seoul = next(row for row in scores if row["region"] == "서울특별시")
    assert seoul["matches"] == 2
    assert seoul["spectators"] == 1000


def test_assign_region_clusters_adds_actionable_labels():
    rows = build_region_scores(
        attendance_rows=[
            {"region": "서울", "matches": 10, "spectators": 50_000},
            {"region": "부산", "matches": 1, "spectators": 2_000},
            {"region": "경기", "matches": 4, "spectators": 20_000},
            {"region": "제주", "matches": 0, "spectators": 0},
        ],
        facility_rows=[
            {"region": "서울", "facilities": 80},
            {"region": "부산", "facilities": 40},
            {"region": "경기", "facilities": 140},
            {"region": "제주", "facilities": 20},
        ],
        population_rows=[
            {"region": "서울", "population": 9_400_000, "adult_population": 2_300_000},
            {"region": "부산", "population": 3_300_000, "adult_population": 700_000},
            {"region": "경기", "population": 13_600_000, "adult_population": 3_400_000},
            {"region": "제주", "population": 675_000, "adult_population": 145_000},
        ],
    )

    clustered = assign_region_clusters(rows, cluster_count=4)

    assert all(row["region_type"] for row in clustered)
    assert all(row["recommendation"] for row in clustered)


def test_run_analysis_writes_csv_json_and_markdown(tmp_path: Path):
    output = tmp_path / "scores.csv"
    summary = tmp_path / "summary.json"
    report = tmp_path / "report.md"

    run_analysis(
        attendance_path=Path("data/official/attendance.csv"),
        facilities_path=Path("data/official/facilities.csv"),
        population_path=Path("data/official/population.csv"),
        output_path=output,
        summary_path=summary,
        report_path=report,
    )

    assert output.exists()
    assert summary.exists()
    assert report.exists()
    assert "potential_demand_score" in output.read_text(encoding="utf-8-sig")
    assert "상위 지역" in report.read_text(encoding="utf-8")


def test_write_folium_map_uses_folium_and_writes_html(tmp_path: Path, monkeypatch):
    class FakeHtml:
        def __init__(self):
            self.children = []

        def add_child(self, child):
            self.children.append(child)

    class FakeRoot:
        def __init__(self):
            self.html = FakeHtml()

    class FakeMap:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.root = FakeRoot()
            self.markers = []

        def get_root(self):
            return self.root

        def save(self, path):
            Path(path).write_text(
                "<html><body>프로배구 지역별 잠재수요 점수</body></html>",
                encoding="utf-8",
            )

    class FakeCircleMarker:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def add_to(self, demand_map):
            demand_map.markers.append(self)
            return self

    fake_folium = types.SimpleNamespace(
        Map=FakeMap,
        CircleMarker=FakeCircleMarker,
        Popup=lambda html, max_width: {"html": html, "max_width": max_width},
        Element=lambda html: html,
    )
    monkeypatch.setitem(sys.modules, "folium", fake_folium)

    output = tmp_path / "volleyball_demand_map.html"
    write_folium_map(
        [
            {
                "rank": 1,
                "region": "서울특별시",
                "potential_demand_score": 58.5,
                "region_type": "기존 흥행지역",
                "matches": 36,
                "spectators": 45887,
                "facilities": 148,
            }
        ],
        output,
    )

    assert output.exists()
    assert "프로배구 지역별 잠재수요 점수" in output.read_text(encoding="utf-8")


def test_read_csv_rows_accepts_korean_headers(tmp_path: Path):
    csv_path = tmp_path / "attendance.csv"
    csv_path.write_text("지역,경기수,관람객수\n서울,2,1000\n", encoding="utf-8")

    rows = read_csv_rows(
        csv_path,
        {
            "region": ("region", "지역"),
            "matches": ("matches", "경기수"),
            "spectators": ("spectators", "관람객수"),
        },
    )

    assert rows == [{"region": "서울", "matches": "2", "spectators": "1000"}]


def test_read_csv_rows_accepts_url_resources(monkeypatch):
    class FakeHeaders:
        @staticmethod
        def get_content_charset():
            return "utf-8"

    class FakeResponse:
        headers = FakeHeaders()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        @staticmethod
        def read():
            return "지역,경기수,관람객수\n서울,2,1000\n".encode("utf-8")

    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(vda, "urlopen", fake_urlopen)

    rows = read_csv_rows(
        "https://example.com/attendance.csv",
        {
            "region": ("region", "지역"),
            "matches": ("matches", "경기수"),
            "spectators": ("spectators", "관람객수"),
        },
    )

    assert captured == {"url": "https://example.com/attendance.csv", "timeout": 30}
    assert rows == [{"region": "서울", "matches": "2", "spectators": "1000"}]


def test_indicator_weights_must_sum_to_one():
    with pytest.raises(ValueError):
        IndicatorWeights(demand=1.0).validate()
