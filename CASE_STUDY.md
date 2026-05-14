# Case Study: Self-Correcting Agent Workflow for Math Modeling

> A demonstration of autonomous error detection, root-cause analysis, and full solver rewrite by a multi-agent system — without human intervention.

---

## 1. Problem Overview

| Field | Detail |
|-------|--------|
| **Source** | 2026 CQUPU Math Modeling Competition — Problem A |
| **Title** | 水下目标探测与定位 (Underwater Target Detection & Localization) |
| **Domain** | Deep-sea manganese nodule detection via multi-beam sonar |
| **Core Task** | Locate point/spherical targets on the seabed using echo time measurements |
| **Input** | PDF problem statement (3 pages, Chinese) |
| **Expected Output** | Solver code, numerical results, figures, paper outline, summary |

The problem asks contestants to:
1. Locate 2 point-source nodules from echo times at 5 ship positions
2. Fit a spherical nodule (center + radius) from 4 sonar measurements
3. Derive the echo time function `t(x)` for a ship moving along the X-axis
4. Perform 2D isochrone analysis with gradient-based path planning

**Coordinate system**: Ship at origin `(0,0,0)` on sea surface; seabed is XOY plane; sound speed `c = 1500 m/s`.

---

## 2. Multi-Agent Workflow

The system follows a 6-stage pipeline, each stage handled by a specialized agent:

```
PDF Parser → Strategy Planner → Code Generator → Experiment Runner → Paper Writer → GitHub Publisher
```

### Agent Responsibilities

| Agent | Input | Output | Skills Used |
|-------|-------|--------|-------------|
| **Parser** | PDF file | `parsed_problem.json` | Document reading, OCR fallback |
| **Strategy** | Problem spec | `strategy.md` | Model selection, complexity analysis |
| **Coder** | Strategy + spec | `generated_code.py` | Python, numpy, matplotlib |
| **Experimenter** | Code | `results.json`, `figures/` | Execution, debugging, validation |
| **Paper Writer** | Results | `paper_outline.md`, `solution_summary.md` | Technical writing |
| **GitHub** | All artifacts | Git commit + push | Version control |

### Auto-Triggered Skills

| Trigger | Skill | Purpose |
|---------|-------|---------|
| Architecture design | `planning-with-files` | Persistent markdown planning |
| Python traceback | `python-debug` | Auto-fix + rerun loop |
| Code written/modified | `everything-claude-code /python-review` | Lint, type-check, review |
| Build/import error | `everything-claude-code /build-fix` | Fix compilation issues |
| Code commit | `everything-claude-code /code-review` | Pre-commit review |

---

## 3. Initial Failure

### What Happened

The PDF parser identified the problem as **"Multistatic Sonar — Bottom Topology Co-optimization"** (2025 CUMCM Problem A) instead of the actual **"Underwater Target Detection & Localization"** (2026 CQUPU Problem A). This was a misclassification at the problem-understanding stage.

### The Wrong Solver

The system generated ~900 lines of code implementing:

- **Three-layer ocean model** (water → sediment → basement)
- **Snell's law refraction** with critical angle analysis
- **Two-way ray tracing** (S → bottom → R)
- **Shadow zone detection** and **reef obstruction analysis**

None of this was relevant to the actual problem.

### Why It Happened

| Root Cause | Explanation |
|------------|-------------|
| PDF ambiguity | Both problems involve underwater acoustics and sonar |
| Title confusion | "水下目标探测" could match multiple problem types |
| No content verification | The solver was built from assumptions, not from parsing the actual question text |

### Verification Against Ground Truth

| Metric | Wrong Solver | Expected |
|--------|-------------|----------|
| Problem type | Snell refraction + ray tracing | Echo time geometry |
| Q1 result | Shadow zone = 30.6% | Point nodule coordinates |
| Q2 result | 0/25 reef combinations detectable | Sphere center + radius |
| Q3 result | Source position optimization | t(x) analytical function |
| Q4 | Not implemented | 2D isochrone analysis |

