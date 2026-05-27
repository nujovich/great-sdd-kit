// merge_pptx.js
// Presentación completa: 11 slides originales + 8 slides de casos de uso = 19 slides

const pptxgen = require("pptxgenjs");
const path = require("path");

const NAVY = "101054";
const BLUE = "1E41B0";
const CYAN = "00B4D8";
const CYAN_SOFT = "CAF0F8";
const GREY_TEXT = "494949";
const GREY_NEUTRAL = "D0D2D3";
const GREY_BG = "F3F3F3";
const RULE = "E9EFF3";
const WHITE = "FFFFFF";

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.title = "GREAT SDD Kit — Del prompt al deploy";
pres.author = "GREAT System";

const TOTAL = 19;

function makeShadow() {
  return { type: "outer", blur: 6, offset: 2, color: "000000", opacity: 0.10 };
}

function addFooter(slide, pageNum) {
  slide.addText("GREAT · Propuesta interna", {
    x: 0, y: 5.2, w: 10, h: 0.3,
    fontSize: 10, fontFace: "Open Sans", color: GREY_TEXT,
    align: "center", margin: 0
  });
  slide.addShape(pres.shapes.OVAL, {
    x: 4.35, y: 5.28, w: 0.08, h: 0.08,
    fill: { color: CYAN }
  });
  slide.addText(String(pageNum).padStart(2, "0") + " / " + String(TOTAL).padStart(2, "0"), {
    x: 8.8, y: 5.15, w: 1.0, h: 0.4,
    fontSize: 20, fontFace: "Arial", color: GREY_TEXT,
    align: "right", margin: 0
  });
}

function addEyebrow(slide, text, x=0.64, y=1.0) {
  slide.addText(text, {
    x, y, w: 8, h: 0.35,
    fontSize: 11, fontFace: "Poppins", color: CYAN,
    bold: true, letterSpacing: 2, margin: 0
  });
}

// ═══════════════════════════════════════════
// SLIDE 01 · PORTADA
// ═══════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  s.addShape(pres.shapes.OVAL, { x: 7.2, y: -0.8, w: 4.5, h: 4.5, fill: { color: CYAN_SOFT, transparency: 60 } });
  s.addText("GREAT System  ·  Especificaciones ejecutables", { x: 1.0, y: 1.8, w: 8, h: 0.35, fontSize: 13, fontFace: "Open Sans", color: GREY_TEXT, letterSpacing: 2, margin: 0 });
  s.addText("SDD Kit", { x: 1.0, y: 2.3, w: 8, h: 1.2, fontSize: 72, fontFace: "Poppins", color: BLUE, margin: 0 });
  s.addShape(pres.shapes.RECTANGLE, { x: 1.0, y: 3.5, w: 5.5, h: 0.7, fill: { color: CYAN } });
  s.addText("Del prompt al deploy en un día", { x: 1.15, y: 3.55, w: 5.2, h: 0.6, fontSize: 26, fontFace: "Poppins", color: WHITE, bold: true, margin: 0 });
  s.addShape(pres.shapes.RECTANGLE, { x: 1.0, y: 4.4, w: 0.5, h: 0.04, fill: { color: CYAN } });
  s.addText([{ text: "No más documentación que se pudre.\n", options: { breakLine: true } }, { text: "Specs como código. Tests como garantía." }], { x: 1.0, y: 4.6, w: 7, h: 0.8, fontSize: 16, fontFace: "Open Sans", color: GREY_TEXT, lineSpacingMultiple: 1.4, margin: 0 });
  addFooter(s, 1);
}

// ═══════════════════════════════════════════
// SLIDE 02 · DIVISOR — El problema
// ═══════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  s.addText("01", { x: 7.5, y: 1.5, w: 2.5, h: 4, fontSize: 280, fontFace: "Open Sans", color: CYAN_SOFT, bold: true, margin: 0 });
  addEyebrow(s, "EL PROBLEMA", 1.0, 1.5);
  s.addText("La documentación tradicional\nya no funciona", { x: 1.0, y: 1.9, w: 6.5, h: 1.8, fontSize: 44, fontFace: "Poppins", color: NAVY, bold: true, lineSpacingMultiple: 1.15, margin: 0 });
  s.addShape(pres.shapes.RECTANGLE, { x: 1.0, y: 3.8, w: 0.6, h: 0.05, fill: { color: CYAN } });
  s.addText("Se escribe, se lee una vez y se pudre. Nadie la actualiza cuando el código cambia.\nLas reglas de negocio viven en cabezas, no en código.\nLos agentes de IA no pueden ejecutar un PDF.", { x: 1.0, y: 4.1, w: 6.5, h: 1.2, fontSize: 16, fontFace: "Open Sans", color: GREY_TEXT, lineSpacingMultiple: 1.5, margin: 0 });
  addFooter(s, 2);
}

// ═══════════════════════════════════════════
// SLIDE 03 · HOOK
// ═══════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  s.addShape(pres.shapes.RECTANGLE, { x: 0.64, y: 2.0, w: 0.06, h: 3.8, fill: { color: CYAN } });
  s.addText([
    { text: "Cuándo fue la última vez que alguien ", options: { fontFace: "Poppins", fontSize: 40, color: NAVY } },
    { text: "actualizó", options: { fontFace: "Poppins", fontSize: 40, color: BLUE, italic: true } },
    { text: " la docs de tu proyecto?", options: { fontFace: "Poppins", fontSize: 40, color: NAVY } }
  ], { x: 1.0, y: 2.2, w: 8.5, h: 2.0, margin: 0, lineSpacingMultiple: 1.2 });
  s.addText("Si la respuesta es \"no sé\" o \"hace meses\" — seguí leyendo.", { x: 1.0, y: 4.5, w: 8, h: 0.6, fontSize: 20, fontFace: "Open Sans", color: GREY_TEXT, italic: true, margin: 0 });
  addFooter(s, 3);
}

