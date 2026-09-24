# Clinical AI Safety, Autonomy & Governance

## Guardrails, Invariants, and Ethical Boundaries for THALI × P.L.A.T.E.

---

## 1. The Core Safety Doctrine

In medical software, unconstrained generative AI poses critical clinical hazards: hallucinated drug dosages, false reassurance during severe hypoglycemia, and erratic dietary advice. **THALI × P.L.A.T.E.** implements a multi-layered safety firewall:

$$\text{Ambient Capture} \longrightarrow \text{Strict Guardrails} \longrightarrow \text{Deterministic Math} \longrightarrow \text{Human Clinician Review}$$

---

## 2. Prohibited AI Behaviors

Under no circumstances may any AI model, adapter, or agent:
1. **Diagnose Autonomously**: Never state that a patient has diabetes, prediabetes, ketoacidosis, or neuropathy.
2. **Prescribe Medication**: Never recommend initiating insulin, metformin, sulfonylureas, GLP-1 agonists, or SGLT2 inhibitors.
3. **Titrate Medication**: Never advise a patient to adjust their insulin units, timing, or oral tablet quantity.
4. **Modify Clinician Plans**: An `AIReviewArtifact` has zero authority to alter a `MedicationPlan`.
5. **Estimate Nutrition Speculatively**: Never allow an LLM to hallucinate carbohydrate numbers.

---

## 3. The 3-Role Authorization Boundary

The runtime environment permits only three human roles:
- **`PATIENT`**: Owns telemetry logging; confirms/rejects observations; views tasks.
- **`CAREGIVER`**: Acts on delegated authority with verified relationship scopes (viewing telemetry, assisting logs).
- **`DOCTOR`**: Holds exclusive clinical authority to approve recommendations, modify treatment plans, and diagnose.

*Admin Web is completely removed from the current product scope.*

---

## 4. Deterministic Clinical Mathematics

All clinical indices are computed deterministically prior to any AI engagement:
- **Time in Range (TIR)**: $\% \text{ readings between } 70-180\text{ mg/dL}$ (Target $> 70\%$).
- **Time Below Range (TBR)**: $\% \text{ readings } < 70\text{ mg/dL}$ (Target $< 4\%$).
- **Time Above Range (TAR)**: $\% \text{ readings } > 180\text{ mg/dL}$.
- **Coefficient of Variation (CV%)**: $\frac{\text{SD}}{\text{Mean}} \times 100$ ($\le 36\%$ = stable glycemic control).
- **Glucose Management Indicator (GMI)**: $3.31 + (0.02392 \times \text{Mean mg/dL})$ (Bergman et al., 2018).
- **Estimated A1c (eA1c)**: $\frac{\text{Mean mg/dL} + 46.7}{28.7}$ (Nathan et al., 2008 ADAG).

---

## 5. Human-in-the-Loop Review Workflow

```
[ AI Evidence Package ]
        │ (Deterministic Glycemic Metrics + Longitudinal Trends)
        ▼
[ SarvamAIProvider / ProductionModelProvider ]
        │ Generates draft SOAP note
        ▼
[ AIReviewArtifact: Status = GENERATED ]
        │
        ▼ Doctor P.L.A.T.E. Clinician Interface
[ Licensed Physician Review ]
        │
        ├── [ APPROVE ] ──> Generates Patient Care Tasks & Plan Updates
        ├── [ EDIT ]    ──> Doctor edits text; records Doctor as author
        └── [ REJECT ]  ──> Terminal state; audit record stored
```
An artifact in `GENERATED` state has **zero patient-facing visibility**. Only approved artifacts generate care tasks.
