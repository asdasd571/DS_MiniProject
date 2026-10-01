import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const workspaceDir = path.resolve(process.cwd());
const SKILL_DIR = "/Users/nak/.codex/plugins/cache/openai-primary-runtime/presentations/26.905.11957/skills/presentations";
const RUNTIME_PYTHON = "/Users/nak/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3";
const buildDir = path.join(workspaceDir, ".report-build");
const finalPath = path.join(workspaceDir, "reports/report_source/DS-MINI-Design-울산_1반-김낙근.pptx");
const figures = path.join(workspaceDir, "results/figures");
await fs.mkdir(buildDir, { recursive: true });
await fs.mkdir(path.dirname(finalPath), { recursive: true });

const { finalizePresentation } = await import(pathToFileURL(path.join(SKILL_DIR, "container_tools/artifact_tool_utils.mjs")).href);
const p = Presentation.create({ slideSize: { width: 1280, height: 720 } });
const FONT = "AppleGothic";
const C = { bg: "#0B1220", panel: "#121D2F", text: "#F4F7FB", muted: "#A9B7C9", cyan: "#49D6C6", blue: "#4F8CFF", amber: "#FFCB66", red: "#FF6B6B", line: "#263850" };

function box(slide, x, y, w, h, fill = C.panel, radius = "roundRect") {
  return slide.shapes.add({ geometry: radius, position: { left: x, top: y, width: w, height: h }, fill, line: { fill: "none", width: 0 } });
}
function text(slide, value, x, y, w, h, size = 22, color = C.text, bold = false, align = "left") {
  const s = slide.shapes.add({ geometry: "textbox", position: { left: x, top: y, width: w, height: h }, fill: "none", line: { fill: "none", width: 0 } });
  s.text = value;
  s.text.style = { typeface: FONT, fontSize: size, color, bold, alignment: align, autoFit: "shrinkText", verticalAlignment: "middle" };
  return s;
}
function title(slide, value, kicker) {
  if (kicker) text(slide, kicker, 64, 30, 420, 28, 15, C.cyan, true);
  text(slide, value, 64, 58, 1140, 62, 35, C.text, true);
  slide.shapes.add({ geometry: "line", position: { left: 64, top: 128, width: 1152, height: 0 }, fill: "none", line: { fill: C.line, width: 2 } });
}
async function image(slide, filename, x, y, w, h, alt) {
  slide.images.add({ blob: await fs.readFile(path.join(figures, filename)), contentType: "image/png", alt, fit: "contain", position: { left: x, top: y, width: w, height: h } });
}
function addFooter(slide, page) {
  text(slide, `DAY1 MODEL STRATEGY  /  ${String(page).padStart(2, "0")}`, 64, 684, 1152, 20, 12, "#71839A", false, "right");
}
function addSlide() { const s = p.slides.add(); s.background.fill = C.bg; return s; }
function note(slide, source) { slide.speakerNotes.textFrame.setText(`Source: ${source}`); }

// 1. Cover and input
{
  const s = addSlide();
  text(s, "ESS 배터리 수명 예측", 72, 82, 780, 80, 52, C.text, true);
  text(s, "초기 100 Cycle의 미세한 열화 신호로 전체 Battery Life를 예측한다", 74, 168, 850, 64, 25, C.cyan, true);
  box(s, 72, 278, 720, 272, C.panel);
  text(s, "INPUT", 104, 302, 180, 34, 16, C.amber, true);
  text(s, "Dataset  MIT-Stanford Battery Dataset\nTrain  Batch 1\nTest  Batch 2\nAdditional Test  Batch 3\nTarget  cycle_life", 104, 342, 620, 180, 23, C.text, false);
  box(s, 850, 100, 340, 450, "#11283A");
  text(s, "평가 질문", 884, 128, 260, 38, 19, C.cyan, true);
  text(s, "왜 초기 100 Cycle인가?\n\nX와 Y는 무엇인가?\n\n어떤 입력 변수를 만드는가?\n\nBatch별 역할은 무엇인가?", 884, 182, 254, 300, 21, C.text, false);
  text(s, "교체 계획 · Predictive Maintenance · Battery Health Management", 74, 592, 1110, 46, 19, C.muted, false);
  addFooter(s, 1); note(s, "Severson et al. (2019); repository results generated from the supplied MAT files.");
}