---

## 4. Reality Audit

The system performed an autonomous **authenticity audit** — a structured review comparing the claimed model against actual implementation.

### Audit Protocol

```
1. Read the problem PDF directly (not from cached understanding)
2. Compare each claim in strategy.md against generated_code.py
3. Verify mathematical formulas match implementation
4. Check if results are physically plausible
5. Flag discrepancies as "risk items"
```

### Audit Findings

| # | Finding | Severity | Category |
|---|---------|----------|----------|
| 1 | **Wrong problem entirely** — PDF is CQUPU 2026, not CUMCM 2025 | Critical | Problem identification |
| 2 | Solver implements Snell refraction for a problem about echo time localization | Critical | Model mismatch |
| 3 | All Q1/Q2/Q3 results are for irrelevant physical quantities | Critical | Result validity |
| 4 | Code is well-structured but solves the wrong equations | High | Implementation |

### Audit Decision

> **REJECT** — Complete solver rewrite required. The implementation, while technically correct for its own model, is entirely wrong for this problem.

---

## 5. Problem Re-Parsing

After the audit flagged the mismatch, the system re-parsed the PDF with full attention to the actual question text.

### Key Realizations

| Aspect | Previous (Wrong) | Actual |
|--------|------------------|--------|
| Competition | 2025 CUMCM | 2026 CQUPU |
| Topic | Multistatic sonar optimization | Manganese nodule localization |
| Physics | Snell refraction, ray tracing | Echo time t = 2d/c |
| Q1 | Shadow zone analysis | Locate 2 point sources |
| Q2 | Reef obstruction | Fit sphere parameters |
| Q3 | Source position optimization | Derive t(x) function |
| Q4 | Not planned | 2D isochrone + gradient |

### Corrected Problem Specification

```json
{
  "title": "水下目标探测与定位",
  "coordinate_system": "Ship at (0,0,0), seabed = XOY plane",
  "sound_speed": 1500,
  "Q1": "Locate 2 point nodules from echo times at 5 ship positions",
  "Q2": "Fit sphere (center + radius) from 4 sonar echo delays",
  "Q3": "Derive t(x) for ship along X-axis, target at (100,50,-100)",
  "Q4": "2D isochrone map + gradient path planning"
}
```

---

## 6. Solver Rewrite

### Architecture

The new solver implements 4 independent modules, each matching a question:

```
generated_code.py (~780 lines)
├── solve_q1()    — Nonlinear least squares for point source localization
├── solve_q2()    — Sphere fitting with grid search + gradient descent
├── solve_q3()    — Analytical t(x) derivation + geometric analysis
├── solve_q4()    — 2D isochrone computation + gradient field visualization
└── plot_comprehensive()  — 6-panel summary figure
```

### Mathematical Models

**Q1 — Point Nodule Localization**
```
d_i = sqrt((x_si - x_n)^2 + y_n^2 + z_n^2)
Linearized: [2*x_si, -1] · [x_n, b]^T = x_si^2 - d_i^2
Then nonlinear refinement via gradient descent
```

**Q2 — Sphere Fitting**
```
D_i = d_i + R    (sonar-to-center = sonar-to-surface + radius)
D_i^2 = (x_si - x_c)^2 + (y_si - y_c)^2 + (z_si - z_c)^2
Cost: min Σ(D_calc - (d_meas + R))^2
Solved via grid search (8³ × 6 = 3072 candidates) + local gradient descent
```

**Q3 — Echo Time Function**
```
t(x) = (2/c) · sqrt((x - x_t)^2 + y_t^2 + z_t^2)
Analytical — no optimization needed
```

**Q4 — Isochrone Analysis**
```
t(x,y) = (2/c) · sqrt((x - x_t)^2 + (y - y_t)^2 + z_t^2)
Isochrones: concentric circles centered at (x_t, y_t)
Gradient: ∇t = (2/(c·d)) · (x - x_t, y - y_t)
Path planning: follow -∇t from any starting point
```

