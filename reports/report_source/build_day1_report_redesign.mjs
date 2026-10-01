import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const workspaceDir = path.resolve(process.cwd());
const SKILL_DIR = "/Users/nak/.codex/plugins/cache/openai-primary-runtime/presentations/26.905.11957/skills/presentations";
const RUNTIME_PYTHON = "/Users/nak/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3";
const buildDir = path.join(workspaceDir, ".report-build-redesign");
const finalPath = path.join(workspaceDir, "reports/report_source/DS-MINI-Design-울산_1반-김낙근-redesign.pptx");
const figures = path.join(workspaceDir, "results/figures");
await fs.mkdir(buildDir, { recursive: true });
await fs.mkdir(path.dirname(finalPath), { recursive: true });

const { finalizePresentation } = await import(pathToFileURL(path.join(SKILL_DIR, "container_tools/artifact_tool_utils.mjs")).href);
const deck = Presentation.create({ slideSize: { width: 1280, height: 720 } });
const FONT = "Pretendard";
const C = {
  white: "#FFFFFF", paper: "#F7F9FB", ink: "#1F2933", gray: "#5F6B76",
  line: "#D9E1E8", navy: "#17324D", teal: "#008C85", paleTeal: "#E8F5F3",
  paleNavy: "#EEF3F8", orange: "#E97827", red: "#C94C4C", paleWarn: "#FFF4E8",
};

function shape(slide, x, y, w, h, fill = C.white, geometry = "rect", line = C.line) {
  return slide.shapes.add({ geometry, position: { left: x, top: y, width: w, height: h }, fill, line: { fill: line, width: line === "none" ? 0 : 1 } });
}
function txt(slide, value, x, y, w, h, size = 20, color = C.ink, bold = false, align = "left") {
  const s = slide.shapes.add({ geometry: "textbox", position: { left: x, top: y, width: w, height: h }, fill: "none", line: { fill: "none", width: 0 } });
  s.text = value;
  s.text.style = { typeface: FONT, fontSize: size, color, bold, alignment: align, autoFit: "shrinkText", verticalAlignment: "middle" };
  return s;
}
function page(slide, n, section) {
  txt(slide, section, 64, 28, 500, 24, 13, C.teal, true);
  txt(slide, String(n).padStart(2, "0"), 1170, 678, 40, 18, 11, "#94A0AA", false, "right");
  slide.shapes.add({ geometry: "rect", position: { left: 64, top: 660, width: 1152, height: 1 }, fill: C.line, line: { fill: C.line, width: 0 } });
}
function heading(slide, title, subtitle, n, section) {
  page(slide, n, section);
  txt(slide, title, 64, 58, 1150, 56, 32, C.navy, true);
  txt(slide, subtitle, 64, 116, 1120, 38, 18, C.gray, false);
}
async function img(slide, name, x, y, w, h, alt) {
  shape(slide, x - 6, y - 6, w + 12, h + 12, C.white, "rect", C.line);
  slide.images.add({ blob: await fs.readFile(path.join(figures, name)), contentType: "image/png", alt, fit: "contain", position: { left: x, top: y, width: w, height: h } });
}
function info(slide, label, body, x, y, w, h, tone = "teal") {
  const fill = tone === "warn" ? C.paleWarn : tone === "navy" ? C.paleNavy : C.paleTeal;
  const color = tone === "warn" ? C.orange : tone === "navy" ? C.navy : C.teal;
  shape(slide, x, y, w, h, fill, "roundRect", "none");
  txt(slide, label, x + 18, y + 12, w - 36, 24, 14, color, true);
  txt(slide, body, x + 18, y + 38, w - 36, h - 48, 17, C.ink, false);
}
function note(slide, value) { slide.speakerNotes.textFrame.setText(value); }

