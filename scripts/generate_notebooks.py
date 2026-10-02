"""Generate compact, executable notebooks backed by the tested src pipeline."""
from pathlib import Path
import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "notebooks"
OUT.mkdir(exist_ok=True)


def write(name: str, cells: list):
    nb = nbf.v4.new_notebook(cells=cells, metadata={"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}})
    nbf.write(nb, OUT / name)


setup = nbf.v4.new_code_cell("""from pathlib import Path
import sys
import json
ROOT = Path.cwd().parent if Path.cwd().name == 'notebooks' else Path.cwd()
sys.path.insert(0, str(ROOT))
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import Image, display
RESULTS = ROOT / 'results'
""")

write("01_EDA.ipynb", [
    nbf.v4.new_markdown_cell("# ESS Battery Cycle Life — EDA\n\n다섯 가지 EDA 질문을 Batch 1·2·3에서 비교하고, 확인한 결과를 Feature 설계와 검증 전략으로 연결한다."),
    setup,
    nbf.v4.new_markdown_cell("## 1. Data Load / Structure"),
    nbf.v4.new_code_cell("summary = pd.read_csv(RESULTS/'tables/cycle_life_summary.csv')\nsummary"),
    nbf.v4.new_markdown_cell("## 2. Q1 — Cycle Life Distribution"),
    nbf.v4.new_code_cell("display(Image(filename=RESULTS/'figures/day1_eda01_cycle_life_by_batch.png'))"),
    nbf.v4.new_markdown_cell("Batch 2는 단수명 비중이 크고 Batch 3는 장수명 비중이 커서 Batch 1과 뚜렷한 분포 이동이 존재한다."),
    nbf.v4.new_markdown_cell("## 3. Q2 — Capacity Degradation"),
    nbf.v4.new_code_cell("display(Image(filename=RESULTS/'figures/day1_eda02_qd_degradation_by_batch.png'))\nevidence = json.loads((RESULTS/'tables/day1_batch_comparison.json').read_text())\npd.DataFrame({b: {'knee_median_cycle': v['knee_median_cycle'], 'knee_median_fraction': v['knee_median_fraction']} for b, v in evidence['batches'].items()}).T"),
    nbf.v4.new_markdown_cell("전체 수명 곡선에서 계산한 Knee 중앙값은 Batch 1 549, Batch 2 323, Batch 3 753.5 Cycle이다. 이는 열화 시점 차이를 설명하는 사후 지표이며 미래 정보를 사용하므로 모델 Feature에서 제외한다. 초기 QD 절대값보다 초기 변화량과 ΔQ(V)를 사용한다."),
    nbf.v4.new_markdown_cell("## 4. Q3 — ΔQ(V)"),
    nbf.v4.new_code_cell("display(Image(filename=RESULTS/'figures/day1_eda03_delta_q_by_batch.png'))\ncorr = pd.read_csv(RESULTS/'tables/feature_target_correlations.csv'); corr[corr.feature=='log_dq_var']"),
    nbf.v4.new_markdown_cell("## 5. Q4 — Charging Policy"),
    nbf.v4.new_code_cell("display(Image(filename=RESULTS/'figures/day1_eda04_charging_by_batch.png'))\nrows=[]\nfor batch, values in evidence['batches'].items():\n    top=max(values['charging_policy'], key=lambda x: x['n'])\n    rows.append({'batch': batch, **top})\npd.DataFrame(rows)"),
    nbf.v4.new_markdown_cell("표본이 가장 많은 대표 Protocol 평균은 Batch 1 1,182.0, Batch 2 448.5, Batch 3 1,074.4 Cycle이다. Batch 구성과 표본 수가 함께 다르므로 C-rate만의 인과효과로 해석하지 않는다."),
    nbf.v4.new_markdown_cell("## 6. Q5 — Correlation / Conclusions"),
    nbf.v4.new_code_cell("display(Image(filename=RESULTS/'figures/day1_eda05_correlation_strategy.png'))"),
    nbf.v4.new_markdown_cell("ΔQ 파생 변수끼리 다중공선성이 크므로 정규화 선형 모델을 주 후보로 비교하고, 외부 배치는 선택·튜닝에 사용하지 않는다."),
])

write("02_feature_engineering.ipynb", [
    nbf.v4.new_markdown_cell("# Feature Engineering\n\n모든 배치에 `src.features`의 동일한 파이프라인을 적용한다. 한 행은 한 셀이다."), setup,
    nbf.v4.new_markdown_cell("## Definitions\n\n`ΔQ100−10(V)`는 공통 전압 범위의 1,000점 grid로 보간한 뒤 point-wise 차이를 계산한다. `log_dq_var = log10(max(var(ΔQ), 1e-12))`이다."),
    nbf.v4.new_code_cell("from src.features import EPSILON, MODEL_FEATURES, parse_policy\nprint('variance epsilon:', EPSILON)\nprint('model features:', MODEL_FEATURES)"),
    nbf.v4.new_markdown_cell("## Feature datasets and quality checks"),
    nbf.v4.new_code_cell("""features = {b: pd.read_csv(RESULTS/f'feature_dataset_{b}.csv') for b in ('batch1','batch2','batch3')}
quality = {b: pd.read_csv(RESULTS/'tables'/f'quality_report_{b}.csv') for b in ('batch1','batch2','batch3')}
pd.DataFrame({b: {'rows': len(features[b]), 'valid': int(quality[b].valid_for_model.sum()), 'columns': len(features[b].columns)} for b in features}).T"""),
    nbf.v4.new_code_cell("features['batch1'].head()"),
    nbf.v4.new_markdown_cell("## Batch comparison"),
    nbf.v4.new_code_cell("display(Image(filename=RESULTS/'figures/batch_feature_distribution_shift.png'))"),
    nbf.v4.new_markdown_cell("## EDA에서 모델 입력으로\n\nKnee처럼 수명 종료 이후에 알 수 있는 값과 `cycle_life`는 입력에서 제외한다. 세 Batch에는 동일한 Feature 추출 함수를 적용하며, Batch 2·3는 고정 모델의 외부 평가에만 사용한다."),
    nbf.v4.new_code_cell("strategy = json.loads((RESULTS/'tables/day1_model_strategy.json').read_text())\nstrategy"),
])

write("03_modeling.ipynb", [
    nbf.v4.new_markdown_cell("# Modeling and External Evaluation\n\nBatch 1에서만 split, CV, 전처리 학습과 hyperparameter tuning을 수행한다. 타깃은 `log(cycle_life)`로 학습하고 MAPE는 cycle 단위로 역변환해 계산한다."), setup,
    nbf.v4.new_markdown_cell("## Model comparison"),
    nbf.v4.new_code_cell("comparison = pd.read_csv(RESULTS/'tables/model_comparison.csv'); comparison"),
    nbf.v4.new_markdown_cell("후보 모델은 EDA 가설에 따라 정했다. Linear Regression은 선형 기준, ElasticNet은 ΔQ Feature 간 다중공선성 대응, Gradient Boosting은 비선형 관계 비교 역할을 갖는다. ElasticNet은 CV MAPE 8.10%로 가장 낮았지만 충전 정책 Hold-out에서 20.58%로 악화됐다. Gradient Boosting은 CV 10.45%, Hold-out 8.48%였으며 새로운 충전 정책에서 가장 안정적인 결과를 보여 선택했다. 단일 Hold-out 결과가 절대적인 우위를 뜻하지는 않는다."),
    nbf.v4.new_markdown_cell("## Split audit — 같은 충전 정책의 중복 방지"),
    nbf.v4.new_code_cell("audit = pd.read_csv(RESULTS/'tables/day2_split_audit.csv')\ntrain_policy = set(audit.loc[audit.split=='Train (Batch 1)', 'charging_policy'])\nvalid_policy = set(audit.loc[audit.split=='Valid (Batch 1 Hold-out)', 'charging_policy'])\n{'train_cells': int((audit.split=='Train (Batch 1)').sum()), 'valid_cells': int((audit.split=='Valid (Batch 1 Hold-out)').sum()), 'policy_overlap': sorted(train_policy & valid_policy)}"),
    nbf.v4.new_markdown_cell("## Performance"),
    nbf.v4.new_code_cell("performance = pd.read_csv(RESULTS/'model_performance.csv'); performance"),
    nbf.v4.new_markdown_cell("## Batch 2 test and residuals"),
    nbf.v4.new_code_cell("display(Image(filename=RESULTS/'figures/test_batch2_actual_vs_pred.png')); display(Image(filename=RESULTS/'figures/test_batch2_residual.png'))"),
    nbf.v4.new_markdown_cell("## Batch 3 generalization"),
    nbf.v4.new_code_cell("display(Image(filename=RESULTS/'figures/test_batch3_actual_vs_pred.png')); display(Image(filename=RESULTS/'figures/test_batch3_residual.png'))"),
    nbf.v4.new_markdown_cell("## Error analysis"),
    nbf.v4.new_code_cell("summary = pd.read_csv(RESULTS/'tables/day2_error_analysis_summary.csv'); display(summary)\nerrors = pd.read_csv(RESULTS/'tables/error_analysis_batch2.csv'); errors[['cell_id','cycle_life','prediction','absolute_percentage_error','charging_policy','log_dq_var']].head(10)"),
    nbf.v4.new_markdown_cell("Batch 2의 큰 오류는 주로 실제 400–500 cycle대 셀을 과대예측한 경우다. 이는 Batch 1에 500 cycle 미만 표본이 없고 Batch 2의 단수명 비중이 76.5%인 외삽 문제와 연결된다."),
])