// 2. Target distribution
{
  const s = addSlide(); title(s, "ISSUE 1. Batch별 Cycle Life 분포는 동일한가?", "TARGET DISTRIBUTION");
  text(s, "왜", 66, 154, 70, 30, 16, C.cyan, true);
  text(s, "학습 Batch와 외부 Batch의 일반화 난이도를 먼저 확인", 134, 150, 430, 42, 19, C.text, true);
  text(s, "발견", 66, 212, 70, 30, 16, C.amber, true);
  text(s, "Batch 1 median 842.0 cycles\nBatch 2 median 468.5 cycles\nBatch 3 median 964.5 cycles", 134, 208, 390, 110, 22, C.text, false);
  box(s, 64, 350, 460, 218, "#10243A");
  text(s, "76.5%", 92, 372, 180, 62, 42, C.red, true);
  text(s, "Batch 2의 500 cycle 미만 비율\nBatch 1에는 해당 표본이 없다", 92, 438, 374, 84, 20, C.text, false);
  text(s, "모델링 시사점\nBatch 2는 단수명 외삽 Test, Batch 3는 장수명 방향의 추가 일반화 Test로 사용", 66, 586, 500, 72, 18, C.muted, false);
  await image(s, "eda_cycle_life_hist.png", 560, 150, 650, 248, "Batch별 cycle life histogram");
  await image(s, "eda_cycle_life_boxplot.png", 650, 420, 470, 222, "Batch별 cycle life boxplot");
  addFooter(s, 2); note(s, "Source: results/tables/cycle_life_summary.csv and results/figures/eda_cycle_life_*.png");
}

// 3. Capacity degradation
{
  const s = addSlide(); title(s, "ISSUE 2. 장수명 Cell과 단수명 Cell의 열화 차이", "CAPACITY DEGRADATION");
  text(s, "왜 확인했는가", 68, 158, 260, 32, 17, C.cyan, true);
  text(s, "초기 Capacity 절대값만으로 수명을 구분할 수 있는지 확인", 68, 194, 430, 58, 20, C.text, false);
  text(s, "무엇을 발견했는가", 68, 282, 280, 32, 17, C.amber, true);
  text(s, "초기 QD 곡선은 상당 부분 겹친다\nqd_10과 cycle_life의 Pearson r = 0.101", 68, 320, 430, 74, 21, C.text, true);
  box(s, 66, 452, 438, 126, "#10243A");
  text(s, "절대값보다 변화 형태가 필요하다", 92, 468, 386, 38, 23, C.cyan, true);
  text(s, "qd_change · qd_slope · ΔQ(V)", 92, 514, 380, 34, 19, C.text, false);
  text(s, "다음 질문  초기 100 Cycle의 미세한 Curve 변화에는 차이가 있는가?", 68, 612, 1030, 40, 20, C.muted, true);
  await image(s, "eda_degradation_curve.png", 530, 160, 690, 420, "대표 셀의 capacity degradation curves");
  addFooter(s, 3); note(s, "Source: results/figures/eda_degradation_curve.png and results/tables/feature_target_correlations.csv");
}

// 4. Delta Q
{
  const s = addSlide(); title(s, "ISSUE 3. 초기 100 Cycle에서 장·단수명의 차이를 찾을 수 있는가?", "DELTA Q(V)");
  box(s, 66, 145, 450, 102, "#10243A");
  text(s, "ΔQ₁₀₀₋₁₀(V) = Q₁₀₀(V) - Q₁₀(V)", 82, 158, 418, 48, 28, C.cyan, true, "center");
  text(s, "QD scalar 차이가 아니라 Qdlin curve의 point-wise difference", 86, 208, 410, 26, 14, C.muted, false, "center");
  text(s, "Cycle 10과 100을 공통 전압 구간의 1,000점 grid로 보간", 68, 270, 442, 58, 19, C.text, false);
  text(s, "Pearson", 70, 366, 160, 28, 15, C.muted, true);
  text(s, "-0.886", 68, 394, 220, 64, 45, C.red, true);
  text(s, "Spearman", 290, 366, 160, 28, 15, C.muted, true);
  text(s, "-0.880", 286, 394, 220, 64, 45, C.amber, true);
  text(s, "Modeling 시사점", 68, 500, 250, 30, 17, C.cyan, true);
  text(s, "log_dq_var를 핵심 Feature 후보로 선정", 68, 538, 430, 54, 21, C.text, true);
  await image(s, "eda_delta_q_curve.png", 540, 150, 660, 240, "대표 Delta Q curves");
  await image(s, "eda_delta_q_vs_cycle_life.png", 590, 404, 570, 248, "log Delta Q variance versus cycle life");
  addFooter(s, 4); note(s, "Source: results/figures/eda_delta_q_curve.png, eda_delta_q_vs_cycle_life.png, and feature_target_correlations.csv");
}