// 1. Executive setup
{
  const s = deck.slides.add(); s.background.fill = C.white; page(s, 1, "ESS 배터리 수명 예측");
  txt(s, "초기 열화 신호로 ESS 배터리 수명을 예측할 수 있는가?", 64, 78, 1050, 82, 42, C.navy, true);
  txt(s, "MIT-Stanford 배터리 데이터셋 · 초기 100 Cycle · Cell 단위 회귀 분석", 66, 168, 950, 34, 20, C.gray, false);
  shape(s, 64, 238, 1152, 2, C.teal, "rect", "none");
  txt(s, "분석 목표", 64, 272, 180, 34, 18, C.teal, true);
  txt(s, "수명 종료까지 기다리지 않고 초기 충방전 신호로 장기 Cycle Life를 추정한다", 64, 312, 690, 64, 28, C.ink, true);
  info(s, "입력", "Cycle 1-100의 QD, Qdlin, IR, 온도, 충전시간과 충전 정책", 64, 420, 350, 150, "navy");
  info(s, "목표값", "cycle_life\nCell이 EOL에 도달하기까지의 총 Cycle 수", 442, 420, 350, 150, "teal");
  info(s, "검증", "Batch 1에서 모델 선택\nBatch 2와 3은 외부 일반화 평가", 820, 420, 396, 150, "warn");
  txt(s, "ESS 적용 관점", 64, 600, 170, 28, 15, C.gray, true);
  txt(s, "교체 계획과 예방 정비를 위해 조기 위험 Cell을 선별할 수 있는지 검증", 224, 594, 900, 38, 20, C.navy, true);
  note(s, "Source: repository README and supplied MIT-Stanford MAT files.");
}

// 2. Distribution
{
  const s = deck.slides.add(); s.background.fill = C.white;
  heading(s, "Batch별 수명 분포가 크게 다르다", "분석 질문  ·  Batch 1에서 학습한 관계가 Batch 2와 3에서도 유지되는가?", 2, "EDA 01  ·  목표값 분포");
  await img(s, "eda_cycle_life_hist.png", 64, 182, 500, 230, "Cycle life histogram by batch");
  await img(s, "eda_cycle_life_boxplot.png", 64, 440, 500, 184, "Cycle life boxplot by batch");
  info(s, "핵심 발견", "중앙값은 Batch 1 842.0, Batch 2 468.5, Batch 3 964.5 cycles다. Batch 2의 76.5%가 500 cycle 미만이다.", 600, 176, 580, 130, "warn");
  info(s, "ESS 시사점", "실제 ESS에서도 운전환경이나 사용조건이 달라지면 학습 데이터와 현장 데이터 사이에 분포 이동이 발생할 수 있다.", 600, 326, 580, 130, "navy");
  info(s, "모델링 결정", "Batch 1에서만 모델을 선택하고 튜닝한다. Batch 2는 단수명 영역 외부 테스트, Batch 3는 장수명 영역 추가 외부 테스트로 사용한다.", 600, 476, 580, 148, "teal");
  note(s, "Source: results/tables/cycle_life_summary.csv and cycle-life figures.");
}

// 3. Capacity degradation
{
  const s = deck.slides.add(); s.background.fill = C.white;
  heading(s, "초기 용량 절대값만으로 장기 수명을 구분하기 어렵다", "분석 질문  ·  장수명 Cell과 단수명 Cell은 초기 열화 구간에서 어떻게 다른가?", 3, "EDA 02  ·  용량 열화");
  await img(s, "eda_degradation_curve.png", 64, 184, 650, 390, "Representative capacity degradation curves");
  txt(s, "분석 근거", 64, 594, 90, 24, 14, C.gray, true);
  txt(s, "qd_10 vs cycle_life  ·  Pearson r = 0.101", 150, 588, 500, 34, 19, C.navy, true);
  info(s, "핵심 발견", "초기 QD 곡선은 상당 부분 겹치며 특정 Cycle의 용량 절대값과 수명의 관계가 약하다.", 750, 184, 430, 116, "warn");
  info(s, "ESS 시사점", "한 시점의 용량만으로 장기 수명을 판단하기보다 초기 운전 구간의 열화 변화 추세를 추적해야 한다.", 750, 320, 430, 128, "navy");
  info(s, "모델링 결정", "qd_change, qd_slope와 전압별 곡선 변화인 ΔQ(V)를 생성한다.", 750, 468, 430, 106, "teal");
  txt(s, "다음 분석", 750, 596, 90, 22, 14, C.gray, true);
  txt(s, "초기 10-100 Cycle의 미세한 Curve 변화는 수명을 설명하는가?", 840, 588, 340, 38, 17, C.teal, true);
  note(s, "Source: results/figures/eda_degradation_curve.png and feature_target_correlations.csv.");
}