// ═══════════════════════════════════════════
// SLIDE 04 · 2-COL
// ═══════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  addEyebrow(s, "DOCUMENTACIÓN VS. SPEC KIT", 0.64, 1.0);
  s.addText("El antes y el después", { x: 0.64, y: 1.35, w: 8, h: 0.8, fontSize: 32, fontFace: "Poppins", color: NAVY, bold: true, margin: 0 });
  s.addText("Documentación tradicional", { x: 0.64, y: 2.4, w: 3.8, h: 0.4, fontSize: 14, fontFace: "Open Sans", color: GREY_NEUTRAL, bold: true, letterSpacing: 1.5, margin: 0 });
  ["Se escribe en Google Docs / Confluence","Se lee en el onboarding (quizás)","El código cambia, la doc no","\"Según la reunión, el sistema debe...\"","Devs nuevo preguntan al senior"].forEach((step, i) => {
    s.addText([{ text: "→ ", options: { color: GREY_NEUTRAL, bold: true } }, { text: step }], { x: 0.64, y: 2.9 + i * 0.38, w: 3.8, h: 0.35, fontSize: 13, fontFace: "Open Sans", color: GREY_TEXT, margin: 0 });
  });
  s.addText("6 meses después: la doc es un museo.", { x: 0.64, y: 5.0, w: 3.8, h: 0.4, fontSize: 14, fontFace: "Poppins", color: NAVY, bold: true, margin: 0 });
  s.addText("Nadie confía. Nadie actualiza.", { x: 0.64, y: 5.3, w: 3.8, h: 0.3, fontSize: 11, fontFace: "Open Sans", color: GREY_TEXT, margin: 0 });
  s.addShape(pres.shapes.RECTANGLE, { x: 4.9, y: 2.4, w: 0.01, h: 3.2, fill: { color: CYAN } });
  s.addText("SDD Kit de GREAT", { x: 5.3, y: 2.4, w: 3.8, h: 0.4, fontSize: 14, fontFace: "Open Sans", color: CYAN, bold: true, letterSpacing: 1.5, margin: 0 });
  ["Specs como código versionado","Tests validan compliance automático","Si el código no cumple, el test falla","CLAUDE.md apunta al kit (1 línea)","Agentes AI ejecutan las mismas specs"].forEach((step, i) => {
    s.addText([{ text: "→ ", options: { color: CYAN, bold: true } }, { text: step }], { x: 5.3, y: 2.9 + i * 0.38, w: 3.8, h: 0.35, fontSize: 13, fontFace: "Open Sans", color: GREY_TEXT, margin: 0 });
  });
  s.addText("6 meses después: la spec sigue viva.", { x: 5.3, y: 5.0, w: 3.8, h: 0.4, fontSize: 14, fontFace: "Poppins", color: NAVY, bold: true, margin: 0 });
  s.addText("El test te avisa cuando algo se rompe.", { x: 5.3, y: 5.3, w: 3.8, h: 0.3, fontSize: 11, fontFace: "Open Sans", color: GREY_TEXT, margin: 0 });
  addFooter(s, 4);
}

