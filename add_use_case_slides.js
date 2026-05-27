// add_use_case_slides.js
// Agrega slides de "Casos de Uso" al PPTX existente

const pptxgen = require("pptxgenjs");
const path = require("path");
const fs = require("fs");

const NAVY = "101054";
const BLUE = "1E41B0";
const CYAN = "00B4D8";
const CYAN_SOFT = "CAF0F8";
const GREY_TEXT = "494949";
const GREY_NEUTRAL = "D0D2D3";
const GREY_BG = "F3F3F3";
const RULE = "E9EFF3";
const WHITE = "FFFFFF";

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
  slide.addText(String(pageNum).padStart(2, "0"), {
    x: 9.0, y: 5.15, w: 0.8, h: 0.4,
    fontSize: 24, fontFace: "Arial", color: GREY_TEXT,
    align: "right", margin: 0
  });
}

function addEyebrow(slide, text, x = 0.64, y = 1.0) {
  slide.addText(text, {
    x, y, w: 8, h: 0.35,
    fontSize: 11, fontFace: "Poppins", color: CYAN,
    bold: true, letterSpacing: 2, margin: 0
  });
}

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.title = "GREAT SDD Kit — Casos de Uso";
pres.author = "GREAT System";

// ═══════════════════════════════════════════
// SLIDE 12 · DIVISOR — Casos de Uso
// ═══════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  s.addText("03", {
    x: 7.5, y: 1.5, w: 2.5, h: 4,
    fontSize: 280, fontFace: "Open Sans", color: CYAN_SOFT, bold: true, margin: 0
  });
  addEyebrow(s, "CASOS DE USO", 1.0, 1.5);
  s.addText("El SDD Kit no es solo\nun validador de reglas", {
    x: 1.0, y: 1.9, w: 6.5, h: 1.8,
    fontSize: 44, fontFace: "Poppins", color: NAVY, bold: true, lineSpacingMultiple: 1.15, margin: 0
  });
  s.addShape(pres.shapes.RECTANGLE, { x: 1.0, y: 3.8, w: 0.6, h: 0.05, fill: { color: CYAN } });
  s.addText(
    "Es una herramienta multipropósito: validar compliance, guiar agentes de IA, documentar reglas, auditar código, onboarding de devs, y extender a otros dominios.",
    { x: 1.0, y: 4.1, w: 6.5, h: 1.2, fontSize: 16, fontFace: "Open Sans", color: GREY_TEXT, lineSpacingMultiple: 1.5, margin: 0 }
  );
  addFooter(s, 12);
}

