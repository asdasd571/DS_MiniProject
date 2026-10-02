import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const workspaceDir = path.resolve(process.cwd());
const skillDir = "/Users/nak/.codex/plugins/cache/openai-primary-runtime/presentations/26.905.11957/skills/presentations";
const python = "/Users/nak/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3";
const buildDir = path.join(workspaceDir, ".report-build-day1-bridge");
const finalPath = path.join(workspaceDir, "reports/report_source/day1-eda-to-strategy.pptx");
await fs.mkdir(buildDir, { recursive: true });

const { finalizePresentation } = await import(pathToFileURL(path.join(skillDir, "container_tools/artifact_tool_utils.mjs")).href);
const deck = Presentation.create({ slideSize: { width: 1280, height: 720 } });
const FONT = "Pretendard";
const C = { white: "#FFFFFF", navy: "#17324D", ink: "#263641", gray: "#6A7782", teal: "#008C85", pale: "#EEF8F7", line: "#D8E3E8", orange: "#F28C28" };

function rect(slide, x, y, w, h, fill, radius = "roundRect", line = C.line) {
  return slide.shapes.add({ geometry: radius, position: { left: x, top: y, width: w, height: h }, fill, line: { fill: line, width: line === "none" ? 0 : 1 } });
}
function txt(slide, value, x, y, w, h, size = 18, color = C.ink, bold = false, align = "left") {
  const s = slide.shapes.add({ geometry: "textbox", position: { left: x, top: y, width: w, height: h }, fill: "none", line: { fill: "none", width: 0 } });
  s.text = value;
  s.text.style = { typeface: FONT, fontSize: size, color, bold, alignment: align, verticalAlignment: "middle", autoFit: "shrinkText" };
  return s;
}

const s = deck.slides.add();
s.background.fill = C.white;
txt(s, "DAY 1 · 요구사항 대응", 48, 24, 360, 24, 13, C.teal, true);
txt(s, "5개 EDA 질문을 Feature 설계와 모델 전략으로 연결한다", 48, 58, 1160, 52, 31, C.navy, true);
txt(s, "각 Batch에서 관계가 유지되는 신호와 달라지는 신호를 구분해 모델 입력과 검증 구조를 결정", 48, 112, 1160, 30, 17, C.gray);

const cards = [
  ["Q1  Cycle Life", "중앙값\nB1 842 · B2 469 · B3 965\n단수명: B2 76.5%", "Batch 1 선택·튜닝\nBatch 2·3 외부 Test"],
  ["Q2  QD 열화", "qd_slope–수명 r\nB1 +0.10 · B2 -0.49\nB3 +0.35 · 방향 불일치", "절대 QD·slope에\n단독 의존하지 않음"],
  ["Q3  ΔQ(V)", "log_dq_var–수명 r\nB1 -0.886 · B2 -0.910\nB3 -0.742 · 방향 유지", "log_dq_var\n핵심 조기 열화 Feature"],
  ["Q4  C-rate", "C-rate–수명 r\nB1 -0.577 · B2 +0.138\nB3 -0.039 · 영향 차이", "Cell 상태 + 운전조건\n충전 정책 그룹 검증"],
  ["Q5  상관관계", "상위 신호\n세 Batch 모두 ΔQ 계열\nFeature끼리 강한 중복", "대표 Feature 선택\nElasticNet·복잡도 제한"],
];

cards.forEach((c, i) => {
  const x = 40 + i * 244;
  rect(s, x, 170, 222, 388, C.white, "roundRect", C.line);
  txt(s, c[0], x + 16, 188, 190, 30, 16, C.teal, true, "center");
  rect(s, x + 16, 236, 190, 132, "#F7F9FB", "roundRect", "none");
  txt(s, c[1], x + 28, 248, 166, 108, 16, C.navy, true, "center");
  txt(s, "↓", x + 88, 380, 46, 42, 29, C.orange, true, "center");
  rect(s, x + 16, 432, 190, 94, C.pale, "roundRect", "none");
  txt(s, c[2], x + 28, 444, 166, 70, 16, C.navy, true, "center");
});

rect(s, 72, 592, 1136, 66, C.pale, "roundRect", C.line);
txt(s, "Batch마다 달라지는 관계와 공통으로 유지되는 신호를 구분해 Feature와 검증 전략을 결정한다.", 98, 603, 1084, 44, 20, C.navy, true, "center");
s.speakerNotes.textFrame.setText("Source: results/feature_dataset_batch1.csv, batch2.csv, batch3.csv. Correlations recalculated from valid modeling cells only.");

const candidate = path.join(buildDir, "candidate.pptx");
await (await PresentationFile.exportPptx(deck)).save(candidate);
await finalizePresentation({
  workspaceDir,
  candidatePath: candidate,
  finalPath,
  pythonExecutable: python,
  integrityValidatorPath: path.join(skillDir, "container_tools/inspect_presentation_package_integrity.py"),
  layoutValidatorPath: path.join(skillDir, "container_tools/inspect_presentation_layout_geometry.py"),
  layoutArgs: ["--expected-slide-size-emu", "12192000,6858000", "--validate-heading-fit"],
  explicitTotalSlideCount: 1,
  requiredNativeTableOwnerSlides: [],
  requiredNativeChartOwnerSlides: [],
  fontPolicy: { basis: "design", families: [FONT] },
  verifyArtifactToolImport: true,
  receiptPath: path.join(buildDir, "validation.json"),
});
console.log(finalPath);