// ═══════════════════════════════════════════
// SLIDE 05 · SDD FIX
// ═══════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  addEyebrow(s, "CÓMO FUNCIONA", 0.64, 1.0);
  s.addText("Menos incorrecto por diseño", { x: 0.64, y: 1.35, w: 8, h: 0.8, fontSize: 32, fontFace: "Poppins", color: NAVY, bold: true, margin: 0 });
  const nodes = [
    { role: "PO / Arquitecta", line: "\"El sistema debe...\"", human: true },
    { role: "SDD Kit", line: "rules → pipelines → tests", human: false },
    { role: "Test Suite", line: "216 tests validan compliance", human: false },
    { role: "Agente AI", line: "lee specs, no adivina", human: false }
  ];
  nodes.forEach((node, i) => {
    const x = 0.64 + i * 2.35;
    s.addShape(pres.shapes.RECTANGLE, { x, y: 2.5, w: 1.9, h: 1.1, fill: { color: node.human ? "F8FAFD" : WHITE }, line: { color: node.human ? NAVY : RULE, width: 1 } });
    s.addShape(pres.shapes.RECTANGLE, { x, y: 2.5, w: 1.9, h: 0.04, fill: { color: node.human ? NAVY : CYAN } });
    s.addText(node.role, { x: x+0.1, y: 2.6, w: 1.7, h: 0.4, fontSize: 13, fontFace: "Poppins", color: NAVY, bold: true, margin: 0 });
    s.addText(node.line, { x: x+0.1, y: 3.0, w: 1.7, h: 0.4, fontSize: 10, fontFace: "JetBrains Mono", color: GREY_TEXT, margin: 0 });
    if (i < 3) s.addText("→", { x: x+1.95, y: 2.7, w: 0.3, h: 0.6, fontSize: 22, color: CYAN, align: "center", margin: 0 });
  });
  s.addShape(pres.shapes.LINE, { x: 0.64, y: 4.0, w: 3.5, h: 0, line: { color: NAVY, width: 1.5 } });
  s.addShape(pres.shapes.LINE, { x: 6.0, y: 4.0, w: 3.36, h: 0, line: { color: CYAN, width: 1.5 } });
  s.addShape(pres.shapes.RECTANGLE, { x: 3.0, y: 4.15, w: 4.0, h: 0.9, fill: { color: NAVY } });
  s.addText("RESULTADO", { x: 3.0, y: 4.18, w: 4.0, h: 0.25, fontSize: 9, fontFace: "Poppins", color: CYAN, bold: true, letterSpacing: 2, align: "center", margin: 0 });
  s.addText("Single source of truth versionada y testeable", { x: 3.0, y: 4.42, w: 4.0, h: 0.4, fontSize: 14, fontFace: "Poppins", color: WHITE, align: "center", margin: 0 });
  s.addText("Sin kit", { x: 0.64, y: 5.3, w: 3.5, h: 0.3, fontSize: 10, fontFace: "Open Sans", color: GREY_NEUTRAL, bold: true, letterSpacing: 1.5, margin: 0 });
  s.addText("Reglas en cabezas. Conocimiento tribal.\nOnboarding de semanas.", { x: 0.64, y: 5.55, w: 3.5, h: 0.5, fontSize: 11, fontFace: "Poppins", color: GREY_TEXT, lineSpacingMultiple: 1.3, margin: 0 });
  s.addText("→", { x: 4.7, y: 5.55, w: 0.5, h: 0.5, fontSize: 28, color: CYAN, align: "center", margin: 0 });
  s.addText("Con kit", { x: 5.5, y: 5.3, w: 3.5, h: 0.3, fontSize: 10, fontFace: "Open Sans", color: CYAN, bold: true, letterSpacing: 1.5, margin: 0 });
  s.addText("Reglas versionadas y testeables.\nOnboarding en minutos.", { x: 5.5, y: 5.55, w: 3.5, h: 0.5, fontSize: 11, fontFace: "Poppins", color: NAVY, lineSpacingMultiple: 1.3, margin: 0 });
  addFooter(s, 5);
}

// ═══════════════════════════════════════════
// SLIDE 06 · NÚMEROS
// ═══════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  s.addText("02", { x: 7.5, y: 1.5, w: 2.5, h: 4, fontSize: 280, fontFace: "Open Sans", color: CYAN_SOFT, bold: true, margin: 0 });
  addEyebrow(s, "ESTADO ACTUAL", 1.0, 1.5);
  s.addText("PoC funcional,\nlisto para escalar", { x: 1.0, y: 1.9, w: 6.5, h: 1.8, fontSize: 44, fontFace: "Poppins", color: NAVY, bold: true, lineSpacingMultiple: 1.15, margin: 0 });
  s.addShape(pres.shapes.RECTANGLE, { x: 1.0, y: 3.8, w: 0.6, h: 0.05, fill: { color: CYAN } });
  [{n:"78",l:"Reglas de negocio"},{n:"30",l:"Módulos DSPy"},{n:"6",l:"Pipelines"},{n:"216",l:"Tests ejecutables"},{n:"3",l:"Entry points"}].forEach((st, i) => {
    const x = 1.0 + i * 1.7;
    s.addText(st.n, { x, y: 4.2, w: 1.5, h: 0.8, fontSize: 48, fontFace: "Open Sans", color: CYAN, bold: true, margin: 0 });
    s.addText(st.l, { x, y: 5.0, w: 1.5, h: 0.4, fontSize: 10, fontFace: "Open Sans", color: GREY_TEXT, letterSpacing: 1, margin: 0 });
    if (i < 4) s.addShape(pres.shapes.RECTANGLE, { x: x+1.55, y: 4.3, w: 0.01, h: 1.0, fill: { color: RULE } });
  });
  addFooter(s, 6);
}

// ═══════════════════════════════════════════
// SLIDE 07 · QUOTE
// ═══════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  s.addShape(pres.shapes.RECTANGLE, { x: 0.64, y: 1.8, w: 0.06, h: 3.8, fill: { color: CYAN } });
  addEyebrow(s, "EL PRINCIPIO", 1.0, 1.8);
  s.addText([
    { text: "\"La documentación escrita describe lo que alguien\npensó que el sistema debería hacer.\"\n\n", options: { fontFace: "Poppins", fontSize: 28, color: GREY_NEUTRAL, italic: true } },
    { text: "El Spec Kit describe lo que el sistema ", options: { fontFace: "Poppins", fontSize: 28, color: NAVY, bold: true } },
    { text: "realmente hace", options: { fontFace: "Poppins", fontSize: 28, color: BLUE, bold: true, italic: true } },
    { text: " — y te avisa\ncuando dejan de coincidir.", options: { fontFace: "Poppins", fontSize: 28, color: NAVY, bold: true } }
  ], { x: 1.0, y: 2.2, w: 8.5, h: 3.0, margin: 0, lineSpacingMultiple: 1.3 });
  s.addText("— Principio GREAT", { x: 1.0, y: 5.0, w: 8, h: 0.4, fontSize: 14, fontFace: "Open Sans", color: GREY_TEXT, italic: true, margin: 0 });
  addFooter(s, 7);
}