// 4. Delta Q
{
  const s = deck.slides.add(); s.background.fill = C.white;
  heading(s, "ΔQ(V)는 초기 수명 구간에서 장기 수명 위험을 구분한다", "분석 질문  ·  Cycle 10과 100 사이의 방전곡선 변화가 Cycle Life와 연결되는가?", 4, "EDA 03  ·  ΔQ(V)");
  shape(s, 64, 174, 1116, 64, C.paleNavy, "roundRect", "none");
  txt(s, "ΔQ₁₀₀₋₁₀(V) = Q₁₀₀(V) - Q₁₀(V)", 86, 184, 470, 42, 26, C.navy, true);
  txt(s, "QD 단일값 차이가 아니라 공통 전압 격자에서 계산한 Qdlin 곡선의 지점별 차이", 558, 184, 596, 42, 16, C.gray, false);
  await img(s, "eda_delta_q_curve.png", 64, 268, 470, 256, "Representative Delta Q curves");
  await img(s, "eda_delta_q_vs_cycle_life.png", 552, 268, 430, 256, "Delta Q variance correlation");
  shape(s, 1000, 268, 180, 256, C.paleWarn, "roundRect", "none");
  txt(s, "Pearson", 1020, 300, 140, 24, 14, C.gray, true, "center");
  txt(s, "-0.886", 1010, 326, 160, 54, 38, C.red, true, "center");
  txt(s, "Spearman", 1020, 404, 140, 24, 14, C.gray, true, "center");
  txt(s, "-0.880", 1010, 430, 160, 54, 38, C.orange, true, "center");
  info(s, "ESS 시사점", "배터리 수명 종료까지 기다리지 않고 초기 수명 데이터만으로 장기 열화 위험 Cell을 조기에 선별할 가능성을 보여준다.", 64, 548, 720, 88, "navy");
  info(s, "모델링 결정", "log_dq_var를 핵심 Feature 후보로 선정한다.", 806, 548, 374, 88, "teal");
  note(s, "Source: results/figures/eda_delta_q_curve.png, eda_delta_q_vs_cycle_life.png, and actual Batch 1 correlations.");
}

// 5. Charging policy
{
  const s = deck.slides.add(); s.background.fill = C.white;
  heading(s, "수명 예측에는 Cell 상태와 충전 운전조건이 함께 필요하다", "분석 질문  ·  충전 Protocol에 따라 Cycle Life 분포가 달라지는가?", 5, "EDA 04  ·  충전 정책");
  await img(s, "eda_charging_policy.png", 64, 186, 670, 376, "Charging policy versus cycle life");
  txt(s, "충전 정책 분해", 64, 586, 120, 24, 14, C.gray, true);
  txt(s, "4.8C(80%)-3.6C  →  first_c_rate 4.8  /  switch_soc 0.8  /  second_c_rate 3.6", 184, 578, 690, 38, 18, C.navy, true);
  info(s, "핵심 발견", "first_c_rate와 Cycle Life 사이에 Pearson r = -0.577의 연관이 관찰됐다.", 770, 186, 410, 104, "warn");
  info(s, "ESS 시사점", "실제 ESS 수명 예측은 열화 상태뿐 아니라 충전 운전조건도 함께 고려해야 한다. 상관관계를 인과관계로 확대 해석하지 않는다.", 770, 310, 410, 144, "navy");
  info(s, "모델링 결정", "C-rate Feature를 포함하고 charging_policy를 고려한 그룹 분할을 적용한다.", 770, 474, 410, 112, "teal");
  note(s, "Source: results/figures/eda_charging_policy.png and feature_target_correlations.csv.");
}

// 6. Feature correlation
{
  const s = deck.slides.add(); s.background.fill = C.white;
  heading(s, "강한 ΔQ 신호에는 중복 정보도 함께 존재한다", "분석 질문  ·  어떤 초기 신호가 수명과 관련 있고, Feature끼리는 얼마나 중복되는가?", 6, "EDA 05  ·  Feature 상관관계");
  await img(s, "eda_feature_target_corr.png", 64, 186, 410, 350, "Feature target correlation chart");
  await img(s, "eda_feature_corr_heatmap.png", 492, 186, 410, 350, "Feature correlation heatmap");
  shape(s, 64, 560, 838, 68, C.paleNavy, "roundRect", "none");
  txt(s, "dq_std -0.896   ·   log_dq_var -0.886   ·   dq_range -0.884   ·   dq_min +0.883", 82, 574, 802, 40, 19, C.navy, true, "center");
  info(s, "핵심 발견", "ΔQ Feature들은 Cycle Life와 높은 상관을 보이지만 서로도 강하게 연관된다.", 930, 186, 250, 112, "warn");
  info(s, "ESS 시사점", "유사한 열화 신호를 무작정 늘리기보다 대표 지표를 선택해 안정적인 예측 모델을 구성해야 한다.", 930, 318, 250, 144, "navy");
  info(s, "모델링 결정", "Feature Selection 또는 Regularization을 적용한다.", 930, 482, 250, 104, "teal");
  note(s, "Source: results/figures/eda_feature_target_corr.png and eda_feature_corr_heatmap.png.");
}

