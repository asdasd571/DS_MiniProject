# DAY 2 모델 개발 및 평가

## 모델 선택

EDA에서 초기 QD 절대값보다 ΔQ(V), 용량 변화와 충전조건의 조합이 수명 차이를 설명하는 데 중요하다고 판단했다. 나는 이 관계가 하나의 직선보다 여러 조건이 함께 작용하는 비선형 관계에 가깝다고 보았다. Gradient Boosting이 작은 열화 차이를 순차적으로 보완해 장기 수명 위험 Cell을 구분하는 데 기여할 수 있다고 생각해 주 모델로 정했다.

Linear Regression은 선형 기준, ElasticNet은 다중공선성 대응 여부를 확인하는 비교 모델로 사용했다. Batch 1 CV와 충전 정책 Hold-out은 이 판단이 실제 데이터에서도 무리 없이 작동하는지 확인하는 근거로 사용했다. 작은 데이터에서 복잡도를 억제하기 위해 깊이 1의 얕은 Tree를 사용했다. Batch 2와 Batch 3 결과는 선택이나 재튜닝에 사용하지 않았다.

## 성능 보고

| 구분 | MAPE (%) | 비고 |
|---|---:|---|
| Train (Batch 1 CV) | 10.45 | GradientBoosting |
| Valid (Batch 1 Hold-out) | 8.48 | GroupShuffleSplit by charging_policy |
| Test (Batch 2) | 37.01 | external batch; no tuning |
| Gap (Train-Valid) | -1.98 | (+) : 과적합 의심 |
| Gap (Valid-Test) | 28.53 | (+) : 배치 간 일반화 저하 의심 |
| Gap (Target-Test) | 27.91 | Target : 원논문 9.1% |
| Test (Batch 3) | 16.93 | external batch; no tuning |
| Gap (Batch2-Batch3) | -20.07 | Test 성능 간 비교 |
| Gap (Target-Batch3) | 7.83 | Batch 3 기준, 원논문 성능 비교 |

## 오류 분석

- Batch 2 최대 오류 Cell: `Batch2_cell_006` (APE 74.2%)
- Batch 2 과대예측 비율: 88.2%
- Batch 3 최대 오류 Cell: `Batch3_cell_038` (APE 52.2%)

Batch 1 내부 검증과 외부 Batch의 차이는 배치별 수명 분포와 운전조건 차이에서 발생하는 일반화 문제로 해석한다. 특히 Batch 2는 Batch 1에 없던 단수명 영역이 많아 외삽 오류를 확인하는 핵심 테스트다.