// ═══════════════════════════════════════════
// SLIDE 08 · TABLA
// ═══════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  addEyebrow(s, "COMPARACIÓN", 0.64, 1.0);
  s.addText("Docs escritas vs. SDD Kit", { x: 0.64, y: 1.35, w: 8, h: 0.8, fontSize: 32, fontFace: "Poppins", color: NAVY, bold: true, margin: 0 });
  const rows = [
    ["Se actualiza con cada cambio","✗","✓"],["Testeable / auditable","✗","✓"],
    ["Onboarding sin preguntar al senior","✗","✓"],["Agentes AI pueden ejecutarlo","✗","✓"],
    ["Reglas de negocio versionadas","✗","✓"],["Detecta drift código vs. diseño","✗","✓"],
    ["Costo de setup","Bajo\n(escribir docs)","1 día\n(git submodule)"]
  ];
  const tableData = [
    ["Criterio","Docs escritas","SDD Kit"].map(h => ({ text: h, options: { fill: { color: h==="SDD Kit"?CYAN:h==="Docs escritas"?"8B8B8B":NAVY }, color: h==="SDD Kit"?NAVY:WHITE, bold: true, fontFace: "Poppins", fontSize: 11, align: h==="Criterio"?"left":"center" } })),
    ...rows.map((row, ri) => row.map((cell, ci) => ({ text: cell, options: { fill: { color: ri%2===0?WHITE:GREY_BG }, color: ci===0?NAVY:cell==="✓"?CYAN:cell==="✗"?GREY_NEUTRAL:GREY_TEXT, bold: ci===0, fontFace: "Open Sans", fontSize: ci>0&&cell.length<=3?16:11, align: ci===0?"left":"center" } })))
  ];
  s.addTable(tableData, { x: 0.64, y: 2.3, w: 8.7, h: 3.0, colW: [4.5, 2.1, 2.1], border: { pt: 0.5, color: RULE }, margin: 0 });
  addFooter(s, 8);
}

// ═══════════════════════════════════════════
// SLIDE 09 · ADOPCIÓN
// ═══════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  addEyebrow(s, "ADOPCIÓN", 0.64, 1.0);
  s.addText("Qué se necesita\npara implementarlo", { x: 0.64, y: 1.35, w: 8, h: 1.2, fontSize: 32, fontFace: "Poppins", color: NAVY, bold: true, lineSpacingMultiple: 1.15, margin: 0 });
  [{n:"01",t:"Agregar como submodule",d:"El kit se incluye como git submodule. Reusable entre backend y frontend.",c:"git submodule add great-dspy-pipeline"},{n:"02",t:"Configurar agentes AI",d:"Una línea en CLAUDE.md / .cursorrules apunta al kit.",c:"Carga sdd-kit/AGENTS.md"},{n:"03",t:"Correr tests y validar",d:"Los tests validan que el proyecto cumple cada spec.",c:"pytest tests/ -v"}].forEach((step, i) => {
    const x = 0.64 + i * 3.1;
    s.addShape(pres.shapes.RECTANGLE, { x, y: 2.7, w: 2.8, h: 2.6, fill: { color: WHITE }, line: { color: RULE, width: 1 } });
    s.addShape(pres.shapes.RECTANGLE, { x, y: 2.7, w: 2.8, h: 0.04, fill: { color: CYAN } });
    s.addText(step.n, { x: x+0.2, y: 2.85, w: 2.4, h: 0.6, fontSize: 30, fontFace: "Open Sans", color: CYAN, bold: true, margin: 0 });
    s.addText(step.t, { x: x+0.2, y: 3.4, w: 2.4, h: 0.5, fontSize: 14, fontFace: "Poppins", color: NAVY, bold: true, margin: 0 });
    s.addText(step.d, { x: x+0.2, y: 3.9, w: 2.4, h: 0.7, fontSize: 10, fontFace: "Open Sans", color: GREY_TEXT, lineSpacingMultiple: 1.4, margin: 0 });
    s.addShape(pres.shapes.RECTANGLE, { x: x+0.15, y: 4.65, w: 2.5, h: 0.55, fill: { color: GREY_BG } });
    s.addShape(pres.shapes.RECTANGLE, { x: x+0.15, y: 4.65, w: 0.03, h: 0.55, fill: { color: CYAN } });
    s.addText(step.c, { x: x+0.25, y: 4.68, w: 2.35, h: 0.5, fontSize: 8, fontFace: "JetBrains Mono", color: NAVY, lineSpacingMultiple: 1.3, margin: 0 });
  });
  addFooter(s, 9);
}