// ═══════════════════════════════════════════
// SLIDE 13 · 6 Casos de Uso (grid 3x2)
// ═══════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  addEyebrow(s, "6 CASOS DE USO", 0.64, 1.0);
  s.addText("¿Para qué sirve el SDD Kit?", {
    x: 0.64, y: 1.35, w: 8, h: 0.8,
    fontSize: 32, fontFace: "Poppins", color: NAVY, bold: true, margin: 0
  });

  const useCases = [
    { icon: "✓", title: "Validación de Compliance", desc: "216 tests verifican que el código cumple las 78 reglas de negocio automáticamente.", color: CYAN },
    { icon: "🤖", title: "Guía para Agentes de IA", desc: "AGENTS.md + CLAUDE.md + .cursorrules: el agente lee specs, no adivina reglas.", color: BLUE },
    { icon: "📋", title: "Documentación Ejecutable", desc: "Las reglas viven como código versionado, no como PDFs que se pudren.", color: CYAN },
    { icon: "🔍", title: "Auditoría de Código", desc: "¿Este código cumple las reglas? pytest lo dice en segundos.", color: BLUE },
    { icon: "🚀", title: "Onboarding de Devs", desc: "Un dev nuevo lee los specs y sabe exactamente qué construir sin preguntar.", color: CYAN },
    { icon: "🧩", title: "Extensible a Otros Dominios", desc: "El framework sdd/ es reusable. Copiá las base classes y creá tus propias reglas.", color: BLUE }
  ];

  useCases.forEach((uc, i) => {
    const col = i % 3;
    const row = Math.floor(i / 3);
    const x = 0.64 + col * 3.1;
    const y = 2.4 + row * 1.55;

    // Card
    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w: 2.8, h: 1.35,
      fill: { color: WHITE }, line: { color: RULE, width: 1 },
      shadow: makeShadow()
    });
    // Top accent
    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w: 2.8, h: 0.04,
      fill: { color: uc.color }
    });

    // Icon circle
    s.addShape(pres.shapes.OVAL, {
      x: x + 0.15, y: y + 0.15, w: 0.35, h: 0.35,
      fill: { color: uc.color }
    });
    s.addText(uc.icon, {
      x: x + 0.15, y: y + 0.17, w: 0.35, h: 0.3,
      fontSize: 14, fontFace: "Open Sans", color: WHITE,
      align: "center", margin: 0
    });

    // Title
    s.addText(uc.title, {
      x: x + 0.55, y: y + 0.15, w: 2.1, h: 0.35,
      fontSize: 11, fontFace: "Poppins", color: NAVY, bold: true, margin: 0
    });

    // Description
    s.addText(uc.desc, {
      x: x + 0.15, y: y + 0.5, w: 2.5, h: 0.7,
      fontSize: 9, fontFace: "Open Sans", color: GREY_TEXT,
      lineSpacingMultiple: 1.3, margin: 0
    });
  });

  addFooter(s, 13);
}

// ═══════════════════════════════════════════
// SLIDE 14 · Como librería (módulos)
// ═══════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  addEyebrow(s, "USO 1: COMO LIBRERÍA", 0.64, 1.0);
  s.addText("Importá los módulos\ncomo librería Python", {
    x: 0.64, y: 1.35, w: 8, h: 1.2,
    fontSize: 32, fontFace: "Poppins", color: NAVY, bold: true, lineSpacingMultiple: 1.15, margin: 0
  });

  // Code block
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.64, y: 2.7, w: 8.7, h: 2.5,
    fill: { color: "1E1E2E" }
  });

  const codeLines = [
    { text: "from great_dspy.modules.pre_estimation import StatusTransitionValidator", color: CYAN },
    { text: "", color: WHITE },
    { text: "v = StatusTransitionValidator()", color: WHITE },
    { text: "result = v.forward(\"approved\", \"draft\")", color: WHITE },
    { text: "assert result[\"is_valid\"] is False  # Approved es terminal", color: GREY_NEUTRAL },
    { text: "", color: WHITE },
    { text: "from great_dspy.specs.allocation_specs import calculate_fte_ke", color: CYAN },
    { text: "ke = calculate_fte_ke(fte=1.0, societe_site=\"Horse Spain\", year=\"2024\")", color: WHITE },
    { text: "assert ke == 107.0  # Validación automática de fórmula", color: GREY_NEUTRAL }
  ];

  codeLines.forEach((line, i) => {
    s.addText(line.text, {
      x: 0.8, y: 2.8 + i * 0.28, w: 8.4, h: 0.25,
      fontSize: 11, fontFace: "JetBrains Mono", color: line.color, margin: 0
    });
  });

  // Result box
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.64, y: 5.35, w: 8.7, h: 0.05,
    fill: { color: CYAN }
  });
  s.addText("✅ Sin LLM, sin agentes. Python puro. Los módulos son importables como cualquier librería.", {
    x: 0.64, y: 5.45, w: 8.7, h: 0.4,
    fontSize: 12, fontFace: "Open Sans", color: GREY_TEXT, margin: 0
  });

  addFooter(s, 14);
}