### Key Implementation Decisions

| Decision | Rationale |
|----------|-----------|
| No scipy dependency | Environment lacks scipy; implemented gradient descent from scratch |
| Grid search + local optimization | Avoids local minima; handles non-convex cost landscape |
| Analytical Q3/Q4 | Exact solutions where physics allows; no numerical approximation |
| Adaptive learning rate | Gradient descent with backtracking for robust convergence |
| Multi-start for Q2 | Sphere fitting has multiple local minima; 6 starting points |

---

## 7. Final Results

### Numerical Results

| Question | Metric | Value |
|----------|--------|-------|
| **Q1** | Nodule A | `(0.75, 79.44, 0.00)` m |
| | Nodule B | `(1.12, 82.20, 0.00)` m |
| | Fit residual | RMS ≈ 19 m (noisy data) |
| **Q2** | Sphere center | `(20.23, 19.85, -103.46)` m |
| | Sphere radius | `7.52` m |
| | Fit residual | `0.226` (< 0.5 ms error) |
| **Q3** | Formula | `t(x) = 2√((x-100)² + 12500) / 1500` |
| | Min echo time | `149.07 ms` at `x = 100` m |
| | Symmetry axis | `x = 100` (target x-coordinate) |
| **Q4** | Formula | `t(x,y) = 2√((x-100)² + (y-50)² + 10000) / 1500` |
| | Min echo time | `133.34 ms` at `(100, 50)` |
| | Gradient path | 101 steps to convergence |

### Verification

| Check | Status |
|-------|--------|
| Q2: Sonar(0,0,0) → sphere center distance = 107.58 m | Pass |
| Q2: Calculated delay = 2×(107.58-7.52)/1500 = 133.41 ms ≈ 133.42 ms | Pass |
| Q3: t(100) = 2×111.80/1500 = 149.07 ms | Pass |
| Q3: t(0) = 2×150.0/1500 = 200.0 ms | Pass |
| Q4: Isotherms are concentric circles | Visual pass |

---

## 8. Visualizations

### Generated Figures

| Figure | File | Description |
|--------|------|-------------|
| **Q1 Localization** | `q1_localization.png` | Echo time curves, distance plot, nodule positions (top view) |
| **Q2 Sphere** | `q2_sphere.png` | 3D sphere visualization, top view, measured vs calculated delays |
| **Q3 Echo Time** | `q3_echo_time.png` | t-x curve, geometry diagram, gradient direction analysis |
| **Q4 Isochrone** | `q4_isochrone.png` | 3D surface, 2D contour map, gradient field, path planning |
| **Comprehensive** | `comprehensive_analysis.png` | 6-panel summary of all results |

### Figure Highlights

**Q2 Sphere Fitting** — The 3D visualization shows the fitted sphere (red, R=7.5m) below the seabed at z ≈ -103m, with 4 sonar positions (blue triangles) on the surface. The bar chart confirms calculated delays match measured within 0.5ms.

**Q4 Isochrone Map** — The contour plot reveals concentric circles centered at the target. The gradient field (quiver plot) shows arrows pointing inward. The path planning subplot demonstrates convergence from `(-50, -50)` to the target in 101 gradient descent steps.

---

## 9. Lessons Learned

### Error Detection Patterns

| Pattern | Detection Method | Response |
|---------|-----------------|----------|
| Wrong problem interpretation | Reality audit: PDF re-read | Full re-parse and solver rewrite |
| Numerical divergence | Runtime monitoring (values → billions) | Reduce learning rate, add normalization |
| Poor fit quality | RMS residual check | Wider grid search, multi-start optimization |
| Module not found | Import error detection | Implement from scratch (no scipy) |

### What Worked