// ═══════════════════════════════════════════
// SLIDE 10 · ARGUMENTO
// ═══════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  addEyebrow(s, "EL ARGUMENTO", 0.64, 1.0);
  s.addText("Para devs y para negocio", { x: 0.64, y: 1.35, w: 8, h: 0.8, fontSize: 32, fontFace: "Poppins", color: NAVY, bold: true, margin: 0 });
  ["\"el código no coincide con el diseño\" — el test lo atrapa.","\"pero el PO dijo que...\" — la spec es la fuente.","reverse-engineering de código legacy.","Refactor con confianza — tests validan comportamiento."].forEach((pt, i) => {
    s.addText([{ text: "No más ", options: { bold: true, color: NAVY } }, { text: pt }], { x: 0.64, y: 2.9 + i * 0.42, w: 3.8, h: 0.4, fontSize: 12, fontFace: "Open Sans", color: GREY_TEXT, lineSpacingMultiple: 1.3, margin: 0 });
  });
  s.addShape(pres.shapes.RECTANGLE, { x: 4.9, y: 2.4, w: 0.01, h: 3.2, fill: { color: CYAN } });
  ["Menos bugs en producción = menos costo de soporte.","Onboarding más rápido = devs productivos desde el día 1.","Agentes AI que entienden el negocio = automatización real.","Auditoría — specs ejecutables como documentación regulatoria."].forEach((pt, i) => {
    s.addText(pt, { x: 5.3, y: 2.9 + i * 0.42, w: 3.8, h: 0.4, fontSize: 12, fontFace: "Open Sans", color: GREY_TEXT, lineSpacingMultiple: 1.3, margin: 0 });
  });
  addFooter(s, 10);
}

// ═══════════════════════════════════════════
// SLIDE 11 · PREGUNTAS
// ═══════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  s.addText("?", { x: 0.64, y: 1.2, w: 3, h: 3, fontSize: 160, fontFace: "Poppins", color: NAVY, bold: true, margin: 0 });
  s.addShape(pres.shapes.OVAL, { x: 2.8, y: 1.5, w: 0.3, h: 0.3, fill: { color: CYAN } });
  s.addText("Preguntas, dudas, objeciones.", { x: 0.64, y: 4.2, w: 8, h: 0.6, fontSize: 22, fontFace: "Open Sans", color: GREY_TEXT, margin: 0 });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.64, y: 4.9, w: 0.5, h: 0.04, fill: { color: CYAN } });
  s.addText([{ text: "Repo: ", options: { bold: true, color: NAVY } },{ text: "github.com/nujovich/great-dspy-pipeline\n", options: { color: GREY_TEXT } },{ text: "PoC: ", options: { bold: true, color: NAVY } },{ text: "ux_great_prototype (3 entry points, React + Python)", options: { color: GREY_TEXT } }], { x: 0.64, y: 5.1, w: 8, h: 0.6, fontSize: 14, fontFace: "Open Sans", lineSpacingMultiple: 1.4, margin: 0 });
  addFooter(s, 11);
}

// ═══════════════════════════════════════════
// SLIDE 12 · DIVISOR — Casos de Uso
// ═══════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  s.addText("03", { x: 7.5, y: 1.5, w: 2.5, h: 4, fontSize: 280, fontFace: "Open Sans", color: CYAN_SOFT, bold: true, margin: 0 });
  addEyebrow(s, "CASOS DE USO", 1.0, 1.5);
  s.addText("El SDD Kit no es solo\nun validador de reglas", { x: 1.0, y: 1.9, w: 6.5, h: 1.8, fontSize: 44, fontFace: "Poppins", color: NAVY, bold: true, lineSpacingMultiple: 1.15, margin: 0 });
  s.addShape(pres.shapes.RECTANGLE, { x: 1.0, y: 3.8, w: 0.6, h: 0.05, fill: { color: CYAN } });
  s.addText("Es una herramienta multipropósito: validar compliance, guiar agentes de IA, documentar reglas, auditar código, onboarding de devs, y extender a otros dominios.", { x: 1.0, y: 4.1, w: 6.5, h: 1.2, fontSize: 16, fontFace: "Open Sans", color: GREY_TEXT, lineSpacingMultiple: 1.5, margin: 0 });
  addFooter(s, 12);
}

// ═══════════════════════════════════════════
// SLIDE 13 · 6 Casos de Uso (grid)
// ═══════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  addEyebrow(s, "6 CASOS DE USO", 0.64, 1.0);
  s.addText("¿Para qué sirve el SDD Kit?", { x: 0.64, y: 1.35, w: 8, h: 0.8, fontSize: 32, fontFace: "Poppins", color: NAVY, bold: true, margin: 0 });
  [{i:"✓",t:"Validación de Compliance",d:"216 tests verifican que el código cumple las 78 reglas de negocio automáticamente.",c:CYAN},{i:"🤖",t:"Guía para Agentes de IA",d:"AGENTS.md + CLAUDE.md + .cursorrules: el agente lee specs, no adivina reglas.",c:BLUE},{i:"📋",t:"Documentación Ejecutable",d:"Las reglas viven como código versionado, no como PDFs que se pudren.",c:CYAN},{i:"🔍",t:"Auditoría de Código",d:"¿Este código cumple las reglas? pytest lo dice en segundos.",c:BLUE},{i:"🚀",t:"Onboarding de Devs",d:"Un dev nuevo lee los specs y sabe exactamente qué construir sin preguntar.",c:CYAN},{i:"🧩",t:"Extensible a Otros Dominios",d:"El framework sdd/ es reusable. Copiá las base classes y creá tus propias reglas.",c:BLUE}].forEach((uc, i) => {
    const x = 0.64 + (i%3) * 3.1, y = 2.4 + Math.floor(i/3) * 1.55;
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: 2.8, h: 1.35, fill: { color: WHITE }, line: { color: RULE, width: 1 }, shadow: makeShadow() });
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: 2.8, h: 0.04, fill: { color: uc.c } });
    s.addShape(pres.shapes.OVAL, { x: x+0.15, y: y+0.15, w: 0.35, h: 0.35, fill: { color: uc.c } });
    s.addText(uc.i, { x: x+0.15, y: y+0.17, w: 0.35, h: 0.3, fontSize: 14, fontFace: "Open Sans", color: WHITE, align: "center", margin: 0 });
    s.addText(uc.t, { x: x+0.55, y: y+0.15, w: 2.1, h: 0.35, fontSize: 11, fontFace: "Poppins", color: NAVY, bold: true, margin: 0 });
    s.addText(uc.d, { x: x+0.15, y: y+0.5, w: 2.5, h: 0.7, fontSize: 9, fontFace: "Open Sans", color: GREY_TEXT, lineSpacingMultiple: 1.3, margin: 0 });
  });
  addFooter(s, 13);
}

