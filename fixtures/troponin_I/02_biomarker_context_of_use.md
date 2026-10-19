# Biomarker Context of Use

- **Document:** Biomarker Context of Use (CoU)
- **Study:** BM-2026-01
- **Version:** 1.0
- **Asserted by:** Sponsor Biomarker Review Board
- **Assertion date:** 2026-09-01
- **Status:** Approved

## 1. Biomarker identity

- **Analyte:** Cardiac troponin I
- **Entity type:** protein
- **Measured change:** **increased** level (elevation above the reference limit)
- **Specimen matrix:** serum

## 2. Context

- **Condition:** Acute myocardial infarction
- **BEST biomarker role:** **diagnostic** (primary), with a secondary **prognostic** claim: an elevated
  admission value predicts adverse outcome (death, MI or revascularisation) within 30 days
- **Intended context of use:** early diagnosis and risk stratification of acute myocardial
  infarction in adults presenting to a chest-pain unit with suspected AMI.

Note: the role is only interpretable together with the condition — "troponin I" alone is not
a biomarker; *increased troponin I in the context of suspected acute myocardial infarction* is.

## 3. Assay dependence

This context is **specific to the assay** named in `03_assay_instructions_for_use.md`
(Troponin I Ultra on the ADVIA Centaur XP). Cardiac troponin I is **not standardised across
manufacturers** and has no certified primary reference material, so decision thresholds do
**not** transfer to another assay or platform.

## 4. Interpretation / decision rule

A diagnosis of acute myocardial infarction is established when **both** conditions hold:

1. a troponin I value **greater than 0.04 ng/mL** (the assay's 99th-percentile upper reference
   limit), **and**
2. a **rise or fall of ≥ 30 %** in the troponin I value **within 6 hours** after admission.

Supporting parameters of the rule:

- applied reference limit: 99th percentile (upper), 0.04 ng/mL
- relative-change threshold: 30 %
- relative-change window: 6 hours
- direction: rise or fall

**Repeat criteria:** if the admission value lies between the limit of detection and the
reference limit, the sample is repeated at 3 and 6 hours.

**Reporting convention:** concentrations in ng/mL to 3 decimals; values below the limit of
quantitation are reported as "<LLOQ" and excluded from numeric summaries.

## 5. Evidence

- **Primary evidence:** Keller T, Zeller T, Peetz D, et al. Sensitive troponin I assay in
  early diagnosis of acute myocardial infarction. *N Engl J Med.* 2009;361(9):868–877.
- **Supporting:** the 99th-percentile reference limit was derived in the Gutenberg Heart
  Study population (n = 5000).

## 6. Caveats

- Concentrations rise with age and falling renal function independently of acute injury.
- The 30 % relative-change threshold is assay-specific (derived from this assay's imprecision),
  not a biological constant.
- The reference limit derives from the named reference population; a different age or sex
  distribution shifts the false-positive rate.