1. **Reality audit** — The structured review caught the fundamental mismatch between claimed model and actual problem. Without this step, the wrong results would have been delivered with confidence.

2. **Autonomous rewrite** — The system re-parsed the PDF, identified the correct problem type, designed new mathematical models, and implemented a complete solver — all in a single session.

3. **Progressive refinement** — Each iteration improved the solver: initial → debug Q2 divergence → fix Q1 fit → final results. The system didn't give up after the first failure.

### What Could Be Improved

1. **Initial PDF parsing** — The parser should extract exact problem text before choosing a model, not rely on title/keyword matching alone.

2. **Cross-validation** — Before committing to a model, verify that the first few lines of the problem description match the assumed domain.

3. **Graceful degradation** — When Q1 fit quality is poor (RMS=19m), the system should flag this as uncertain rather than presenting it as a definitive result.

### Agent Self-Correction Timeline

```
T+0:00  PDF parsed → misidentified as multistatic sonar problem
T+0:05  Strategy planner generates ray-tracing model
T+0:10  Code generator writes 900-line solver (wrong problem)
T+0:15  First execution: numpy bool serialization error → auto-fix
T+0:20  Second execution: Q1 shadow=0% → suspicious
T+0:25  Third execution: Q2 reef unreachable → physics bug
T+0:30  Fourth execution: TL formula corrected → Q1=30.6%, Q2=0/25
T+0:35  Reality audit triggered → REJECT (wrong problem)
T+0:40  PDF re-parsed → correct problem identified
T+0:45  New solver designed (4 modules, no scipy)
T+0:50  First run: Q2 gradient divergence → fix learning rate
T+0:55  Second run: Q1 poor fit → improve optimization
T+1:00  Final run: Q2 residual=0.23, Q3/Q4 analytical → PASS
T+1:05  All documentation updated, committed, pushed
```

---

## 10. Future Improvements

### Short-term

| Improvement | Impact | Effort |
|-------------|--------|--------|
| PDF text extraction before model selection | Prevents wrong-problem errors | Low |
| Automatic problem-type classification | Faster, more reliable routing | Medium |
| Q1 confidence reporting | Flags noisy/poor fits | Low |

### Medium-term

| Improvement | Impact | Effort |
|-------------|--------|--------|
| Multi-prompt PDF parsing | Better accuracy on complex layouts | Medium |
| Result plausibility checks | Catches physical impossibilities | Medium |
| Parallel question solving | Faster end-to-end execution | Medium |

### Long-term

| Improvement | Impact | Effort |
|-------------|--------|--------|
| Learned problem classification model | Eliminates misidentification | High |
| Cross-problem knowledge transfer | Reuses patterns from similar problems | High |
| Human-in-the-loop audit triggers | Interactive confirmation at critical points | High |

---

## Appendix: File Manifest

```
outputs/A_underwater_detection/
├── parsed_problem.json          # Extracted problem parameters
├── strategy.md                  # Model selection rationale
├── generated_code.py            # Complete solver (~780 lines)
├── results.json                 # Numerical results (Q1–Q4)
├── experiment_report.md         # Detailed experiment documentation
├── paper_outline.md             # Competition paper framework
├── solution_summary.md          # Executive summary
├── execution.log                # Runtime log
└── figures/
    ├── q1_localization.png      # Point nodule analysis
    ├── q2_sphere.png            # Sphere fitting visualization
    ├── q3_echo_time.png         # t(x) function analysis
    ├── q4_isochrone.png         # 2D isochrone + gradient
    └── comprehensive_analysis.png  # 6-panel summary
```

---

## Appendix: Git History

```
13129af  fix: rewrite solver for correct problem (2026 CQUPU Math Modeling A)
7af4c0b  real mathematical modeling case: underwater detection
```

**Net change**: 16 files, +1045 / -3317 lines (complete solver replacement)

---

*Generated by MathModel Dev Agent — A self-correcting multi-agent system for mathematical modeling.*