// ═══════════════════════════════════════════
// SLIDE 15 · Como pipeline (blueprint de endpoints)
// ═══════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  addEyebrow(s, "USO 2: COMO PIPELINE", 0.64, 1.0);
  s.addText("Cada pipeline es el blueprint\nde un endpoint", {
    x: 0.64, y: 1.35, w: 8, h: 1.2,
    fontSize: 32, fontFace: "Poppins", color: NAVY, bold: true, lineSpacingMultiple: 1.15, margin: 0
  });

  // Pipeline diagram
  const stages = [
    { name: "SelectionValidator", rules: "§5 Compatibilidad" },
    { name: "PermissionChecker", rules: "§2 Roles" },
    { name: "InductorSelector", rules: "§6-8 Workload" },
    { name: "EstimationCalculator", rules: "§9 Fórmulas" },
    { name: "SaveValidator", rules: "§10 Draft gate" },
    { name: "MonthDistributor", rules: "§9.4 Monthly" },
    { name: "SummaryGenerator", rules: "§10.3 Panel" }
  ];

  const stageW = 1.1;
  const gap = 0.08;
  const startX = 0.64;

  stages.forEach((stage, i) => {
    const x = startX + i * (stageW + gap);

    s.addShape(pres.shapes.RECTANGLE, {
      x, y: 2.7, w: stageW, h: 0.9,
      fill: { color: i % 2 === 0 ? NAVY : CYAN }
    });
    s.addText(stage.name, {
      x: x + 0.05, y: 2.75, w: stageW - 0.1, h: 0.4,
      fontSize: 7, fontFace: "Poppins", color: WHITE, bold: true, align: "center", margin: 0
    });
    s.addText(stage.rules, {
      x: x + 0.05, y: 3.1, w: stageW - 0.1, h: 0.35,
      fontSize: 6, fontFace: "Open Sans", color: i % 2 === 0 ? CYAN_SOFT : NAVY, align: "center", margin: 0
    });

    if (i < stages.length - 1) {
      s.addText("→", {
        x: x + stageW + 0.01, y: 2.9, w: 0.06, h: 0.4,
        fontSize: 10, color: CYAN, align: "center", margin: 0
      });
    }
  });

  // Endpoint mapping
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.64, y: 3.9, w: 8.7, h: 0.8,
    fill: { color: GREY_BG }
  });
  s.addText("POST /api/pre-estimation/save-draft", {
    x: 0.7, y: 3.95, w: 4, h: 0.35,
    fontSize: 12, fontFace: "JetBrains Mono", color: NAVY, bold: true, margin: 0
  });
  s.addText("→ Cada etapa del pipeline = un paso del endpoint", {
    x: 0.7, y: 4.25, w: 8.5, h: 0.3,
    fontSize: 10, fontFace: "Open Sans", color: GREY_TEXT, margin: 0
  });

  // Code example
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.64, y: 4.85, w: 8.7, h: 0.5,
    fill: { color: "1E1E2E" }
  });
  s.addText("ctx = run_pipeline(selected_lines=[line_1, line_2], role=\"Engineer\", metier=\"Backend\")", {
    x: 0.7, y: 4.88, w: 8.5, h: 0.25,
    fontSize: 10, fontFace: "JetBrains Mono", color: CYAN, margin: 0
  });
  s.addText("print(f\"Can save draft: {ctx.can_save_draft}\")  # → True/False según reglas", {
    x: 0.7, y: 5.08, w: 8.5, h: 0.22,
    fontSize: 9, fontFace: "JetBrains Mono", color: GREY_NEUTRAL, margin: 0
  });

  addFooter(s, 15);
}

