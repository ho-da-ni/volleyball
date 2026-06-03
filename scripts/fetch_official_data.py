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
    {
        "region": "서울특별시",
        "matches": 36,
        "spectators": 45887,
        "source_year": 2023,
        "source_name": "한국프로스포츠협회 2023 프로스포츠 관람객 성향조사 프로배구",
        "source_note": "최근 3년(2020~2022) 구단별 평균 관중 수를 연고 시도별로 합산; 경기수는 14개 구단 6라운드 정규리그 기준 구단당 홈 18경기",
    },
    {"region": "부산광역시", "matches": 0, "spectators": 0, "source_year": 2023, "source_name": "한국프로스포츠협회 2023 프로스포츠 관람객 성향조사 프로배구", "source_note": "해당 기준 기간 프로배구 연고 구단 없음"},
    {"region": "대구광역시", "matches": 0, "spectators": 0, "source_year": 2023, "source_name": "한국프로스포츠협회 2023 프로스포츠 관람객 성향조사 프로배구", "source_note": "해당 기준 기간 프로배구 연고 구단 없음"},
    {"region": "인천광역시", "matches": 36, "spectators": 46634, "source_year": 2023, "source_name": "한국프로스포츠협회 2023 프로스포츠 관람객 성향조사 프로배구", "source_note": "대한항공 13,639 + 흥국생명 32,995"},
    {"region": "광주광역시", "matches": 18, "spectators": 17871, "source_year": 2023, "source_name": "한국프로스포츠협회 2023 프로스포츠 관람객 성향조사 프로배구", "source_note": "페퍼저축은행 17,871"},
    {"region": "대전광역시", "matches": 36, "spectators": 28633, "source_year": 2023, "source_name": "한국프로스포츠협회 2023 프로스포츠 관람객 성향조사 프로배구", "source_note": "삼성화재 9,445 + 정관장 19,188"},
    {"region": "울산광역시", "matches": 0, "spectators": 0, "source_year": 2023, "source_name": "한국프로스포츠협회 2023 프로스포츠 관람객 성향조사 프로배구", "source_note": "해당 기준 기간 프로배구 연고 구단 없음"},
    {"region": "세종특별자치시", "matches": 0, "spectators": 0, "source_year": 2023, "source_name": "한국프로스포츠협회 2023 프로스포츠 관람객 성향조사 프로배구", "source_note": "해당 기준 기간 프로배구 연고 구단 없음"},
    {"region": "경기도", "matches": 90, "spectators": 79922, "source_year": 2023, "source_name": "한국프로스포츠협회 2023 프로스포츠 관람객 성향조사 프로배구", "source_note": "OK금융그룹 11,823 + 한국전력 11,744 + KB손해보험 15,304 + 현대건설 21,307 + IBK기업은행 19,744"},
    {"region": "강원특별자치도", "matches": 0, "spectators": 0, "source_year": 2023, "source_name": "한국프로스포츠협회 2023 프로스포츠 관람객 성향조사 프로배구", "source_note": "해당 기준 기간 프로배구 연고 구단 없음"},
    {"region": "충청북도", "matches": 0, "spectators": 0, "source_year": 2023, "source_name": "한국프로스포츠협회 2023 프로스포츠 관람객 성향조사 프로배구", "source_note": "해당 기준 기간 프로배구 연고 구단 없음"},
    {"region": "충청남도", "matches": 18, "spectators": 15613, "source_year": 2023, "source_name": "한국프로스포츠협회 2023 프로스포츠 관람객 성향조사 프로배구", "source_note": "현대캐피탈 15,613"},
    {"region": "전북특별자치도", "matches": 0, "spectators": 0, "source_year": 2023, "source_name": "한국프로스포츠협회 2023 프로스포츠 관람객 성향조사 프로배구", "source_note": "해당 기준 기간 프로배구 연고 구단 없음"},
    {"region": "전라남도", "matches": 0, "spectators": 0, "source_year": 2023, "source_name": "한국프로스포츠협회 2023 프로스포츠 관람객 성향조사 프로배구", "source_note": "해당 기준 기간 프로배구 연고 구단 없음"},
    {"region": "경상북도", "matches": 18, "spectators": 21841, "source_year": 2023, "source_name": "한국프로스포츠협회 2023 프로스포츠 관람객 성향조사 프로배구", "source_note": "한국도로공사 21,841"},
    {"region": "경상남도", "matches": 0, "spectators": 0, "source_year": 2023, "source_name": "한국프로스포츠협회 2023 프로스포츠 관람객 성향조사 프로배구", "source_note": "해당 기준 기간 프로배구 연고 구단 없음"},
    {"region": "제주특별자치도", "matches": 0, "spectators": 0, "source_year": 2023, "source_name": "한국프로스포츠협회 2023 프로스포츠 관람객 성향조사 프로배구", "source_note": "해당 기준 기간 프로배구 연고 구단 없음"},
]

FACILITY_VALUES = {
    "서울특별시": 3136,
    "부산광역시": 1782,
    "대구광역시": 835,
    "인천광역시": 1266,
    "광주광역시": 1186,
    "대전광역시": 537,
    "울산광역시": 447,
    "세종특별자치시": 196,
    "경기도": 5462,
    "강원특별자치도": 2952,
    "충청북도": 2529,
    "충청남도": 2131,
    "전북특별자치도": 1397,
    "전라남도": 3924,
    "경상북도": 4375,
    "경상남도": 3146,
    "제주특별자치도": 640,
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


def build_facility_rows() -> list[dict[str, object]]:
    return [
        {
            "region": region,
            "facilities": facilities,
            "indoor_facilities": 0,
            "source_year": 2022,
            "source_name": "문화체육관광부 전국 공공체육시설 현황",
            "source_note": "시도별 공공 체육시설 설치수; 공개 집계표에 실내체육시설 세부 합계가 없어 0으로 두고 전체 시설 수 중심으로 분석",
        }
        for region, facilities in FACILITY_VALUES.items()
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
