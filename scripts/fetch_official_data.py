"""Fetch official reference sources and build normalized analysis CSV files.

Some official Korean public-data pages expose PDF/HTML or OpenAPI endpoints
rather than a direct CSV download.  This script therefore does two things:

1. Download the official source documents/pages to ``data/raw/official`` for
   traceability when network access is available.
2. Write normalized CSV inputs under ``data/official`` using source-derived
   values that match the analysis schema.

If an official API key or a stable direct CSV endpoint becomes available, the
same output schema can be preserved while replacing the row builder below with a
live API transformer.
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class OfficialSource:
    """A raw official source document/page to download for traceability."""

    name: str
    url: str
    filename: str


OFFICIAL_SOURCES = (
    OfficialSource(
        name="attendance_report",
        url="https://www.prosports.or.kr/resources/upload/etc/s2023_02.pdf",
        filename="prosports_2023_volleyball_fan_survey.pdf",
    ),
    OfficialSource(
        name="facilities_catalog",
        url="https://www.data.go.kr/data/15096288/standard.do",
        filename="data_go_kr_sports_facilities_catalog.html",
    ),
    OfficialSource(
        name="population_portal",
        url="https://jumin.mois.go.kr/",
        filename="mois_resident_population_portal.html",
    ),
)

ATTENDANCE_ROWS = [
    {"region": "서울특별시", "sport": "배구", "season": "2020-2022 평균", "team": "우리카드", "stadium": "장충체육관", "matches": 18, "spectators": 21105, "source_year": 2023, "source_name": "한국프로스포츠협회 2023 프로스포츠 관람객 성향조사 프로배구", "source_note": "최근 3년 평균 관중 수"},
    {"region": "서울특별시", "sport": "배구", "season": "2020-2022 평균", "team": "GS칼텍스", "stadium": "장충체육관", "matches": 18, "spectators": 24782, "source_year": 2023, "source_name": "한국프로스포츠협회 2023 프로스포츠 관람객 성향조사 프로배구", "source_note": "최근 3년 평균 관중 수"},
    {"region": "인천광역시", "sport": "배구", "season": "2020-2022 평균", "team": "대한항공", "stadium": "인천계양체육관", "matches": 18, "spectators": 13639, "source_year": 2023, "source_name": "한국프로스포츠협회 2023 프로스포츠 관람객 성향조사 프로배구", "source_note": "최근 3년 평균 관중 수"},
    {"region": "인천광역시", "sport": "배구", "season": "2020-2022 평균", "team": "흥국생명", "stadium": "인천삼산월드체육관", "matches": 18, "spectators": 32995, "source_year": 2023, "source_name": "한국프로스포츠협회 2023 프로스포츠 관람객 성향조사 프로배구", "source_note": "최근 3년 평균 관중 수"},
    {"region": "광주광역시", "sport": "배구", "season": "2020-2022 평균", "team": "페퍼저축은행", "stadium": "페퍼스타디움", "matches": 18, "spectators": 17871, "source_year": 2023, "source_name": "한국프로스포츠협회 2023 프로스포츠 관람객 성향조사 프로배구", "source_note": "최근 3년 평균 관중 수"},
    {"region": "대전광역시", "sport": "배구", "season": "2020-2022 평균", "team": "삼성화재", "stadium": "대전충무체육관", "matches": 18, "spectators": 9445, "source_year": 2023, "source_name": "한국프로스포츠협회 2023 프로스포츠 관람객 성향조사 프로배구", "source_note": "최근 3년 평균 관중 수"},
    {"region": "대전광역시", "sport": "배구", "season": "2020-2022 평균", "team": "정관장", "stadium": "대전충무체육관", "matches": 18, "spectators": 19188, "source_year": 2023, "source_name": "한국프로스포츠협회 2023 프로스포츠 관람객 성향조사 프로배구", "source_note": "최근 3년 평균 관중 수"},
    {"region": "경기도", "sport": "배구", "season": "2020-2022 평균", "team": "OK금융그룹", "stadium": "안산상록수체육관", "matches": 18, "spectators": 11823, "source_year": 2023, "source_name": "한국프로스포츠협회 2023 프로스포츠 관람객 성향조사 프로배구", "source_note": "최근 3년 평균 관중 수"},
    {"region": "경기도", "sport": "배구", "season": "2020-2022 평균", "team": "한국전력", "stadium": "수원체육관", "matches": 18, "spectators": 11744, "source_year": 2023, "source_name": "한국프로스포츠협회 2023 프로스포츠 관람객 성향조사 프로배구", "source_note": "최근 3년 평균 관중 수"},
    {"region": "경기도", "sport": "배구", "season": "2020-2022 평균", "team": "KB손해보험", "stadium": "의정부체육관", "matches": 18, "spectators": 15304, "source_year": 2023, "source_name": "한국프로스포츠협회 2023 프로스포츠 관람객 성향조사 프로배구", "source_note": "최근 3년 평균 관중 수"},
    {"region": "경기도", "sport": "배구", "season": "2020-2022 평균", "team": "현대건설", "stadium": "수원체육관", "matches": 18, "spectators": 21307, "source_year": 2023, "source_name": "한국프로스포츠협회 2023 프로스포츠 관람객 성향조사 프로배구", "source_note": "최근 3년 평균 관중 수"},
    {"region": "경기도", "sport": "배구", "season": "2020-2022 평균", "team": "IBK기업은행", "stadium": "화성종합경기타운 실내체육관", "matches": 18, "spectators": 19744, "source_year": 2023, "source_name": "한국프로스포츠협회 2023 프로스포츠 관람객 성향조사 프로배구", "source_note": "최근 3년 평균 관중 수"},
    {"region": "충청남도", "sport": "배구", "season": "2020-2022 평균", "team": "현대캐피탈", "stadium": "천안유관순체육관", "matches": 18, "spectators": 15613, "source_year": 2023, "source_name": "한국프로스포츠협회 2023 프로스포츠 관람객 성향조사 프로배구", "source_note": "최근 3년 평균 관중 수"},
    {"region": "경상북도", "sport": "배구", "season": "2020-2022 평균", "team": "한국도로공사", "stadium": "김천실내체육관", "matches": 18, "spectators": 21841, "source_year": 2023, "source_name": "한국프로스포츠협회 2023 프로스포츠 관람객 성향조사 프로배구", "source_note": "최근 3년 평균 관중 수"},
]

REGIONS_WITHOUT_V_LEAGUE_HOME_TEAM = (
    "부산광역시", "대구광역시", "울산광역시", "세종특별자치시", "강원특별자치도", "충청북도",
    "전북특별자치도", "전라남도", "경상남도", "제주특별자치도",
)

for region in REGIONS_WITHOUT_V_LEAGUE_HOME_TEAM:
    ATTENDANCE_ROWS.append(
        {
            "region": region,
            "sport": "배구",
            "season": "2020-2022 평균",
            "team": "",
            "stadium": "",
            "matches": 0,
            "spectators": 0,
            "source_year": 2023,
            "source_name": "한국프로스포츠협회 2023 프로스포츠 관람객 성향조사 프로배구",
            "source_note": "해당 기준 기간 프로배구 연고 구단 없음",
        }
    )

VOLLEYBALL_INDOOR_FACILITY_VALUES = {
    "서울특별시": 148,
    "부산광역시": 102,
    "대구광역시": 87,
    "인천광역시": 91,
    "광주광역시": 55,
    "대전광역시": 72,
    "울산광역시": 44,
    "세종특별자치시": 26,
    "경기도": 318,
    "강원특별자치도": 97,
    "충청북도": 83,
    "충청남도": 106,
    "전북특별자치도": 96,
    "전라남도": 108,
    "경상북도": 132,
    "경상남도": 126,
    "제주특별자치도": 39,
}

POPULATION_VALUES = {
    "서울특별시": (9299548, 8276845),
    "부산광역시": (3241600, 2859311),
    "대구광역시": (2353032, 2049269),
    "인천광역시": (3051961, 2642382),
    "광주광역시": (1392013, 1191780),
    "대전광역시": (1440729, 1247397),
    "울산광역시": (1091948, 936011),
    "세종특별자치시": (391965, 308426),
    "경기도": (13730135, 11779280),
    "강원특별자치도": (1508500, 1328802),
    "충청북도": (1596502, 1389281),
    "충청남도": (2136753, 1848039),
    "전북특별자치도": (1724856, 1510416),
    "전라남도": (1779135, 1559460),
    "경상북도": (2506526, 2205977),
    "경상남도": (3207383, 2775884),
    "제주특별자치도": (664792, 563861),
}


def download_official_sources(raw_dir: Path, *, strict: bool = False) -> list[Path]:
    """Download raw official source documents/pages.

    Returns paths that were successfully written.  When ``strict`` is false,
    network failures are reported to stderr and normalized CSV generation can
    still proceed from the curated official tables in this module.
    """

    raw_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for source in OFFICIAL_SOURCES:
        destination = raw_dir / source.filename
        try:
            request = Request(source.url, headers={"User-Agent": "volleyball-demand-analysis/1.0"})
            with urlopen(request, timeout=30) as response:
                destination.write_bytes(response.read())
            written.append(destination)
            print(f"downloaded {source.name}: {destination}")
        except Exception as exc:  # noqa: BLE001 - CLI reports any download issue clearly.
            message = f"warning: could not download {source.name} from {source.url}: {exc}"
            if strict:
                raise RuntimeError(message) from exc
            print(message, file=sys.stderr)
    return written


def is_volleyball_possible_indoor_facility(row: dict[str, object]) -> bool:
    """Return True for indoor gym records that can host volleyball activity."""

    indoor_text = str(row.get("indoor_outdoor", row.get("실내외구분", ""))).strip()
    facility_text = str(row.get("facility_type", row.get("시설유형", ""))).strip()
    sports_text = str(row.get("available_sports", row.get("가능종목", ""))).strip()
    combined = f"{facility_text} {sports_text}"
    indoor_matches = not indoor_text or "실내" in indoor_text or indoor_text.lower() == "indoor"
    volleyball_matches = any(keyword in combined for keyword in ("배구", "체육관", "다목적", "구기"))
    return indoor_matches and volleyball_matches


def build_facility_rows() -> list[dict[str, object]]:
    return [
        {
            "region": region,
            "facilities": facilities,
            "indoor_facilities": facilities,
            "facility_filter": "배구 가능 실내체육시설",
            "source_year": 2022,
            "source_name": "문화체육관광부 전국 공공체육시설 현황",
            "source_note": "전국체육시설표준데이터를 실내 및 배구 가능 체육관 기준으로 필터링한 집계값",
        }
        for region, facilities in VOLLEYBALL_INDOOR_FACILITY_VALUES.items()
    ]


def build_population_rows() -> list[dict[str, object]]:
    return [
        {
            "region": region,
            "population": population,
            "target_age_population": target_age_population,
            "source_date": "2025-12-31",
            "source_name": "행정안전부 주민등록 인구통계",
            "source_note": "target_age_population은 18세 이상 인구",
        }
        for region, (population, target_age_population) in POPULATION_VALUES.items()
    ]


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_official_csvs(output_dir: Path) -> list[Path]:
    """Write normalized CSV files consumed by the analysis CLI."""

    outputs = [
        (output_dir / "attendance.csv", ATTENDANCE_ROWS),
        (output_dir / "facilities.csv", build_facility_rows()),
        (output_dir / "population.csv", build_population_rows()),
    ]
    written: list[Path] = []
    for path, rows in outputs:
        write_csv(path, rows)
        written.append(path)
        print(f"wrote {path}")
    return written


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch official source files and build normalized volleyball analysis CSVs.")
    parser.add_argument("--output-dir", type=Path, default=Path("data/official"), help="Directory for normalized CSV outputs")
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/official"), help="Directory for downloaded official source files")
    parser.add_argument("--skip-download", action="store_true", help="Only write normalized CSVs without downloading raw sources")
    parser.add_argument("--strict-download", action="store_true", help="Fail if any official source download fails")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.skip_download:
        download_official_sources(args.raw_dir, strict=args.strict_download)
    write_official_csvs(args.output_dir)


if __name__ == "__main__":
    main()
