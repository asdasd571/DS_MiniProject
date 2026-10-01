# ESS 배터리 수명 예측

MIT-Stanford Battery Dataset의 초기 100회 충·방전 신호로 총 `cycle_life`를 예측한다. EDA → 관찰 → feature engineering → 모델 선택 → 외부 평가 → ESS 해석을 실제 실행 결과로 연결했다.

## 프로젝트 개요

- Batch 1 (`2017-05-12`): 학습·CV·홀드아웃 전용
- Batch 2 (`2018-02-20`): 최종 Test 전용
- Batch 3 (`2018-04-12`): 추가 일반화 Test 전용
- Task / Target / Metric: regression / `cycle_life` / 원 cycle 단위 MAPE (%)
- 학습 target: `log(cycle_life)`; 평가 전에 지수 역변환
- `2018-04-03` varcharge 배치는 사용하지 않음

## 파일 구조

```text
data/README.md
notebooks/{01_EDA,02_feature_engineering,03_modeling}.ipynb
src/{preprocess,features,evaluation,train}.py
results/{figures,tables}/
results/feature_dataset_batch{1,2,3}.csv
results/model_performance.csv
```

## 환경 설정

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## 데이터 준비

원본 MAT 파일명은 [data/README.md](data/README.md)에 정리했다. 수 GB 파일 전체를 메모리에 올리지 않고 셀별로 summary 및 cycle 10/100의 `Qdlin`만 읽는다.

```bash
python -m src.train \
  --batch1 /Users/nak/Downloads/archive/2017-05-12_batchdata_updated_struct_errorcorrect.mat \
  --batch2 /Users/nak/Downloads/archive/2018-02-20_batchdata_updated_struct_errorcorrect.mat \
  --batch3 /Users/nak/Downloads/archive/2018-04-12_batchdata_updated_struct_errorcorrect.mat \
  --output-dir results
```

원본 셀은 Batch 1/2/3 각각 46/47/46개다. 저자 공개 전처리의 Batch 1 미도달 셀 5개, Batch 2 continuation 5개, Batch 3 noisy channel 6개를 제외했고, Batch 2의 target 결측 8개도 제외했다. 최종 모델링 가능 셀은 41/34/40개다. 짧은 수명 자체를 이유로 제외한 셀은 없으며 근거는 `results/tables/excluded_cells.csv`에 있다.

## EDA

### 1. Cycle Life 분포

**목적 → 결과.** 외부 일반화 난이도를 확인했다. 중앙값은 Batch 1/2/3에서 842.0/468.5/964.5 cycles였다. Batch 2는 500 미만이 76.5%지만 Batch 1에는 없고, Batch 3는 1000 초과가 47.5%다.

![Cycle life histogram](results/figures/eda_cycle_life_hist.png)

**발견 → 시사점.** Batch 2는 단수명 방향, Batch 3는 장수명 방향의 distribution shift다. 두 외부 배치는 feature 선택과 tuning에서 완전히 격리했다.

### 2. 열화 곡선

![Capacity degradation](results/figures/eda_degradation_curve.png)

초기 QD 곡선은 상당 부분 겹치고 `qd_10`과 수명의 Pearson 상관은 0.101이었다. 절대 QD만으로 구분하기 어려워 초기 slope와 전압별 곡선 변화량을 feature로 만들었다. Cycle 100 이후 값은 누수 방지를 위해 feature에 쓰지 않았다.

### 3. DeltaQ(V)

Cycle 10과 100의 Qdlin을 공통 voltage 구간의 1,000점 grid에 보간한 뒤 point-wise `Q100(V)-Q10(V)`를 계산했다. `log_dq_var = log10(max(var(ΔQ), 1e-12))`이다.

![Delta Q correlation](results/figures/eda_delta_q_vs_cycle_life.png)

Batch 1의 `log_dq_var`와 수명은 Pearson **-0.886**, Spearman **-0.880**이었다. 이는 현재 데이터에서 계산한 값이다. ΔQ 파생치끼리 강한 다중공선성이 있어 정규화 모델을 주요 후보로 삼았다.

### 4. C-rate

![Charging policy](results/figures/eda_charging_policy.png)