// ═══════════════════════════════════════════
// SLIDE 16 · Como agente de IA
// ═══════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  addEyebrow(s, "USO 3: COMO AGENTE DE IA", 0.64, 1.0);
  s.addText("El agente lee specs,\nno adivina reglas", {
    x: 0.64, y: 1.35, w: 8, h: 1.2,
    fontSize: 32, fontFace: "Poppins", color: NAVY, bold: true, lineSpacingMultiple: 1.15, margin: 0
  });

  // Flow
  const flow = [
    { label: "CLAUDE.md / .cursorrules", desc: "Entry point del agente", color: CYAN },
    { label: "AGENTS.md", desc: "Instrucciones + reglas de negocio", color: NAVY },
    { label: "great_dspy/specs/", desc: "78 reglas estructuradas", color: CYAN },
    { label: "great_dspy/modules/", desc: "Lógica pura importable", color: NAVY },
    { label: "great_dspy/pipeline/", desc: "Blueprint de endpoints", color: CYAN },
    { label: "tests/", desc: "216 tests de validación", color: NAVY }
  ];

  flow.forEach((step, i) => {
    const y = 2.6 + i * 0.48;

    s.addShape(pres.shapes.RECTANGLE, {
      x: 1.5, y, w: 7, h: 0.4,
      fill: { color: step.color }
    });
    s.addText(step.label, {
      x: 1.6, y: y + 0.05, w: 3.5, h: 0.3,
      fontSize: 12, fontFace: "Poppins", color: WHITE, bold: true, margin: 0
    });
    s.addText(step.desc, {
      x: 5.2, y: y + 0.05, w: 3.2, h: 0.3,
      fontSize: 10, fontFace: "Open Sans", color: step.color === NAVY ? CYAN_SOFT : NAVY, margin: 0
    });

    if (i < flow.length - 1) {
      s.addText("↓", {
        x: 4.8, y: y + 0.38, w: 0.4, h: 0.1,
        fontSize: 12, color: CYAN, align: "center", margin: 0
      });
    }
  });

  // Key insight
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.64, y: 5.35, w: 8.7, h: 0.05,
    fill: { color: CYAN }
  });
  s.addText("💡 Sin AGENTS.md → el agente adivina. Con AGENTS.md → el agente ejecuta specs.", {
    x: 0.64, y: 5.45, w: 8.7, h: 0.4,
    fontSize: 12, fontFace: "Open Sans", color: GREY_TEXT, margin: 0
  });

  addFooter(s, 16);
}

// ═══════════════════════════════════════════
// SLIDE 17 · Como documentación + auditoría
// ═══════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  addEyebrow(s, "USO 4 Y 5: DOCUMENTACIÓN + AUDITORÍA", 0.64, 1.0);
  s.addText("Docs que no se pudren +\nAuditoría en segundos", {
    x: 0.64, y: 1.35, w: 8, h: 1.2,
    fontSize: 32, fontFace: "Poppins", color: NAVY, bold: true, lineSpacingMultiple: 1.15, margin: 0
  });

  // Left: Documentation
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.64, y: 2.6, w: 4, h: 2.5,
    fill: { color: WHITE }, line: { color: RULE, width: 1 }
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.64, y: 2.6, w: 4, h: 0.04,
    fill: { color: CYAN }
  });
  s.addText("📋 Documentación Ejecutable", {
    x: 0.8, y: 2.75, w: 3.7, h: 0.4,
    fontSize: 14, fontFace: "Poppins", color: NAVY, bold: true, margin: 0
  });
  const docPoints = [
    "Las reglas viven como código versionado",
    "Cada regla tiene ID, severity, criterios",
    "Los tests son la documentación que se ejecuta",
    "Si el test falla, la doc está desactualizada",
    "Git history = historial de cambios de reglas"
  ];
  docPoints.forEach((pt, i) => {
    s.addText("→ " + pt, {
      x: 0.8, y: 3.2 + i * 0.32, w: 3.7, h: 0.28,
      fontSize: 10, fontFace: "Open Sans", color: GREY_TEXT, margin: 0
    });
  });

  // Right: Audit
  s.addShape(pres.shapes.RECTANGLE, {
    x: 5.3, y: 2.6, w: 4, h: 2.5,
    fill: { color: WHITE }, line: { color: RULE, width: 1 }
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: 5.3, y: 2.6, w: 4, h: 0.04,
    fill: { color: BLUE }
  });
  s.addText("🔍 Auditoría de Código", {
    x: 5.45, y: 2.75, w: 3.7, h: 0.4,
    fontSize: 14, fontFace: "Poppins", color: NAVY, bold: true, margin: 0
  });
  const auditPoints = [
    "¿Este PR cumple las reglas de negocio?",
    "pytest tests/ → respuesta en segundos",
    "216 tests = 78 reglas verificadas",
    "CI/CD integration: bloquea merge si falla",
    "Compliance report automático"
  ];
  auditPoints.forEach((pt, i) => {
    s.addText("→ " + pt, {
      x: 5.45, y: 3.2 + i * 0.32, w: 3.7, h: 0.28,
      fontSize: 10, fontFace: "Open Sans", color: GREY_TEXT, margin: 0
    });
  });

  addFooter(s, 17);
}

