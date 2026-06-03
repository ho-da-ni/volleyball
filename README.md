# 프로배구 관람 활성화를 위한 지역별 잠재수요 분석

Python을 활용해 프로배구 관람 데이터와 지역별 인구·체육시설 데이터를 결합하고, 전국 17개 시도 단위의 관람 잠재수요 점수와 지역 유형을 산출하는 분석 프로젝트입니다.

## 분석 목표

- 지역별 프로배구 관람 수요와 경기 공급의 불균형을 파악합니다.
- 인구 기반, 체육 인프라, 기존 관람 수요를 종합해 팬 확장 가능성이 높은 지역을 도출합니다.
- 컵대회, 올스타전, 팝업 응원전, 유소년 배구교실 등 관람 활성화 프로그램의 우선 운영지역을 제안합니다.

## 현재 구현된 분석 기능

- 공식 출처 원문 다운로드 및 분석용 CSV 생성 스크립트 제공
- 로컬 CSV 경로 또는 HTTP(S) CSV URL 입력 지원
- CSV 입력 데이터의 영문/국문 컬럼명 자동 인식
- `서울`, `서울특별시`처럼 다른 지역명 표기를 17개 시도 표준명으로 통일
- 지역별 경기 수, 관람객 수, 시설 수, 인구 수 집계
- 경기당 평균 관람객, 인구 대비 관람률, 인구 10만 명당 시설 수, 경기 공급 밀도 산출
- Min-Max Scaling 기반 관람수요지수, 체육인프라지수, 인구잠재력지수, 공급공백지수 계산
- 가중합 방식의 최종 배구 관람 잠재수요 점수 계산
- 표준 라이브러리 기반 K-means 군집분석과 지역 유형 라벨링
- CSV 결과표, JSON 요약, Markdown 분석 리포트, Folium HTML 지도 출력

## 입력 데이터 형식

세 개의 CSV 파일이 필요합니다. 컬럼명은 아래 영문명 또는 대표 국문명을 사용할 수 있습니다.

| 파일 | 필수 컬럼 | 설명 |
| --- | --- | --- |
| 관람 데이터 | `region`, `matches`, `spectators` | 지역, 경기 수, 관람객 수. 현재 공식 입력의 `spectators`는 평균 시즌 총관중이며, `sport`, `season`, `team`, `stadium`, `spectator_basis` 컬럼이 있으면 배구/시즌/구단/경기장/관람객 수 기준 정보를 함께 보존합니다. |
| 체육시설 데이터 | `region`, `facilities` | 지역, 배구 가능 실내체육시설 수 |
| 인구 데이터 | `region`, `population`, `adult_population` | 지역, 총인구, 성인 인구(`data/official`은 18세 이상 인구) |

공식 출처 기반 데이터는 `data/official/`에 포함되어 있어 바로 실행해볼 수 있습니다.

인구잠재력지수는 현재 `adult_population`(18세 이상 성인 인구) 기준입니다. 청년층·학생층 잠재력을 별도로 분석하려면 연령대별 인구 CSV를 추가하고 `adult_population` 대신 해당 연령대 컬럼을 사용하도록 지표를 조정해야 합니다.


## 공식 데이터 내려받기

공식 사이트가 모두 동일한 CSV API를 제공하지는 않기 때문에, 별도 수집 스크립트가 다음 순서로 동작합니다. 관람 데이터는 배구/시즌/구단/경기장 단위로 만들고, 체육시설은 배구 가능 실내체육시설 기준으로 필터링합니다.

1. 한국프로스포츠협회 프로배구 관람객 성향조사 PDF, 공공데이터포털 체육시설 데이터 페이지, 행정안전부 주민등록 인구통계 포털을 `data/raw/official/`에 내려받습니다.
2. 분석 코드가 바로 읽을 수 있는 표준 CSV 3개를 `data/official/`에 생성합니다.
3. 네트워크나 인증 문제로 공식 원문 다운로드가 실패해도, `--strict-download`를 쓰지 않으면 내장된 공식 출처 기반 표를 이용해 CSV 생성은 계속합니다.