// ═══════════════════════════════════════════
// SLIDE 14 · Uso 1: Librería
// ═══════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  addEyebrow(s, "USO 1: COMO LIBRERÍA", 0.64, 1.0);
  s.addText("Importá los módulos\ncomo librería Python", { x: 0.64, y: 1.35, w: 8, h: 1.2, fontSize: 32, fontFace: "Poppins", color: NAVY, bold: true, lineSpacingMultiple: 1.15, margin: 0 });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.64, y: 2.7, w: 8.7, h: 2.5, fill: { color: "1E1E2E" } });
  [{t:"from great_dspy.modules.pre_estimation import StatusTransitionValidator",c:CYAN},{t:"",c:WHITE},{t:"v = StatusTransitionValidator()",c:WHITE},{t:"result = v.forward(\"approved\", \"draft\")",c:WHITE},{t:"assert result[\"is_valid\"] is False  # Approved es terminal",c:GREY_NEUTRAL},{t:"",c:WHITE},{t:"from great_dspy.specs.allocation_specs import calculate_fte_ke",c:CYAN},{t:"ke = calculate_fte_ke(fte=1.0, societe_site=\"Horse Spain\", year=\"2024\")",c:WHITE},{t:"assert ke == 107.0  # Validación automática de fórmula",c:GREY_NEUTRAL}].forEach((l, i) => {
    s.addText(l.t, { x: 0.8, y: 2.8 + i * 0.28, w: 8.4, h: 0.25, fontSize: 11, fontFace: "JetBrains Mono", color: l.c, margin: 0 });
  });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.64, y: 5.35, w: 8.7, h: 0.05, fill: { color: CYAN } });
  s.addText("✅ Sin LLM, sin agentes. Python puro. Los módulos son importables como cualquier librería.", { x: 0.64, y: 5.45, w: 8.7, h: 0.4, fontSize: 12, fontFace: "Open Sans", color: GREY_TEXT, margin: 0 });
  addFooter(s, 14);
}

// ═══════════════════════════════════════════
// SLIDE 15 · Uso 2: Pipeline
// ═══════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  addEyebrow(s, "USO 2: COMO PIPELINE", 0.64, 1.0);
  s.addText("Cada pipeline es el blueprint\nde un endpoint", { x: 0.64, y: 1.35, w: 8, h: 1.2, fontSize: 32, fontFace: "Poppins", color: NAVY, bold: true, lineSpacingMultiple: 1.15, margin: 0 });
  [{n:"SelectionValidator",r:"§5 Compatibilidad"},{n:"PermissionChecker",r:"§2 Roles"},{n:"InductorSelector",r:"§6-8 Workload"},{n:"EstimationCalculator",r:"§9 Fórmulas"},{n:"SaveValidator",r:"§10 Draft gate"},{n:"MonthDistributor",r:"§9.4 Monthly"},{n:"SummaryGenerator",r:"§10.3 Panel"}].forEach((st, i) => {
    const x = 0.64 + i * 1.18;
    s.addShape(pres.shapes.RECTANGLE, { x, y: 2.7, w: 1.1, h: 0.9, fill: { color: i%2===0?NAVY:CYAN } });
    s.addText(st.n, { x: x+0.05, y: 2.75, w: 1.0, h: 0.4, fontSize: 7, fontFace: "Poppins", color: WHITE, bold: true, align: "center", margin: 0 });
    s.addText(st.r, { x: x+0.05, y: 3.1, w: 1.0, h: 0.35, fontSize: 6, fontFace: "Open Sans", color: i%2===0?CYAN_SOFT:NAVY, align: "center", margin: 0 });
    if (i < 6) s.addText("→", { x: x+1.12, y: 2.9, w: 0.04, h: 0.4, fontSize: 10, color: CYAN, align: "center", margin: 0 });
  });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.64, y: 3.9, w: 8.7, h: 0.8, fill: { color: GREY_BG } });
  s.addText("POST /api/pre-estimation/save-draft", { x: 0.7, y: 3.95, w: 4, h: 0.35, fontSize: 12, fontFace: "JetBrains Mono", color: NAVY, bold: true, margin: 0 });
  s.addText("→ Cada etapa del pipeline = un paso del endpoint", { x: 0.7, y: 4.25, w: 8.5, h: 0.3, fontSize: 10, fontFace: "Open Sans", color: GREY_TEXT, margin: 0 });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.64, y: 4.85, w: 8.7, h: 0.5, fill: { color: "1E1E2E" } });
  s.addText("ctx = run_pipeline(selected_lines=[line_1, line_2], role=\"Engineer\", metier=\"Backend\")", { x: 0.7, y: 4.88, w: 8.5, h: 0.25, fontSize: 10, fontFace: "JetBrains Mono", color: CYAN, margin: 0 });
  s.addText("print(f\"Can save draft: {ctx.can_save_draft}\")  # → True/False según reglas", { x: 0.7, y: 5.08, w: 8.5, h: 0.22, fontSize: 9, fontFace: "JetBrains Mono", color: GREY_NEUTRAL, margin: 0 });
  addFooter(s, 15);
}