// ═══════════════════════════════════════════
// SLIDE 18 · Extensible a otros dominios
// ═══════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  addEyebrow(s, "USO 6: EXTENSIBLE A OTROS DOMINIOS", 0.64, 1.0);
  s.addText("El framework sdd/\nes reutilizable", {
    x: 0.64, y: 1.35, w: 8, h: 0.8,
    fontSize: 32, fontFace: "Poppins", color: NAVY, bold: true, margin: 0
  });

  // Before (GREAT)
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.64, y: 2.4, w: 3.8, h: 2.8,
    fill: { color: NAVY }
  });
  s.addText("SDD Kit GREAT", {
    x: 0.8, y: 2.5, w: 3.5, h: 0.4,
    fontSize: 14, fontFace: "Poppins", color: CYAN, bold: true, margin: 0
  });
  const greatContent = [
    "great_dspy/specs/",
    "  pre_estimation_specs.py (17 reglas)",
    "  estimation_review_specs.py (10)",
    "  allocation_specs.py (16)",
    "  final_review_specs.py (10)",
    "  management_view_specs.py (8)",
    "  transversal_specs.py (13)",
    "",
    "great_dspy/modules/ (30 módulos)",
    "great_dspy/pipeline/ (6 pipelines)",
    "tests/ (216 tests)"
  ];
  greatContent.forEach((line, i) => {
    s.addText(line, {
      x: 0.8, y: 2.95 + i * 0.2, w: 3.5, h: 0.18,
      fontSize: 8, fontFace: "JetBrains Mono", color: i === 0 || i === 7 ? CYAN_SOFT : WHITE, margin: 0
    });
  });

  // Arrow
  s.addText("→", {
    x: 4.6, y: 3.5, w: 0.5, h: 0.5,
    fontSize: 30, color: CYAN, align: "center", margin: 0
  });

  // After (Tu dominio)
  s.addShape(pres.shapes.RECTANGLE, {
    x: 5.3, y: 2.4, w: 4, h: 2.8,
    fill: { color: "1E1E2E" }
  });
  s.addText("Tu Dominio", {
    x: 5.45, y: 2.5, w: 3.7, h: 0.4,
    fontSize: 14, fontFace: "Poppins", color: CYAN, bold: true, margin: 0
  });
  const tuContenido = [
    "sdd/ ← Copiar tal cual (base framework)",
    "",
    "domains/tu_dominio/specs/",
    "  tus_reglas.py",
    "",
    "domains/tu_dominio/modules/",
    "  tus_modulos.py",
    "",
    "domains/tu_dominio/pipeline/",
    "  tu_pipeline.py",
    "",
    "tests/ (tus tests)"
  ];
  tuContenido.forEach((line, i) => {
    s.addText(line, {
      x: 5.45, y: 2.95 + i * 0.2, w: 3.7, h: 0.18,
      fontSize: 8, fontFace: "JetBrains Mono", color: i === 0 || i === 2 || i === 5 || i === 8 ? CYAN : GREY_NEUTRAL, margin: 0
    });
  });

  // Steps
  s.addText("6 pasos para extender:", {
    x: 0.64, y: 5.35, w: 8.7, h: 0.3,
    fontSize: 11, fontFace: "Poppins", color: NAVY, bold: true, margin: 0
  });
  const steps = [
    "1. Copiá sdd/ a tu proyecto",
    "2. Creá domains/tu_dominio/specs/ con tus reglas",
    "3. Creá domains/tu_dominio/modules/ con tu lógica",
    "4. Creá domains/tu_dominio/pipeline/ con tu orquestación",
    "5. Creá tests/ que verifiquen tus reglas",
    "6. Los módulos base se heredan de sdd/"
  ];
  steps.forEach((step, i) => {
    s.addText(step, {
      x: 0.64 + (i % 3) * 3.1, y: 5.65 + Math.floor(i / 3) * 0.25, w: 2.9, h: 0.22,
      fontSize: 8, fontFace: "Open Sans", color: GREY_TEXT, margin: 0
    });
  });

  addFooter(s, 18);
}