// 5. Charging policy
{
  const s = addSlide(); title(s, "ISSUE 4. 충전 조건에 따라 Cycle Life가 달라지는가?", "CHARGING POLICY");
  text(s, "정책 문자열을 수치로 분해", 68, 158, 410, 34, 18, C.cyan, true);
  text(s, "4.8C(80%)-3.6C", 68, 208, 370, 46, 29, C.text, true);
  text(s, "first_c_rate = 4.8\nswitch_soc = 0.8\nsecond_c_rate = 3.6", 68, 266, 360, 112, 21, C.text, false);
  box(s, 68, 410, 396, 118, "#10243A");
  text(s, "first_c_rate vs life", 92, 424, 320, 28, 16, C.muted, true);
  text(s, "Pearson r = -0.577", 92, 460, 330, 46, 29, C.amber, true);
  text(s, "관찰된 연관이며 인과관계로 해석하지 않는다", 68, 554, 420, 56, 18, C.muted, false);
  text(s, "모델링  C-rate Feature 포함 · charging_policy 기준 Group split", 68, 620, 600, 34, 19, C.cyan, true);
  await image(s, "eda_charging_policy.png", 500, 162, 710, 420, "Charging policy cycle life boxplot");
  addFooter(s, 5); note(s, "Source: results/figures/eda_charging_policy.png and results/tables/feature_target_correlations.csv");
}

// 6. Correlation
{
  const s = addSlide(); title(s, "ISSUE 5. 어떤 초기 신호가 Battery Life와 관련 있는가?", "FEATURE CORRELATION");
  text(s, "Target과 강한 관계", 68, 156, 300, 30, 17, C.cyan, true);
  text(s, "dq_std  -0.896\nlog_dq_var  -0.886\ndq_range  -0.884\ndq_min  +0.883", 68, 198, 330, 150, 23, C.text, true);
  text(s, "동시에 ΔQ 파생 Feature끼리 높은 상관이 존재", 68, 388, 360, 58, 20, C.amber, true);
  box(s, 68, 480, 360, 114, "#10243A");
  text(s, "전략", 90, 494, 80, 24, 15, C.muted, true);
  text(s, "Feature Selection 또는 Regularization", 90, 524, 310, 50, 21, C.cyan, true);
  await image(s, "eda_feature_target_corr.png", 450, 152, 370, 500, "Feature target correlation bar chart");
  await image(s, "eda_feature_corr_heatmap.png", 820, 152, 390, 500, "Feature correlation heatmap");
  addFooter(s, 6); note(s, "Source: results/figures/eda_feature_target_corr.png and eda_feature_corr_heatmap.png");
}

// 7. Feature strategy
{
  const s = addSlide(); title(s, "EDA Observation과 Cell-level Feature 설계", "FEATURE ENGINEERING");
  const rows = [
    ["초기 QD 절대값의 구분력 제한", "qd_change · qd_slope"],
    ["ΔQ(V)와 수명의 강한 관계", "log_dq_var · dq_min · dq_range"],
    ["IR 변화의 보조 신호", "ir_10 · ir_change"],
    ["온도와 충전시간의 차이", "tavg_mean · tmax_max · charge_time_mean"],
    ["충전 Protocol별 분포 차이", "first_c_rate · switch_soc · second_c_rate"],
  ];
  text(s, "EDA에서 발견한 사실", 84, 160, 470, 38, 18, C.cyan, true);
  text(s, "모델에 반영한 Feature", 650, 160, 470, 38, 18, C.cyan, true);
  rows.forEach((r, i) => {
    const y = 208 + i * 72;
    s.shapes.add({ geometry: "line", position: { left: 80, top: y + 58, width: 1080, height: 0 }, fill: "none", line: { fill: C.line, width: 1 } });
    text(s, r[0], 84, y, 470, 52, 20, C.text, i < 2);
    text(s, r[1], 650, y, 500, 52, 20, i < 2 ? C.amber : C.text, i < 2);
  });
  box(s, 82, 594, 1076, 58, "#10243A");
  text(s, "1 Cell = 1 Row  ·  세 Batch에 동일한 Feature Pipeline 적용", 100, 604, 1040, 38, 22, C.cyan, true, "center");
  addFooter(s, 7); note(s, "Source: src/features.py and results/feature_dataset_batch1.csv");
}