```bash
python -m scripts.fetch_official_data \
  --raw-dir data/raw/official \
  --output-dir data/official
```

다운로드까지 반드시 성공해야 하는 검증 모드로 실행하려면 다음처럼 실행합니다.

```bash
python -m scripts.fetch_official_data \
  --raw-dir data/raw/official \
  --output-dir data/official \
  --strict-download
```

## URL 입력 방식

`--attendance`, `--facilities`, `--population`에는 로컬 파일 경로뿐 아니라 CSV를 직접 반환하는 HTTP(S) URL도 넣을 수 있습니다. 즉, 데이터를 저장소에 직접 커밋하지 않고 공공데이터 다운로드 링크, 사내 데이터 포털 CSV 링크, 정적 CSV 원본 URL을 연결해 분석할 수 있습니다.

```bash
python -m src.volleyball_demand_analysis \
  --attendance "https://example.org/volleyball_attendance.csv" \
  --facilities "https://example.org/sports_facilities.csv" \
  --population "https://example.org/population.csv" \
  --output data/processed/region_scores.csv \
  --summary data/processed/summary.json \
  --report data/processed/report.md \
  --map data/processed/volleyball_demand_map.html
```

단, URL은 최종적으로 CSV 텍스트를 반환해야 합니다. 인증키가 필요한 공공데이터 API나 JSON/XML API는 CSV 다운로드 URL로 변환하거나, 별도 수집 스크립트에서 표준 CSV 컬럼(`region`, `matches`, `spectators` 등)으로 저장한 뒤 연결해야 합니다.

## 공식 데이터 출처

| 파일 | 기준 | 출처/산출 방식 |
| --- | --- | --- |
| `data/official/attendance.csv` | 2023 보고서, 최근 3년 평균 시즌 총관중(2020~2022) | `spectators`는 구단별 시즌 총관중의 최근 3년 평균값이며, 분석 시 지역별로 합산한 뒤 `avg_spectators_per_match = spectators / matches`로 경기당 평균 관람객을 계산 |
| `data/official/facilities.csv` | 2022년 | 문화체육관광부 `전국 공공체육시설 현황` 중 배구 가능 실내체육시설 기준 필터링 집계 |
| `data/official/population.csv` | 2025년 12월 31일 | 행정안전부 주민등록 인구통계 시도별 총인구 및 18세 이상 인구 |

## 실행 예시

```bash
python -m src.volleyball_demand_analysis \
  --attendance data/official/attendance.csv \
  --facilities data/official/facilities.csv \
  --population data/official/population.csv \
  --output data/processed/region_scores.csv \
  --summary data/processed/summary.json \
  --report data/processed/report.md \
  --map data/processed/volleyball_demand_map.html
```

## 주요 산출물

- `region_scores.csv`: 지역별 최종 점수, 세부 지표, 군집, 추천 실행안
- `summary.json`: 상위 지역과 유형별 지역 수 요약
- `report.md`: 분석 결과를 바로 검토할 수 있는 Markdown 리포트
- `volleyball_demand_map.html`: 지역별 잠재수요 점수 지도

## 프로젝트 구조

```text
.
├── data/
│   └── official/
│       ├── attendance.csv
│       ├── facilities.csv
│       └── population.csv
├── docs/
│   └── analysis_plan.md
├── scripts/
│   └── fetch_official_data.py
├── src/
│   └── volleyball_demand_analysis.py
└── tests/
    └── test_volleyball_demand_analysis.py
```

## 해석 시 주의사항

`data/official/` 데이터는 공식 보고서와 공공 통계에 근거해 구성했습니다. 다만 관람 데이터는 한국프로스포츠협회 보고서의 2020~2022년 구단별 최근 3년 평균 시즌 총관중을 연고 시도별로 합산한 값이고, 체육시설 데이터는 전체 공공체육시설이 아니라 배구 가능 실내체육시설 기준으로 필터링했습니다. 최신 원자료가 확보되면 같은 CSV 형식으로 교체해 재실행할 수 있습니다.