// ═══════════════════════════════════════════
// SLIDE 16 · Uso 3: Agente IA
// ═══════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  addEyebrow(s, "USO 3: COMO AGENTE DE IA", 0.64, 1.0);
  s.addText("El agente lee specs,\nno adivina reglas", { x: 0.64, y: 1.35, w: 8, h: 1.2, fontSize: 32, fontFace: "Poppins", color: NAVY, bold: true, lineSpacingMultiple: 1.15, margin: 0 });
  [{l:"CLAUDE.md / .cursorrules",d:"Entry point del agente",c:CYAN},{l:"AGENTS.md",d:"Instrucciones + reglas de negocio",c:NAVY},{l:"great_dspy/specs/",d:"78 reglas estructuradas",c:CYAN},{l:"great_dspy/modules/",d:"Lógica pura importable",c:NAVY},{l:"great_dspy/pipeline/",d:"Blueprint de endpoints",c:CYAN},{l:"tests/",d:"216 tests de validación",c:NAVY}].forEach((step, i) => {
    const y = 2.6 + i * 0.48;
    s.addShape(pres.shapes.RECTANGLE, { x: 1.5, y, w: 7, h: 0.4, fill: { color: step.c } });
    s.addText(step.l, { x: 1.6, y: y+0.05, w: 3.5, h: 0.3, fontSize: 12, fontFace: "Poppins", color: WHITE, bold: true, margin: 0 });
    s.addText(step.d, { x: 5.2, y: y+0.05, w: 3.2, h: 0.3, fontSize: 10, fontFace: "Open Sans", color: step.c===NAVY?CYAN_SOFT:NAVY, margin: 0 });
    if (i < 5) s.addText("↓", { x: 4.8, y: y+0.38, w: 0.4, h: 0.1, fontSize: 12, color: CYAN, align: "center", margin: 0 });
  });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.64, y: 5.35, w: 8.7, h: 0.05, fill: { color: CYAN } });
  s.addText("💡 Sin AGENTS.md → el agente adivina. Con AGENTS.md → el agente ejecuta specs.", { x: 0.64, y: 5.45, w: 8.7, h: 0.4, fontSize: 12, fontFace: "Open Sans", color: GREY_TEXT, margin: 0 });
  addFooter(s, 16);
}

// ═══════════════════════════════════════════
// SLIDE 17 · Uso 4+5: Docs + Auditoría
// ═══════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  addEyebrow(s, "USO 4 Y 5: DOCUMENTACIÓN + AUDITORÍA", 0.64, 1.0);
  s.addText("Docs que no se pudren +\nAuditoría en segundos", { x: 0.64, y: 1.35, w: 8, h: 1.2, fontSize: 32, fontFace: "Poppins", color: NAVY, bold: true, lineSpacingMultiple: 1.15, margin: 0 });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.64, y: 2.6, w: 4, h: 2.5, fill: { color: WHITE }, line: { color: RULE, width: 1 } });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.64, y: 2.6, w: 4, h: 0.04, fill: { color: CYAN } });
  s.addText("📋 Documentación Ejecutable", { x: 0.8, y: 2.75, w: 3.7, h: 0.4, fontSize: 14, fontFace: "Poppins", color: NAVY, bold: true, margin: 0 });
  ["Las reglas viven como código versionado","Cada regla tiene ID, severity, criterios","Los tests son la documentación que se ejecuta","Si el test falla, la doc está desactualizada","Git history = historial de cambios de reglas"].forEach((pt, i) => {
    s.addText("→ " + pt, { x: 0.8, y: 3.2 + i * 0.32, w: 3.7, h: 0.28, fontSize: 10, fontFace: "Open Sans", color: GREY_TEXT, margin: 0 });
  });
  s.addShape(pres.shapes.RECTANGLE, { x: 5.3, y: 2.6, w: 4, h: 2.5, fill: { color: WHITE }, line: { color: RULE, width: 1 } });
  s.addShape(pres.shapes.RECTANGLE, { x: 5.3, y: 2.6, w: 4, h: 0.04, fill: { color: BLUE } });
  s.addText("🔍 Auditoría de Código", { x: 5.45, y: 2.75, w: 3.7, h: 0.4, fontSize: 14, fontFace: "Poppins", color: NAVY, bold: true, margin: 0 });
  ["¿Este PR cumple las reglas de negocio?","pytest tests/ → respuesta en segundos","216 tests = 78 reglas verificadas","CI/CD integration: bloquea merge si falla","Compliance report automático"].forEach((pt, i) => {
    s.addText("→ " + pt, { x: 5.45, y: 3.2 + i * 0.32, w: 3.7, h: 0.28, fontSize: 10, fontFace: "Open Sans", color: GREY_TEXT, margin: 0 });
  });
  addFooter(s, 17);
}