// 8. Modeling strategy
{
  const s = addSlide(); title(s, "모델링 단계에서 어떤 모델을 비교할 것인가?", "MODELING STRATEGY");
  text(s, "Regression", 68, 154, 260, 44, 30, C.cyan, true);
  text(s, "Predicted Cycle Life에서 현재 Cycle을 빼면 Remaining Cycle 추정으로 연결 가능", 68, 204, 480, 66, 20, C.text, false);
  text(s, "Target", 68, 308, 100, 26, 16, C.muted, true);
  text(s, "log(cycle_life)", 68, 342, 300, 48, 30, C.amber, true);
  text(s, "왜 Deep Learning이 아닌가", 68, 436, 330, 28, 17, C.muted, true);
  text(s, "약 100개 Cell의 small tabular data이며 engineered feature를 사용한다. 고복잡도 모델은 과적합 위험이 높다.", 68, 472, 450, 112, 20, C.text, false);
  const models = [
    ["Linear Regression", "선형 baseline\n기본 관계 확인"],
    ["ElasticNet", "Main Candidate\n다중공선성 · L1+L2"],
    ["Gradient Boosting", "비선형 비교\n깊이와 tree 수 제한"],
  ];
  models.forEach((m, i) => {
    const x = 570 + i * 210;
    box(s, x, 174, 188, 330, i === 1 ? "#153447" : C.panel);
    text(s, `0${i + 1}`, x + 18, 190, 50, 30, 16, i === 1 ? C.cyan : C.muted, true);
    text(s, m[0], x + 18, 238, 152, 70, 23, C.text, true);
    text(s, m[1], x + 18, 332, 152, 100, 18, C.muted, false);
  });
  text(s, "DAY1에서는 ElasticNet을 주요 후보로 두고, DAY2 Validation에서 최종 모델을 결정", 570, 550, 610, 70, 21, C.cyan, true, "center");
  addFooter(s, 8); note(s, "Source: README Modeling Strategy and src/train.py candidate definitions. DAY1 strategy intentionally precedes final DAY2 selection.");
}

// 9. Conclusion
{
  const s = addSlide(); title(s, "EDA를 통해 수립한 DAY1 모델 전략", "CONCLUSION");
  const flow = [
    ["Cycle Life 분포", "Batch 일반화 고려"],
    ["Capacity Degradation", "절대값보다 변화량"],
    ["DeltaQ(V)", "핵심 열화 Feature"],
    ["Charging Policy", "운전 조건과 Group split"],
    ["Correlation", "Regularization 필요"],
  ];
  flow.forEach((f, i) => {
    const y = 154 + i * 84;
    text(s, f[0], 88, y, 310, 48, 21, C.text, true);
    s.shapes.add({ geometry: "rightArrow", position: { left: 420, top: y + 8, width: 120, height: 30 }, fill: i === 2 ? C.amber : C.line, line: { fill: "none", width: 0 } });
    text(s, f[1], 570, y, 360, 48, 21, i === 2 ? C.amber : C.cyan, true);
  });
  box(s, 940, 166, 252, 350, "#10243A");
  text(s, "Feature Engineering", 960, 192, 212, 48, 20, C.cyan, true, "center");
  text(s, "+", 1028, 254, 80, 38, 28, C.muted, true, "center");
  text(s, "Regression\nlog(cycle_life)", 960, 298, 212, 80, 21, C.text, true, "center");
  text(s, "+", 1028, 386, 80, 38, 28, C.muted, true, "center");
  text(s, "Linear\nElasticNet\nGradient Boosting", 960, 426, 212, 86, 19, C.text, true, "center");
  text(s, "모델을 먼저 정하지 않았다. EDA에서 확인한 Battery 특성이 Feature와 Model Candidate를 결정했다.", 86, 600, 1070, 62, 23, C.text, true, "center");
  addFooter(s, 9); note(s, "Source: synthesis of pages 2-8 and repository README.");
}

const candidatePath = path.join(buildDir, "day1-report-candidate.pptx");
await (await PresentationFile.exportPptx(p)).save(candidatePath);
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
  receiptPath: path.join(buildDir, "day1-report.validation.json"),
});
console.log(finalPath);