정책 문자열을 `first_c_rate`, `switch_soc`, `second_c_rate`로 파싱했다. `first_c_rate`와 수명의 Pearson 상관은 -0.580이지만 정책별 표본이 작고 온도·충전시간과 얽혀 있어 인과관계로 표현하지 않았다. 정책은 feature이자 Group split의 기준이다.

### 5. Correlation

![Feature correlations](results/figures/eda_feature_corr_heatmap.png)

`dq_std`(-0.896), `log_dq_var`(-0.886), `dq_range`(-0.884), `dq_min`(0.883)이 강했다. scaler와 regularization은 pipeline 안에서 fold별 training data에만 fit했다.

## Modeling

### Feature Engineering Strategy

- 약한 QD 절대 신호 → `qd_10`, `qd_100`, `qd_slope_10_100`
- 강한 초기 곡선 변화 → 보간된 ΔQ 통계와 `log_dq_var`
- 정책 차이 → 두 C-rate와 switch SOC
- 보조 신호 → IR 변화, 온도, 충전시간
- 세 배치에 완전히 동일한 추출 함수를 적용

### Model Selection

Batch 1은 charging policy 기반 GroupShuffleSplit으로 hold-out하고 training portion에서 GroupKFold를 수행했다.

| Model | CV MAPE | CV std | Hold-out MAPE |
|---|---:|---:|---:|
| Linear Regression | 16.95% | 2.95 | 68.36% |
| ElasticNet | **8.10%** | **2.21** | 20.58% |
| Gradient Boosting | 10.45% | 2.57 | **8.48%** |

최종 모델은 Gradient Boosting(`learning_rate=0.1`, `max_depth=1`, `n_estimators=100`)이다. ElasticNet의 CV 평균은 더 낮지만 unseen-policy hold-out에서 20.58%로 크게 악화됐다. 깊이 1의 제한된 boosting 모델은 hold-out 8.48%로 비선형성을 포착하면서 복잡도를 억제했다. 작은 cell-level tabular dataset이므로 대규모 딥러닝은 과적합 위험 때문에 제외했다.

## 성능 결과

| 구분 | MAPE | 비고 |
|---|---:|---|
| Batch 1 CV | 10.45% | 모델 선택 기준 |
| Batch 1 Hold-out | 8.48% | unseen policies |
| Batch 2 Test | 37.01% | tuning 미사용 |
| Batch 3 Test | 16.93% | tuning 미사용 |

Train–Valid gap은 -1.98%p, Valid–Batch2 gap은 +28.53%p, 논문 목표 9.1% 대비 Batch2 gap은 +27.91%p다. Batch3는 Batch2보다 20.07%p 낮다. 현재의 엄격한 Batch1-only 학습/Batch2 외부평가 설정에서는 9.1%를 재현하지 못했다.

## 오류 분석

Batch 2의 큰 오류는 실제 400–500 cycle 셀을 600 cycle 이상으로 과대예측한 경우에 집중된다. 가장 큰 오류인 `Batch2_cell_006`은 실제 393, 예측 685 cycles(74.2%)였다. Batch 1에는 500 미만 셀이 없지만 Batch 2에는 76.5%이므로 학습 범위 밖 외삽 실패가 핵심 원인 가설이다.

개선하려면 단수명 학습 셀, OOD 경고 및 예측구간, 논문의 공식 split·batch continuation·noisy-cell 처리와의 별도 비교가 필요하다. Test 결과를 보고 현재 feature나 hyperparameter를 바꾸지는 않았다.

## ESS 도메인 해석

개념적으로 `remaining cycles ≈ predicted total cycle life − current cycle`로 교체 계획, 예방 정비, 재고, 가용성 관리에 활용할 수 있다. 다만 실험실 셀의 초기수명 모델이지 완전한 운영 RUL 모델은 아니다. 실서비스에는 SOC/SOH, calendar aging, 온도, DoD, C-rate, 제조 편차, pack imbalance와 BMS 센서 정보가 추가로 필요하다. OOD 배치에서는 point prediction만으로 정비를 자동화하면 안 된다.

## 참고문헌

Severson, K. A. et al. (2019). *Data-driven prediction of battery cycle life before capacity degradation*. Nature Energy, 4, 383–391. 저자 공개 [data loading code](https://github.com/rdbraatz/data-driven-prediction-of-battery-cycle-life-before-capacity-degradation/blob/master/Load%20Data.ipynb)의 제외 목록을 사용했다.
