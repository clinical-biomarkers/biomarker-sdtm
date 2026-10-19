---
doc: best-definitions
version: 2.0.0
status: current
updated: 2026-10-19
source: FDA-NIH BEST glossary; Keller et al. NEJM 2009 (troponin example)
---

# BEST biomarker roles

## Contents

1. Definition and the seven roles
2. How to assign a role
3. What each role must carry (record set and SDTM)
4. Prognostic vs predictive
5. Worked example: troponin I

> FDA-NIH Biomarker Working Group. *BEST (Biomarkers, EndpointS, and other Tools) Resource*.
> https://www.ncbi.nlm.nih.gov/books/NBK326791/ · glossary: https://www.ncbi.nlm.nih.gov/books/NBK338448/

## 1. Definition and the seven roles

A **biomarker** is a defined characteristic measured as an indicator of normal biological
processes, pathogenic processes, or responses to an exposure or intervention. It is not a measure of
how a person feels, functions or survives.

| Role (BMKB value, lowercase) | Definition |
|---|---|
| `susceptibility/risk` | Indicates the potential for developing a disease in someone who does not currently have it |
| `diagnostic` | Detects or confirms the presence of a disease, or identifies a subtype |
| `prognostic` | Identifies the likelihood of a clinical event, recurrence or progression in people who have the disease |
| `predictive` | Identifies people more likely than similar people without the biomarker to respond (favourably or not) to a specific product or exposure |
| `monitoring` | Measured repeatedly to assess the status of a disease, or evidence of exposure to or effect of a product |
| `safety` | Measured before or after an exposure to indicate the likelihood, presence or extent of toxicity |
| `pharmacodynamic/response` | Shows that a biological response has occurred in someone exposed to a product |

BMKB `best_biomarker_role[].role` uses the lowercase value; SDTM `BM.BMROLE` uses it uppercased
(`susceptibility/risk` → `SUSCEPTIBILITY/RISK`).

## 2. How to assign a role

- Take the role from what the **study documents claim**: the context-of-use statement first, then
  the protocol's objectives and endpoints, then the cited evidence. Biology alone does not fix a role.
- **List every role the documents support**, one `best_biomarker_role` entry each. The converter
  writes one BM row per role.
- **Never infer a role from the sampling pattern.** Serial draws inside a diagnostic rule (a rise or
  fall within hours) are still diagnostic; monitoring means tracking disease status or treatment
  effect over the course of care.
- Each role needs the annotations in §3. If the documents lack them, the role is not supported:
  leave it out and say why in the hand-over report.

## 3. What each role must carry

| Role | Measurement pattern | Must be annotated | tBCO / rBCO consequence | SDTM beyond LB (index: `sdtmig-guide.md` §2) |
|---|---|---|---|---|
| Diagnostic | Single draw, or a short serial series only when the rule uses a delta | Condition, reference population, decision limit and its direction | A tBCO rule with `role: diagnostic`; `serial_required` only if the rule needs it | CE or MH for the adjudicated diagnosis; TV for planned time points |
| Monitoring | Repeated over disease or treatment, at least two visits | Anchor (diagnosis or treatment start), visit schedule, change metric and meaningful change | Measurements carry VISITNUM; one rBCO per subject per run | TV / SV; EX when monitoring a treatment; RS for response |
| Prognostic | Usually baseline, in people with the condition | Outcome event and time horizon; population with the disease | A tBCO rule with `role: prognostic` naming the outcome and window; no treatment comparison | CE / DS / DD for the outcome; MH for the existing condition |
| Predictive | Pre-treatment baseline | Product, comparator arm, evidence of a treatment-by-biomarker interaction | tBCO rule names the product; measurements before first dose | DM ARM/ACTARM, TA, EX; GF when the marker is genomic |
| Safety | Before and after exposure | Product or agent; toxicity threshold or grade | Time points relative to dosing; grade criteria in the rule | EX, AE, LBTOXGR; RELREC from LB to AE |
| Pharmacodynamic / response | Pre-dose and post-dose, timed to the dose | Product, dose, time from dose | LBTPT / LBELTM / LBTPTREF on the measurements | EX; PC/PP when exposure is measured |
| Susceptibility / risk | Usually once, in people without the condition | Future condition and time window; germline vs somatic | Often no serial sampling; specimen may be DNA | GF for nucleic-acid markers; MH to show absence of disease |

## 4. Prognostic vs predictive

- Prognostic markers predict outcome **regardless of treatment** and can come from observational data.
- Predictive markers need a **treatment-by-biomarker interaction**, normally from a randomised
  comparison. Without a comparator arm, do not assign `predictive`.
- A marker can be both; record both roles when the evidence supports both.

## 5. Worked example: troponin I

Keller et al., *N Engl J Med* 2009;361:868-77 (PMID 19710485) studied 1,818 patients with suspected
acute myocardial infarction, with blood drawn at admission, 3 h and 6 h. It reports diagnostic
accuracy (AUC, sensitivity, specificity) and, as a secondary analysis, the risk of adverse outcome at
30 days. The study protocol (fixture 01) names the same two objectives.

- `diagnostic`, condition AMI (DOID:9408): `Value > 0.04 ng/mL AND rise or fall >= 30% within 6 h`
- `prognostic`, same population: `Admission value > 0.04 ng/mL` for death, MI or
  revascularisation within 30 days

It is **not** a monitoring biomarker. The serial draws belong to the diagnostic rule.
