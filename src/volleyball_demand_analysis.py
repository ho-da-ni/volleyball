"""Run a regional potential-demand analysis for professional volleyball.

The module intentionally uses only the Python standard library so the analysis
can run in restricted environments.  It accepts three CSV inputs, aggregates the
inputs to the 17-province level, calculates weighted demand indicators, assigns
K-means based region types, and writes CSV/JSON/Markdown outputs.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Iterable, Mapping, Sequence
from urllib.parse import urlparse
from urllib.request import Request, urlopen

STANDARD_REGIONS = {
    "서울": "서울특별시",
    "서울특별시": "서울특별시",
    "부산": "부산광역시",
    "부산광역시": "부산광역시",
    "대구": "대구광역시",
    "대구광역시": "대구광역시",
    "인천": "인천광역시",
    "인천광역시": "인천광역시",
    "광주": "광주광역시",
    "광주광역시": "광주광역시",
    "대전": "대전광역시",
    "대전광역시": "대전광역시",
    "울산": "울산광역시",
    "울산광역시": "울산광역시",
    "세종": "세종특별자치시",
    "세종특별자치시": "세종특별자치시",
    "경기": "경기도",
    "경기도": "경기도",
    "강원": "강원특별자치도",
    "강원도": "강원특별자치도",
    "강원특별자치도": "강원특별자치도",
    "충북": "충청북도",
    "충청북도": "충청북도",
    "충남": "충청남도",
    "충청남도": "충청남도",
    "전북": "전북특별자치도",
    "전라북도": "전북특별자치도",
    "전북특별자치도": "전북특별자치도",
    "전남": "전라남도",
    "전라남도": "전라남도",
    "경북": "경상북도",
    "경상북도": "경상북도",
    "경남": "경상남도",
    "경상남도": "경상남도",
    "제주": "제주특별자치도",
    "제주도": "제주특별자치도",
    "제주특별자치도": "제주특별자치도",
}

REGION_ORDER = list(dict.fromkeys(STANDARD_REGIONS.values()))

ATTENDANCE_ALIASES = {
    "region": ("region", "지역", "시도", "광역자치단체", "sido"),
    "matches": ("matches", "경기수", "경기 수", "game_count", "games"),
    "spectators": ("spectators", "관람객수", "관람객 수", "attendance", "audience"),
}
ATTENDANCE_OPTIONAL_ALIASES = {
    "sport": ("sport", "종목"),
    "season": ("season", "시즌", "연도"),
    "team": ("team", "구단", "팀"),
    "stadium": ("stadium", "경기장", "홈경기장"),
}
FACILITY_ALIASES = {
    "region": ("region", "지역", "시도", "광역자치단체", "sido"),
    "facilities": ("facilities", "시설수", "시설 수", "facility_count"),
    "indoor_facilities": ("indoor_facilities", "실내체육시설수", "실내 시설 수", "indoor_count"),
}
POPULATION_ALIASES = {
    "region": ("region", "지역", "시도", "광역자치단체", "sido"),
    "population": ("population", "총인구", "인구", "population_total"),
    "target_age_population": (
        "target_age_population",
        "타깃연령인구",
        "청년학생인구",
        "청년·학생층 인구",
        "target_population",
    ),
}

NUMERIC_OUTPUT_COLUMNS = (
    "matches",
    "spectators",
    "avg_spectators_per_match",
    "population",
    "target_age_population",
    "facilities",
    "indoor_facilities",
    "spectator_rate",
    "facilities_per_100k",
    "target_age_share",
    "match_supply_per_100k",
    "demand_index",
    "infrastructure_index",
    "population_index",
    "supply_gap_index",
    "potential_demand_score",
)


@dataclass(frozen=True)
class IndicatorWeights:
    """Weights used to calculate the final potential-demand score."""

    demand: float = 0.30
    infrastructure: float = 0.25
    population: float = 0.25
    supply_gap: float = 0.20

    def validate(self) -> None:
        total = self.demand + self.infrastructure + self.population + self.supply_gap
        if round(total, 6) != 1.0:
            raise ValueError(f"Indicator weights must sum to 1.0, got {total:.6f}")


@dataclass(frozen=True)
class AnalysisOutputs:
    """Paths written by a completed analysis run."""

    scores_csv: Path
    summary_json: Path | None
    report_md: Path | None


CsvResource = str | Path


def standardize_region_name(value: object) -> str:
    """Return a standard 17-province region name."""

    region = str(value or "").strip()
    return STANDARD_REGIONS.get(region, region)


def safe_float(value: object) -> float:
    """Parse numbers that may contain commas, blanks, or percent signs."""

    if value is None:
        return 0.0
    text = str(value).strip().replace(",", "").replace("%", "")
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def safe_divide(numerator: float, denominator: float, multiplier: float = 1.0) -> float:
    """Divide while returning 0 for missing or zero denominators."""

    if denominator == 0:
        return 0.0
    return numerator / denominator * multiplier


def min_max_scale(values: Sequence[float], *, reverse: bool = False) -> list[float]:
    """Scale numeric values to a 0-100 range."""

    numbers = [safe_float(value) for value in values]
    if not numbers:
        return []
    minimum = min(numbers)
    maximum = max(numbers)
    if maximum == minimum:
        scaled = [0.0 for _ in numbers]
    else:
        scaled = [(value - minimum) / (maximum - minimum) * 100 for value in numbers]
    if reverse:
        return [100 - value for value in scaled]
    return scaled


def resolve_columns(fieldnames: Sequence[str] | None, aliases: Mapping[str, Sequence[str]]) -> dict[str, str]:
    """Resolve canonical column names from a CSV header using alias lists."""

    fieldnames = list(fieldnames or [])
    normalized = {name.replace(" ", "").lower(): name for name in fieldnames}
    resolved: dict[str, str] = {}
    for canonical, candidates in aliases.items():
        for candidate in candidates:
            key = candidate.replace(" ", "").lower()
            if key in normalized:
                resolved[canonical] = normalized[key]
                break
        if canonical not in resolved:
            raise ValueError(
                f"Missing required column for {canonical!r}. "
                f"Accepted aliases: {', '.join(candidates)}. CSV columns: {', '.join(fieldnames)}"
            )
    return resolved


def is_url(resource: CsvResource) -> bool:
    """Return True when a CSV resource is an HTTP(S) URL."""

    parsed = urlparse(str(resource))
    return parsed.scheme in {"http", "https"}


def open_csv_resource(resource: CsvResource) -> io.StringIO:
    """Open a local path or HTTP(S) URL as UTF-8 CSV text."""

    if is_url(resource):
        request = Request(str(resource), headers={"User-Agent": "volleyball-demand-analysis/1.0"})
        with urlopen(request, timeout=30) as response:
            charset = response.headers.get_content_charset() or "utf-8-sig"
            return io.StringIO(response.read().decode(charset))

    return io.StringIO(Path(resource).read_text(encoding="utf-8-sig"))


def resolve_optional_columns(
    fieldnames: Sequence[str] | None,
    aliases: Mapping[str, Sequence[str]],
) -> dict[str, str]:
    """Resolve optional canonical columns from a CSV header when present."""

    fieldnames = list(fieldnames or [])
    normalized = {name.replace(" ", "").lower(): name for name in fieldnames}
    resolved: dict[str, str] = {}
    for canonical, candidates in aliases.items():
        for candidate in candidates:
            key = candidate.replace(" ", "").lower()
            if key in normalized:
                resolved[canonical] = normalized[key]
                break
    return resolved


def read_csv_rows(
    resource: CsvResource,
    aliases: Mapping[str, Sequence[str]],
    optional_aliases: Mapping[str, Sequence[str]] | None = None,
) -> list[dict[str, str]]:
    """Read a local or URL CSV and return rows keyed by canonical column names."""

    with open_csv_resource(resource) as file:
        reader = csv.DictReader(file)
        columns = resolve_columns(reader.fieldnames, aliases)
        columns.update(resolve_optional_columns(reader.fieldnames, optional_aliases or {}))
        rows: list[dict[str, str]] = []
        for raw_row in reader:
            rows.append({canonical: raw_row[source] for canonical, source in columns.items()})
    return rows


def is_volleyball_attendance_row(row: Mapping[str, object]) -> bool:
    """Return True for volleyball rows or legacy rows without a sport column."""

    sport = str(row.get("sport", "")).strip().lower()
    return not sport or sport in {"배구", "프로배구", "volleyball", "v-league", "v리그"}


def aggregate_attendance(rows: Iterable[Mapping[str, object]]) -> dict[str, dict[str, float]]:
    """Aggregate volleyball match supply and spectator demand by region."""

    aggregated: dict[str, dict[str, float]] = defaultdict(lambda: {"matches": 0.0, "spectators": 0.0})
    for row in rows:
        if not is_volleyball_attendance_row(row):
            continue
        region = standardize_region_name(row.get("region"))
        if not region:
            continue
        aggregated[region]["matches"] += safe_float(row.get("matches"))
        aggregated[region]["spectators"] += safe_float(row.get("spectators"))

    for values in aggregated.values():
        values["avg_spectators_per_match"] = safe_divide(values["spectators"], values["matches"])
    return dict(aggregated)


def aggregate_facilities(rows: Iterable[Mapping[str, object]]) -> dict[str, dict[str, float]]:
    """Aggregate sports-facility counts by region."""

    aggregated: dict[str, dict[str, float]] = defaultdict(
        lambda: {"facilities": 0.0, "indoor_facilities": 0.0}
    )
    for row in rows:
        region = standardize_region_name(row.get("region"))
        if not region:
            continue
        aggregated[region]["facilities"] += safe_float(row.get("facilities"))
        aggregated[region]["indoor_facilities"] += safe_float(row.get("indoor_facilities"))
    return dict(aggregated)


def aggregate_population(rows: Iterable[Mapping[str, object]]) -> dict[str, dict[str, float]]:
    """Aggregate population and target-age population by region."""

    aggregated: dict[str, dict[str, float]] = defaultdict(
        lambda: {"population": 0.0, "target_age_population": 0.0}
    )
    for row in rows:
        region = standardize_region_name(row.get("region"))
        if not region:
            continue
        aggregated[region]["population"] += safe_float(row.get("population"))
        aggregated[region]["target_age_population"] += safe_float(row.get("target_age_population"))
    return dict(aggregated)


def build_region_scores(
    attendance_rows: Iterable[Mapping[str, object]],
    facility_rows: Iterable[Mapping[str, object]],
    population_rows: Iterable[Mapping[str, object]],
    weights: IndicatorWeights | None = None,
) -> list[dict[str, object]]:
    """Build regional indicator scores and final volleyball potential-demand score."""

    weights = weights or IndicatorWeights()
    weights.validate()

    attendance = aggregate_attendance(attendance_rows)
    facilities = aggregate_facilities(facility_rows)
    population = aggregate_population(population_rows)
    regions = sorted(set(REGION_ORDER) | set(attendance) | set(facilities) | set(population), key=region_sort_key)

    rows: list[dict[str, object]] = []
    for region in regions:
        row = {
            "region": region,
            "matches": attendance.get(region, {}).get("matches", 0.0),
            "spectators": attendance.get(region, {}).get("spectators", 0.0),
            "avg_spectators_per_match": attendance.get(region, {}).get("avg_spectators_per_match", 0.0),
            "population": population.get(region, {}).get("population", 0.0),
            "target_age_population": population.get(region, {}).get("target_age_population", 0.0),
            "facilities": facilities.get(region, {}).get("facilities", 0.0),
            "indoor_facilities": facilities.get(region, {}).get("indoor_facilities", 0.0),
        }
        row["spectator_rate"] = safe_divide(row["spectators"], row["population"], 100)
        row["facilities_per_100k"] = safe_divide(row["facilities"], row["population"], 100_000)
        row["target_age_share"] = safe_divide(row["target_age_population"], row["population"], 100)
        row["match_supply_per_100k"] = safe_divide(row["matches"], row["population"], 100_000)
        rows.append(row)

    add_weighted_index(
        rows,
        "demand_index",
        {"spectators": 0.4, "avg_spectators_per_match": 0.3, "spectator_rate": 0.3},
    )
    add_weighted_index(
        rows,
        "infrastructure_index",
        {"facilities": 0.4, "facilities_per_100k": 0.3, "indoor_facilities": 0.3},
    )
    add_weighted_index(rows, "population_index", {"population": 0.6, "target_age_share": 0.4})

    supply_scores = min_max_scale([float(row["match_supply_per_100k"]) for row in rows], reverse=True)
    for row, supply_gap_score in zip(rows, supply_scores, strict=True):
        row["supply_gap_index"] = (
            float(row["population_index"]) * 0.4
            + float(row["infrastructure_index"]) * 0.3
            + supply_gap_score * 0.3
        )
        row["potential_demand_score"] = (
            float(row["demand_index"]) * weights.demand
            + float(row["infrastructure_index"]) * weights.infrastructure
            + float(row["population_index"]) * weights.population
            + float(row["supply_gap_index"]) * weights.supply_gap
        )

    rows.sort(key=lambda row: float(row["potential_demand_score"]), reverse=True)
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
    return rows


def add_weighted_index(rows: list[dict[str, object]], output_column: str, components: Mapping[str, float]) -> None:
    """Add a weighted 0-100 index from multiple source columns."""

    scaled_by_column = {
        column: min_max_scale([float(row[column]) for row in rows]) for column in components
    }
    for index, row in enumerate(rows):
        row[output_column] = sum(scaled_by_column[column][index] * weight for column, weight in components.items())


def region_sort_key(region: str) -> tuple[int, str]:
    """Sort official regions first in administrative order, then unknown regions."""

    try:
        return (REGION_ORDER.index(region), region)
    except ValueError:
        return (len(REGION_ORDER), region)


def assign_region_clusters(rows: list[dict[str, object]], cluster_count: int = 4) -> list[dict[str, object]]:
    """Assign K-means clusters and human-readable region types."""

    if not rows:
        return rows
    cluster_count = max(1, min(cluster_count, len(rows)))
    features = [
        [
            float(row["demand_index"]),
            float(row["infrastructure_index"]),
            float(row["population_index"]),
            float(row["supply_gap_index"]),
        ]
        for row in rows
    ]
    assignments, centroids = kmeans(features, cluster_count)
    labels = label_clusters(centroids)
    for row, assignment in zip(rows, assignments, strict=True):
        row["cluster"] = assignment + 1
        row["region_type"] = labels[assignment]
        row["recommendation"] = recommend_action(row["region_type"])
    return rows


def kmeans(
    features: Sequence[Sequence[float]],
    cluster_count: int,
    max_iterations: int = 100,
) -> tuple[list[int], list[list[float]]]:
    """Small deterministic K-means implementation for four-dimensional scores."""

    centroids = initialize_centroids(features, cluster_count)
    assignments = [0 for _ in features]
    for _ in range(max_iterations):
        new_assignments = [nearest_centroid(feature, centroids) for feature in features]
        if new_assignments == assignments:
            break
        assignments = new_assignments
        centroids = recompute_centroids(features, assignments, centroids)
    return assignments, centroids


def initialize_centroids(features: Sequence[Sequence[float]], cluster_count: int) -> list[list[float]]:
    """Pick deterministic initial centroids across the score distribution."""

    ordered = sorted(features, key=lambda values: sum(values), reverse=True)
    if cluster_count == 1:
        return [list(ordered[0])]
    step = (len(ordered) - 1) / (cluster_count - 1)
    return [list(ordered[round(index * step)]) for index in range(cluster_count)]


def nearest_centroid(feature: Sequence[float], centroids: Sequence[Sequence[float]]) -> int:
    """Return index of the nearest centroid by Euclidean distance."""

    distances = [math.dist(feature, centroid) for centroid in centroids]
    return distances.index(min(distances))


def recompute_centroids(
    features: Sequence[Sequence[float]],
    assignments: Sequence[int],
    previous_centroids: Sequence[Sequence[float]],
) -> list[list[float]]:
    """Recompute centroids while keeping empty clusters stable."""

    centroids: list[list[float]] = []
    for cluster_index, previous in enumerate(previous_centroids):
        members = [feature for feature, assignment in zip(features, assignments, strict=True) if assignment == cluster_index]
        if not members:
            centroids.append(list(previous))
            continue
        centroids.append([mean(values) for values in zip(*members, strict=True)])
    return centroids


def label_clusters(centroids: Sequence[Sequence[float]]) -> dict[int, str]:
    """Map centroid profiles to strategic region-type labels."""

    labels: dict[int, str] = {}
    remaining = set(range(len(centroids)))

    high_demand = max(remaining, key=lambda index: centroids[index][0])
    labels[high_demand] = "기존 흥행지역"
    remaining.remove(high_demand)

    if remaining:
        potential = max(remaining, key=lambda index: centroids[index][2] + centroids[index][3])
        labels[potential] = "잠재 고수요지역"
        remaining.remove(potential)

    if remaining:
        infrastructure_gap = min(remaining, key=lambda index: centroids[index][1])
        labels[infrastructure_gap] = "인프라 보완지역"
        remaining.remove(infrastructure_gap)

    for index in remaining:
        labels[index] = "장기 육성지역"
    return labels


def recommend_action(region_type: object) -> str:
    """Return an action recommendation for each strategic region type."""

    recommendations = {
        "기존 흥행지역": "정규리그 빅매치, 멤버십 혜택, 재관람 캠페인 강화",
        "잠재 고수요지역": "컵대회·올스타전 유치, 팝업 응원전, 원정 팬 마케팅 우선 추진",
        "인프라 보완지역": "학교·생활체육 연계 유소년 교실과 시설 활용 협약 우선 추진",
        "장기 육성지역": "저비용 체험 이벤트, 지역 배구협회 협업, 장기 팬덤 육성 캠페인 추진",
    }
    return recommendations.get(str(region_type), "지역 특성 추가 검토")


def build_summary(rows: Sequence[Mapping[str, object]], top_n: int = 5) -> dict[str, object]:
    """Create a JSON-serialisable analysis summary."""

    type_counts: dict[str, int] = defaultdict(int)
    for row in rows:
        type_counts[str(row.get("region_type", "미분류"))] += 1
    return {
        "region_count": len(rows),
        "top_regions": [
            {
                "rank": row["rank"],
                "region": row["region"],
                "potential_demand_score": round(float(row["potential_demand_score"]), 2),
                "region_type": row.get("region_type", "미분류"),
                "recommendation": row.get("recommendation", "지역 특성 추가 검토"),
            }
            for row in rows[:top_n]
        ],
        "region_type_counts": dict(type_counts),
    }


def write_scores_csv(rows: Sequence[Mapping[str, object]], path: Path) -> None:
    """Write regional scores to CSV."""

    fieldnames = [
        "rank",
        "region",
        *NUMERIC_OUTPUT_COLUMNS,
        "cluster",
        "region_type",
        "recommendation",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(format_output_row(row))


def format_output_row(row: Mapping[str, object]) -> dict[str, object]:
    """Round numeric output values for readable CSV reports."""

    formatted = dict(row)
    for column in NUMERIC_OUTPUT_COLUMNS:
        formatted[column] = round(float(formatted.get(column, 0.0)), 4)
    return formatted


def write_summary_json(summary: Mapping[str, object], path: Path) -> None:
    """Write summary metadata to JSON."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def write_markdown_report(rows: Sequence[Mapping[str, object]], summary: Mapping[str, object], path: Path) -> None:
    """Write a compact analyst-facing Markdown report."""

    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 프로배구 관람 잠재수요 분석 결과",
        "",
        f"- 분석 지역 수: {summary['region_count']}",
        "- 최종 점수는 관람수요 30%, 체육인프라 25%, 인구잠재력 25%, 공급공백 20%를 반영했습니다.",
        "",
        "## 상위 지역",
        "",
        "| 순위 | 지역 | 점수 | 유형 | 추천 실행안 |",
        "| ---: | --- | ---: | --- | --- |",
    ]
    for row in rows[:10]:
        lines.append(
            "| {rank} | {region} | {score:.2f} | {region_type} | {recommendation} |".format(
                rank=row["rank"],
                region=row["region"],
                score=float(row["potential_demand_score"]),
                region_type=row.get("region_type", "미분류"),
                recommendation=row.get("recommendation", "지역 특성 추가 검토"),
            )
        )
    lines.extend([
        "",
        "## 유형별 지역 수",
        "",
    ])
    for region_type, count in summary["region_type_counts"].items():
        lines.append(f"- {region_type}: {count}개")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_analysis(
    attendance_path: CsvResource,
    facilities_path: CsvResource,
    population_path: CsvResource,
    output_path: Path,
    summary_path: Path | None = None,
    report_path: Path | None = None,
    cluster_count: int = 4,
    weights: IndicatorWeights | None = None,
) -> AnalysisOutputs:
    """Read CSV inputs, run scoring/clustering, and write requested outputs."""

    rows = build_region_scores(
        attendance_rows=read_csv_rows(attendance_path, ATTENDANCE_ALIASES, ATTENDANCE_OPTIONAL_ALIASES),
        facility_rows=read_csv_rows(facilities_path, FACILITY_ALIASES),
        population_rows=read_csv_rows(population_path, POPULATION_ALIASES),
        weights=weights,
    )
    assign_region_clusters(rows, cluster_count=cluster_count)
    write_scores_csv(rows, output_path)
    summary = build_summary(rows)
    if summary_path:
        write_summary_json(summary, summary_path)
    if report_path:
        write_markdown_report(rows, summary, report_path)
    return AnalysisOutputs(output_path, summary_path, report_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Calculate regional volleyball potential-demand scores.")
    parser.add_argument("--attendance", required=True, help="Local path or URL CSV with region, matches, spectators columns")
    parser.add_argument("--facilities", required=True, help="Local path or URL CSV with region, facilities, indoor_facilities columns")
    parser.add_argument("--population", required=True, help="Local path or URL CSV with region, population, target_age_population columns")
    parser.add_argument("--output", type=Path, required=True, help="Output score CSV path")
    parser.add_argument("--summary", type=Path, help="Optional output summary JSON path")
    parser.add_argument("--report", type=Path, help="Optional output Markdown report path")
    parser.add_argument("--clusters", type=int, default=4, help="Number of K-means clusters to assign")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_analysis(
        attendance_path=args.attendance,
        facilities_path=args.facilities,
        population_path=args.population,
        output_path=args.output,
        summary_path=args.summary,
        report_path=args.report,
        cluster_count=args.clusters,
    )


if __name__ == "__main__":
    main()