// ═══════════════════════════════════════════
// SLIDE 18 · Uso 6: Extensible
// ═══════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  addEyebrow(s, "USO 6: EXTENSIBLE A OTROS DOMINIOS", 0.64, 1.0);
  s.addText("El framework sdd/\nes reutilizable", { x: 0.64, y: 1.35, w: 8, h: 0.8, fontSize: 32, fontFace: "Poppins", color: NAVY, bold: true, margin: 0 });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.64, y: 2.4, w: 3.8, h: 2.8, fill: { color: NAVY } });
  s.addText("SDD Kit GREAT", { x: 0.8, y: 2.5, w: 3.5, h: 0.4, fontSize: 14, fontFace: "Poppins", color: CYAN, bold: true, margin: 0 });
  ["great_dspy/specs/","  pre_estimation_specs (17 reglas)","  estimation_review_specs (10)","  allocation_specs (16)","  final_review_specs (10)","  management_view_specs (8)","  transversal_specs (13)","great_dspy/modules/ (30)","great_dspy/pipeline/ (6)","tests/ (216 tests)"].forEach((l, i) => {
    s.addText(l, { x: 0.8, y: 2.95 + i * 0.2, w: 3.5, h: 0.18, fontSize: 8, fontFace: "JetBrains Mono", color: i===0||i===7?CYAN_SOFT:WHITE, margin: 0 });
  });
  s.addText("→", { x: 4.6, y: 3.5, w: 0.5, h: 0.5, fontSize: 30, color: CYAN, align: "center", margin: 0 });
  s.addShape(pres.shapes.RECTANGLE, { x: 5.3, y: 2.4, w: 4, h: 2.8, fill: { color: "1E1E2E" } });
  s.addText("Tu Dominio", { x: 5.45, y: 2.5, w: 3.7, h: 0.4, fontSize: 14, fontFace: "Poppins", color: CYAN, bold: true, margin: 0 });
  ["sdd/ ← Copiar tal cual (base)","","domains/tu_dominio/specs/","  tus_reglas.py","","domains/tu_dominio/modules/","  tus_modulos.py","","domains/tu_dominio/pipeline/","  tu_pipeline.py","","tests/ (tus tests)"].forEach((l, i) => {
    s.addText(l, { x: 5.45, y: 2.95 + i * 0.2, w: 3.7, h: 0.18, fontSize: 8, fontFace: "JetBrains Mono", color: i===0||i===2||i===5||i===8?CYAN:GREY_NEUTRAL, margin: 0 });
  });
  s.addText("6 pasos para extender:", { x: 0.64, y: 5.35, w: 8.7, h: 0.3, fontSize: 11, fontFace: "Poppins", color: NAVY, bold: true, margin: 0 });
  ["1. Copiá sdd/","2. Creá specs/","3. Creá modules/","4. Creá pipeline/","5. Creá tests/","6. Heredá de sdd/"].forEach((st, i) => {
    s.addText(st, { x: 0.64 + (i%3)*3.1, y: 5.65 + Math.floor(i/3)*0.25, w: 2.9, h: 0.22, fontSize: 8, fontFace: "Open Sans", color: GREY_TEXT, margin: 0 });
  });
  addFooter(s, 18);
}

// ═══════════════════════════════════════════
// SLIDE 19 · Resumen
// ═══════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  addEyebrow(s, "RESUMEN", 0.64, 1.0);
  s.addText("Un kit, seis formas de usarlo", { x: 0.64, y: 1.35, w: 8, h: 0.8, fontSize: 32, fontFace: "Poppins", color: NAVY, bold: true, margin: 0 });
  const summary = [
    {u:"Librería",c:"Necesitás lógica de negocio importable",s:"Python puro"},
    {u:"Pipeline",c:"Necesitás orquestar validaciones en orden",s:"DSPy modules"},
    {u:"Agente IA",c:"Querés que el agente cumpla reglas sin adivinar",s:"AGENTS.md + specs"},
    {u:"Documentación",c:"Querés docs versionadas y testeables",s:"YAML + Markdown"},
    {u:"Auditoría",c:"Necesitás verificar compliance en CI/CD",s:"pytest + 216 tests"},
    {u:"Extensión",c:"Querés aplicar SDD a otro dominio",s:"sdd/ base framework"}
  ];
  const sumTable = [
    ["Uso","Cuándo","Stack"].map(h => ({t:h,o:{fill:{color:NAVY},color:WHITE,bold:true,fontFace:"Poppins",fontSize:11,align:"center"}})),
    ...summary.map((row,ri) => [
      {t:row.u,o:{fill:{color:ri%2===0?WHITE:GREY_BG},color:NAVY,bold:true,fontFace:"Poppins",fontSize:12,align:"center"}},
      {t:row.c,o:{fill:{color:ri%2===0?WHITE:GREY_BG},color:GREY_TEXT,fontFace:"Open Sans",fontSize:10,align:"left"}},
      {t:row.s,o:{fill:{color:ri%2===0?WHITE:GREY_BG},color:GREY_TEXT,fontFace:"Open Sans",fontSize:10,align:"center"}}
    ])
  ];
  s.addTable(sumTable, { x: 0.64, y: 2.3, w: 8.7, h: 3.0, colW: [1.5, 4.5, 2.7], border: { pt: 0.5, color: RULE }, margin: 0 });
  addFooter(s, 19);
}

// ─── Write ───
const outPath = path.join(__dirname, "GREAT_SDD_Kit_Completo.pptx");
pres.writeFile({ fileName: outPath }).then(() => {
  console.log("Created:", outPath);
}).catch(err => { console.error(err); process.exit(1); });