// 7. Feature engineering table
{
  const s = deck.slides.add(); s.background.fill = C.white;
  heading(s, "EDA 결과를 Cell-level Feature로 구조화한다", "한 Cell을 한 행으로 만들고 세 Batch에 동일한 Feature 생성 절차를 적용", 7, "FEATURE 설계");
  const cols = [64, 410, 790, 1216];
  shape(s, 64, 178, 1152, 54, C.navy, "rect", "none");
  txt(s, "EDA 관찰 결과", cols[0] + 18, 184, 300, 40, 17, C.white, true);
  txt(s, "해석", cols[1] + 18, 184, 330, 40, 17, C.white, true);
  txt(s, "생성 Feature", cols[2] + 18, 184, 390, 40, 17, C.white, true);
  const rows = [
    ["초기 QD 절대값의 구분력이 낮음", "변화 속도와 누적 변화를 표현", "qd_change · qd_slope"],
    ["ΔQ(V)와 수명의 관계가 강함", "Early-life 열화 형태를 요약", "log_dq_var · dq_min · dq_range"],
    ["IR과 온도는 보조 신호", "전기적·열적 상태 변화를 포함", "ir_change · tavg_mean · tmax_max"],
    ["충전 Protocol별 분포 차이", "운전조건을 Cell 상태와 함께 반영", "first_c_rate · switch_soc · second_c_rate"],
    ["ΔQ Feature끼리 중복", "대표 Feature 선택과 규제가 필요", "Feature Selection · Regularization"],
  ];
  rows.forEach((r, i) => {
    const y = 232 + i * 74;
    shape(s, 64, y, 1152, 74, i % 2 ? C.white : C.paper, "rect", C.line);
    txt(s, r[0], cols[0] + 18, y + 10, 310, 54, 18, C.ink, i < 2);
    txt(s, r[1], cols[1] + 18, y + 10, 340, 54, 17, C.gray, false);
    txt(s, r[2], cols[2] + 18, y + 10, 390, 54, 17, i < 2 ? C.teal : C.navy, true);
  });
  shape(s, 64, 616, 1152, 38, C.paleTeal, "roundRect", "none");
  txt(s, "출력 구조", 82, 622, 150, 26, 14, C.teal, true);
  txt(s, "cell_id · cycle_life · log_dq_var · qd_slope · ir_change · temperature · C-rate", 232, 622, 950, 26, 16, C.ink, true);
  note(s, "Source: src/features.py and results/feature_dataset_batch1.csv.");
}

