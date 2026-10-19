===============================================================================
TROPONIN I BIOMARKER PACKAGE - README
===============================================================================

A worked example of a cardiac troponin I biomarker in five files: what the
biomarker is, how it is measured, what happened when it was measured for each
of two subjects, and the study data.

Analyte : cardiac troponin I (TNNI3, UniProtKB P19429)
Assay   : TnI-Ultra on the Siemens ADVIA Centaur XP
Context : acute myocardial infarction (DOID:5844); roles diagnostic and prognostic


-------------------------------------------------------------------------------
FILES
-------------------------------------------------------------------------------

Troponin_I_biomarkerKB.json      what the biomarker is
Troponin_I_tBCO.json             how to measure it
Troponin_I_patient1_rBCO.json    the analytical run for subject 001
Troponin_I_patient2_rBCO.json    the analytical run for subject 002
Troponin_I_SDTM.xlsx              the study data


-------------------------------------------------------------------------------
Troponin_I_biomarkerKB.json
-------------------------------------------------------------------------------

The BiomarkerKB provider-side submission record for troponin I. It describes the biomarker itself, independently of
any assay or patient: the entity being measured, its controlled-vocabulary
term, its BEST biomarker role and the condition that role applies to.


-------------------------------------------------------------------------------
TEMPLATE BCO AND RUN BCO
-------------------------------------------------------------------------------

This package uses two complementary BCO types: template BCOs (tBCOs) and run
BCOs (rBCOs). A tBCO describes a validated workflow and includes reference or
synthetic data with defined expected results or acceptance criteria that can be
used to evaluate pipeline parameters and establish the Error Domain and
Verification Kit. Once validated, a tBCO can be applied to similar input data
and use cases to generate an rBCO that records the inputs, outputs, parameters,
execution environment, and provenance associated with that individual analysis.
This distinction separates validation of the analytical method from
documentation of each subsequent execution. The tBCO therefore serves as the
reusable, validated representation of the workflow, while an rBCO is generated
when that workflow is applied to a particular sample or dataset. This is
important for analyses that are repeatedly applied, such as clinical or
biomarker workflows, because the computational method and its acceptance
criteria can remain fixed while the run-specific inputs, outputs, and
provenance change. The model also provides a direct mechanism for determining
whether an individual execution remains within the conditions established
during workflow validation.


-------------------------------------------------------------------------------
Troponin_I_tBCO.json
-------------------------------------------------------------------------------

Template BioCompute Object (tBCO) (IEEE 2791-2020). The assay specification:
what to detect, where to detect, how to detect it, over what range, when to
sample, and how to read the result.

One tBCO per biomarker assay. It holds no patient data and no results. A
study uses one assay per biomarker.


-------------------------------------------------------------------------------
Troponin_I_patient1_rBCO.json, Troponin_I_patient2_rBCO.json
-------------------------------------------------------------------------------

Run BioCompute Objects (rBCOs). What actually happened on the instrument for
one subject in one analytical run.

One rBCO per subject per analytical run, so a study has one tBCO and at least
as many rBCOs as there are subjects.

Contents:

  run and laboratory identity
  instrument serial number and software version
  reagent and calibrator lots
  calibration and quality-control acceptance
  collection time and handling for each specimen
  censoring state and repeat status for each measurement
  any deviation from the specification

provenance_domain.derived_from names the governing tBCO and fixes its version.
Anything the tBCO already states is not repeated here: the limits, the
reference limits, the platform and the sampling schedule are read from the
tBCO through that link.

The file holds no troponin concentrations and no demographics. BCOs are
public-facing; individual results live only in the study data.


-------------------------------------------------------------------------------
Troponin_I_SDTM.xlsx
-------------------------------------------------------------------------------

The study data, tabulated to CDISC SDTM (SDTMIG v3.4 over SDTM v2.1). Four
record types, one per tab:

  DM       one record per subject: age, sex, country, reference start date

  LB       one record per troponin result: the value as reported and in
           standard units, the reference limit, the limits of detection and
           quantitation (LBLLOD, LBLLOQ, LBULOQ), specimen type, method, LOINC
           code, visit and collection time

  SUPPLB   the qualifiers LB has no variable for, attached to the LB records
           they describe: assay name and platform, the identifier of the rBCO
           for that run, and the censoring state of each result

  BM       the biomarker context layer, one row per claim (diagnostic and
           prognostic): the entity, its role and condition,
           the assay, the interpretation rule, the identifier of the tBCO,
           and pointers to the LB records being described

The censoring state says which of four zones a result falls in - below the
limit of detection, detected but below the limit of quantitation,
quantifiable, or above the upper limit. It is calculated from the result and
the limits, not entered by hand.

A Definitions tab describes each domain and field.


-------------------------------------------------------------------------------
HOW THEY RELATE
-------------------------------------------------------------------------------

  tBCO  ---->  rBCO  ---->  SDTM
  how to       what         the data
  measure      happened

  one per      one per      one per
  biomarker    subject      study
  assay        per run


-------------------------------------------------------------------------------
NOTES
-------------------------------------------------------------------------------

BM is a proposed domain and is not part of SDTMIG v3.4. The DM, LB and SUPPLB
variables are standard.

Fields reading PLACEHOLDER need a real source before use.

The subject data is synthetic.

===============================================================================