// ═══════════════════════════════════════════
// SLIDE 19 · Resumen comparativo
// ═══════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  addEyebrow(s, "RESUMEN", 0.64, 1.0);
  s.addText("Un kit, seis formas de usarlo", {
    x: 0.64, y: 1.35, w: 8, h: 0.8,
    fontSize: 32, fontFace: "Poppins", color: NAVY, bold: true, margin: 0
  });

  const summary = [
    { uso: "Librería", cuándo: "Necesitás lógica de negocio importable", stack: "Python puro" },
    { uso: "Pipeline", cuándo: "Necesitás orquestar validaciones en orden", stack: "DSPy modules" },
    { uso: "Agente IA", cuándo: "Querés que el agente cumpla reglas sin adivinar", stack: "AGENTS.md + specs" },
    { uso: "Documentación", cuándo: "Querés docs versionadas y testeables", stack: "YAML + Markdown" },
    { uso: "Auditoría", cuándo: "Necesitás verificar compliance en CI/CD", stack: "pytest + 216 tests" },
    { uso: "Extensión", cuándo: "Querés aplicar SDD a otro dominio", stack: "sdd/ base framework" }
  ];

  // Table
  const tableData = [
    ["Uso", "Cuándo", "Stack"].map(h => ({
      text: h,
      options: { fill: { color: NAVY }, color: WHITE, bold: true, fontFace: "Poppins", fontSize: 11, align: "center" }
    })),
    ...summary.map((row, ri) => [
      { text: row.uso, options: { fill: { color: ri % 2 === 0 ? WHITE : GREY_BG }, color: NAVY, bold: true, fontFace: "Poppins", fontSize: 12, align: "center" } },
      { text: row.cuándo, options: { fill: { color: ri % 2 === 0 ? WHITE : GREY_BG }, color: GREY_TEXT, fontFace: "Open Sans", fontSize: 10, align: "left" } },
      { text: row.stack, options: { fill: { color: ri % 2 === 0 ? WHITE : GREY_BG }, color: GREY_TEXT, fontFace: "Open Sans", fontSize: 10, align: "center" } }
    ])
  ];

  s.addTable(tableData, {
    x: 0.64, y: 2.3, w: 8.7, h: 3.0,
    colW: [1.5, 4.5, 2.7],
    border: { pt: 0.5, color: RULE },
    margin: 0
  });

  addFooter(s, 19);
}

// ─── Write file ───
const outPath = path.join(__dirname, "GREAT_SDD_Kit_Casos_de_Uso.pptx");
pres.writeFile({ fileName: outPath }).then(() => {
  console.log("Created:", outPath);
}).catch(err => {
  console.error("Error:", err);
  process.exit(1);
});
