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
ROOT = Path.cwd().parent if Path.cwd().name == 'notebooks' else Path.cwd()
sys.path.insert(0, str(ROOT))
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import Image, display
RESULTS = ROOT / 'results'
""")

write("01_EDA.ipynb", [
    nbf.v4.new_markdown_cell("# ESS Battery Cycle Life — EDA\n\nBatch 간 수명 분포, 초기 열화, ΔQ(V), 충전 정책과 상관 구조를 실제 실행 결과로 확인한다."),
    setup,
    nbf.v4.new_markdown_cell("## 1. Data Load / Structure"),
    nbf.v4.new_code_cell("summary = pd.read_csv(RESULTS/'tables/cycle_life_summary.csv')\nsummary"),
    nbf.v4.new_markdown_cell("## 2. Q1 — Cycle Life Distribution"),
    nbf.v4.new_code_cell("display(Image(filename=RESULTS/'figures/eda_cycle_life_hist.png')); display(Image(filename=RESULTS/'figures/eda_cycle_life_boxplot.png'))"),
    nbf.v4.new_markdown_cell("Batch 2는 단수명 비중이 크고 Batch 3는 장수명 비중이 커서 Batch 1과 뚜렷한 분포 이동이 존재한다."),
    nbf.v4.new_markdown_cell("## 3. Q2 — Capacity Degradation"),
    nbf.v4.new_code_cell("display(Image(filename=RESULTS/'figures/eda_degradation_curve.png'))"),
    nbf.v4.new_markdown_cell("초기 QD 절대값만으로는 셀 수명을 충분히 구분하기 어려워 전압 축의 미세 변화인 ΔQ(V)를 사용한다."),
    nbf.v4.new_markdown_cell("## 4. Q3 — ΔQ(V)"),
    nbf.v4.new_code_cell("display(Image(filename=RESULTS/'figures/eda_delta_q_curve.png')); display(Image(filename=RESULTS/'figures/eda_delta_q_vs_cycle_life.png'))\ncorr = pd.read_csv(RESULTS/'tables/feature_target_correlations.csv'); corr[corr.feature=='log_dq_var']"),
    nbf.v4.new_markdown_cell("## 5. Q4 — Charging Policy"),
    nbf.v4.new_code_cell("display(Image(filename=RESULTS/'figures/eda_charging_policy.png')); pd.read_csv(RESULTS/'tables/charging_policy_summary.csv').head(10)"),
    nbf.v4.new_markdown_cell("정책별 차이는 관찰적 연관이며 인과효과로 해석하지 않는다."),
    nbf.v4.new_markdown_cell("## 6. Q5 — Correlation / Conclusions"),
    nbf.v4.new_code_cell("display(Image(filename=RESULTS/'figures/eda_feature_target_corr.png')); display(Image(filename=RESULTS/'figures/eda_feature_corr_heatmap.png'))"),
    nbf.v4.new_markdown_cell("ΔQ 파생 변수끼리 다중공선성이 크므로 정규화 선형 모델을 주 후보로 비교하고, 외부 배치는 선택·튜닝에 사용하지 않는다."),
])

write("02_feature_engineering.ipynb", [
    nbf.v4.new_markdown_cell("# Feature Engineering\n\n모든 배치에 `src.features`의 동일한 파이프라인을 적용한다. 한 행은 한 셀이다."), setup,
    nbf.v4.new_markdown_cell("## Definitions\n\n`ΔQ100−10(V)`는 공통 전압 범위의 1,000점 grid로 보간한 뒤 point-wise 차이를 계산한다. `log_dq_var = log10(max(var(ΔQ), 1e-12))`이다."),
    nbf.v4.new_code_cell("from src.features import EPSILON, parse_policy\nprint('variance epsilon:', EPSILON)"),
    nbf.v4.new_markdown_cell("## Feature datasets and quality checks"),
    nbf.v4.new_code_cell("""features = {b: pd.read_csv(RESULTS/f'feature_dataset_{b}.csv') for b in ('batch1','batch2','batch3')}
quality = {b: pd.read_csv(RESULTS/'tables'/f'quality_report_{b}.csv') for b in ('batch1','batch2','batch3')}
pd.DataFrame({b: {'rows': len(features[b]), 'valid': int(quality[b].valid_for_model.sum()), 'columns': len(features[b].columns)} for b in features}).T"""),
    nbf.v4.new_code_cell("features['batch1'].head()"),
    nbf.v4.new_markdown_cell("## Batch comparison"),
    nbf.v4.new_code_cell("display(Image(filename=RESULTS/'figures/batch_feature_distribution_shift.png'))"),
])

write("03_modeling.ipynb", [
    nbf.v4.new_markdown_cell("# Modeling and External Evaluation\n\nBatch 1에서만 split, CV, 전처리 학습과 hyperparameter tuning을 수행한다. 타깃은 `log(cycle_life)`로 학습하고 MAPE는 cycle 단위로 역변환해 계산한다."), setup,
    nbf.v4.new_markdown_cell("## Model comparison"),
    nbf.v4.new_code_cell("comparison = pd.read_csv(RESULTS/'tables/model_comparison.csv'); comparison"),
    nbf.v4.new_markdown_cell("공식 제외 규칙 반영 후 ElasticNet은 CV 평균이 낮지만 unseen-policy hold-out에서 크게 악화됐다. 제한된 깊이의 Gradient Boosting이 hold-out 일반화와 비선형성 대응에서 우세해 최종 선택됐다."),
    nbf.v4.new_markdown_cell("## Performance"),
    nbf.v4.new_code_cell("performance = pd.read_csv(RESULTS/'model_performance.csv'); performance"),
    nbf.v4.new_markdown_cell("## Batch 2 test and residuals"),
    nbf.v4.new_code_cell("display(Image(filename=RESULTS/'figures/test_batch2_actual_vs_pred.png')); display(Image(filename=RESULTS/'figures/test_batch2_residual.png'))"),
    nbf.v4.new_markdown_cell("## Batch 3 generalization"),
    nbf.v4.new_code_cell("display(Image(filename=RESULTS/'figures/test_batch3_actual_vs_pred.png')); display(Image(filename=RESULTS/'figures/test_batch3_residual.png'))"),
    nbf.v4.new_markdown_cell("## Error analysis"),
    nbf.v4.new_code_cell("errors = pd.read_csv(RESULTS/'tables/error_analysis_batch2.csv'); errors[['cell_id','cycle_life','prediction','absolute_percentage_error','charging_policy','log_dq_var']].head(10)"),
    nbf.v4.new_markdown_cell("Batch 2의 큰 오류는 주로 실제 400–500 cycle대 셀을 과대예측한 경우다. 이는 Batch 1에 500 cycle 미만 표본이 없고 Batch 2의 단수명 비중이 76.5%인 외삽 문제와 연결된다."),
])