// 8. Modeling and validation
{
  const s = deck.slides.add(); s.background.fill = C.white;
  heading(s, "소규모 정형 데이터셋에 맞는 모델과 검증 구조", "Feature와 하이퍼파라미터는 Batch 1에서만 결정하고 테스트 Batch는 최종 평가에만 사용", 8, "모델링 전략");
  txt(s, "모델 후보", 64, 174, 240, 28, 16, C.teal, true);
  const models = [
    ["Linear Regression", "기준 모델", "선형 관계의 기준 성능"],
    ["ElasticNet", "주요 후보", "다중공선성과 정규화"],
    ["Gradient Boosting", "비선형 비교", "비선형 관계, 제한된 복잡도"],
  ];
  models.forEach((m, i) => {
    const x = 64 + i * 258;
    shape(s, x, 214, 236, 160, i === 1 ? C.paleTeal : C.paper, "roundRect", i === 1 ? C.teal : C.line);
    txt(s, m[0], x + 18, 230, 200, 44, 21, C.navy, true);
    txt(s, m[1], x + 18, 280, 200, 24, 14, i === 1 ? C.teal : C.gray, true);
    txt(s, m[2], x + 18, 310, 200, 46, 16, C.gray, false);
  });
  info(s, "딥러닝보다 전통 ML을 우선하는 이유", "약 100개 Cell의 소규모 정형 데이터셋이다. 생성 Feature 기반 분석에서는 고복잡도 모델의 과적합 위험이 높다.", 64, 398, 752, 104, "navy");
  txt(s, "검증 구조", 850, 174, 260, 28, 16, C.teal, true);
  const batches = [
    ["BATCH 1", "학습 + 검증", "모델 선택 · 스케일링 · 튜닝", C.paleTeal, C.teal],
    ["BATCH 2", "외부 테스트", "단수명 영역 · 선택에 사용하지 않음", C.paleWarn, C.orange],
    ["BATCH 3", "추가 외부 테스트", "장수명 영역 · 추가 일반화 검증", C.paleNavy, C.navy],
  ];
  batches.forEach((b, i) => {
    const y = 214 + i * 112;
    shape(s, 850, y, 330, 94, b[3], "roundRect", "none");
    txt(s, b[0], 868, y + 12, 86, 24, 14, b[4], true);
    txt(s, b[1], 960, y + 10, 202, 28, 17, C.ink, true);
    txt(s, b[2], 868, y + 44, 294, 36, 15, C.gray, false);
  });
  shape(s, 64, 530, 752, 2, C.line, "rect", "none");
  txt(s, "소규모 정형 데이터셋", 64, 552, 220, 30, 18, C.navy, true);
  txt(s, "전통 ML 우선", 320, 552, 170, 30, 18, C.teal, true);
  txt(s, "검증 결과로 최종 선택", 520, 552, 296, 30, 18, C.navy, true);
  txt(s, "목표값  log(cycle_life)  ·  평가지표  역변환 후 원 Cycle 단위 MAPE", 64, 606, 752, 30, 17, C.gray, false);
  note(s, "Source: src/train.py and README modeling protocol. Test batches are excluded from selection and tuning.");
}

// 9. Conclusion
{
  const s = deck.slides.add(); s.background.fill = C.white;
  heading(s, "ESS 수명 예측을 위한 네 가지 핵심 시사점", "EDA 결과를 현장 적용 관점과 모델 검증 전략으로 연결", 9, "결론");
  const items = [
    ["01", "조기 예측", "초기 Cycle 데이터로 장기 배터리 수명 위험을 조기에 구분할 가능성", C.paleTeal, C.teal],
    ["02", "절대값보다 추세", "단일 용량값보다 초기 열화 변화 패턴을 추적하는 것이 중요", C.paleNavy, C.navy],
    ["03", "운전조건의 중요성", "배터리 상태와 충전 운전조건을 함께 고려해야 함", C.paleTeal, C.teal],
    ["04", "일반화 검증의 중요성", "다른 운전조건에서도 유지되는 외부 Batch 성능을 검증해야 함", C.paleWarn, C.orange],
  ];
  items.forEach((it, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = 64 + col * 570, y = 180 + row * 184;
    shape(s, x, y, 542, 154, it[3], "roundRect", "none");
    txt(s, it[0], x + 22, y + 18, 54, 34, 16, it[4], true);
    txt(s, it[1], x + 82, y + 16, 420, 38, 23, C.navy, true);
    txt(s, it[2], x + 82, y + 62, 420, 68, 18, C.ink, false);
  });
  shape(s, 64, 570, 1112, 68, C.navy, "roundRect", "none");
  txt(s, "초기 열화 패턴과 운전조건을 결합한 Cell 단위 Feature를 구축하고, 외부 Batch 일반화 성능을 중심으로 수명 예측 모델을 검증한다.", 90, 580, 1060, 48, 21, C.white, true, "center");
  note(s, "Source: synthesis of EDA findings and the requested ESS implications. No new quantitative claims added.");
}

const candidatePath = path.join(buildDir, "candidate-redesign.pptx");
await (await PresentationFile.exportPptx(deck)).save(candidatePath);
await finalizePresentation({
  workspaceDir,
  candidatePath,
  finalPath,
  pythonExecutable: RUNTIME_PYTHON,
  integrityValidatorPath: path.join(SKILL_DIR, "container_tools/inspect_presentation_package_integrity.py"),
  layoutValidatorPath: path.join(SKILL_DIR, "container_tools/inspect_presentation_layout_geometry.py"),
  layoutArgs: ["--expected-slide-size-emu", "12192000,6858000", "--validate-heading-fit"],
  explicitTotalSlideCount: 9,
  requiredNativeTableOwnerSlides: [],
  requiredNativeChartOwnerSlides: [],
  fontPolicy: { basis: "design", families: [FONT] },
  verifyArtifactToolImport: true,
  receiptPath: path.join(buildDir, "redesign.validation.json"),
});
console.log(finalPath);
