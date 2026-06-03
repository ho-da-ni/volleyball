# 프로배구 관람 활성화를 위한 지역별 잠재수요 분석

Python을 활용해 프로배구 관람 데이터와 지역별 인구·체육시설 데이터를 결합하고, 전국 17개 시도 단위의 관람 잠재수요 점수와 지역 유형을 산출하는 분석 프로젝트입니다.

## 분석 목표

- 지역별 프로배구 관람 수요와 경기 공급의 불균형을 파악합니다.
- 인구 기반, 체육 인프라, 기존 관람 수요를 종합해 팬 확장 가능성이 높은 지역을 도출합니다.
- 컵대회, 올스타전, 팝업 응원전, 유소년 배구교실 등 관람 활성화 프로그램의 우선 운영지역을 제안합니다.

## 현재 구현된 분석 기능

- CSV 입력 데이터의 영문/국문 컬럼명 자동 인식
- `서울`, `서울특별시`처럼 다른 지역명 표기를 17개 시도 표준명으로 통일
- 지역별 경기 수, 관람객 수, 시설 수, 인구 수 집계
- 경기당 평균 관람객, 인구 대비 관람률, 인구 10만 명당 시설 수, 경기 공급 밀도 산출
- Min-Max Scaling 기반 관람수요지수, 체육인프라지수, 인구잠재력지수, 공급공백지수 계산
- 가중합 방식의 최종 배구 관람 잠재수요 점수 계산
- 표준 라이브러리 기반 K-means 군집분석과 지역 유형 라벨링
- CSV 결과표, JSON 요약, Markdown 분석 리포트 출력

## 입력 데이터 형식

세 개의 CSV 파일이 필요합니다. 컬럼명은 아래 영문명 또는 대표 국문명을 사용할 수 있습니다.

| 파일 | 필수 컬럼 | 설명 |
| --- | --- | --- |
| 관람 데이터 | `region`, `matches`, `spectators` | 지역, 경기 수, 관람객 수 |
| 체육시설 데이터 | `region`, `facilities`, `indoor_facilities` | 지역, 전체 체육시설 수, 실내체육시설 수 |
| 인구 데이터 | `region`, `population`, `target_age_population` | 지역, 총인구, 청년·학생층 등 타깃 인구 |

샘플 데이터는 `data/sample/`에 포함되어 있어 바로 실행해볼 수 있습니다.

## 실행 예시

```bash
python -m src.volleyball_demand_analysis \
  --attendance data/sample/attendance.csv \
  --facilities data/sample/facilities.csv \
  --population data/sample/population.csv \
  --output data/processed/region_scores.csv \
  --summary data/processed/summary.json \
  --report data/processed/report.md
```

## 주요 산출물

- `region_scores.csv`: 지역별 최종 점수, 세부 지표, 군집, 추천 실행안
- `summary.json`: 상위 지역과 유형별 지역 수 요약
- `report.md`: 분석 결과를 바로 검토할 수 있는 Markdown 리포트

## 프로젝트 구조

```text
.
├── data/
│   └── sample/
│       ├── attendance.csv
│       ├── facilities.csv
│       └── population.csv
├── docs/
│   └── analysis_plan.md
├── src/
│   └── volleyball_demand_analysis.py
└── tests/
    └── test_volleyball_demand_analysis.py
```

## 해석 시 주의사항

샘플 데이터는 실행 검증용 예시 데이터입니다. 실제 공모 분석에서는 공식 관람객 데이터, 체육시설 데이터, 주민등록 인구 데이터로 교체한 뒤 결과를 해석해야 합니다.
