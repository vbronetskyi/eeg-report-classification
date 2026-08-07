from __future__ import annotations

import os
from typing import Any


OUTPUT_FIELDS = (
    "overall_abnormal",
    "focal_epileptiform",
    "generalized_epileptiform",
    "focal_nonepileptiform",
    "generalized_nonepileptiform",
)

OUTPUT_TO_INTERNAL = {
    "overall_abnormal": "abnormality",
    "focal_epileptiform": "focal_epileptiform_activity",
    "generalized_epileptiform": "generalized_epileptiform_activity",
    "focal_nonepileptiform": "focal_non_epileptiform_activity",
    "generalized_nonepileptiform": "generalized_non_epileptiform_activity",
}


# Prompt version is selectable via the PROMPT_VARIANT env var (default "v1").
#   v1 = original baseline prompt (Impression-first, short definitions).
#   v2 = professor's revision: role moved to the system message, body-first
#        information-extraction intro, and extended clinical definitions.
PROMPT_VARIANT = os.environ.get("PROMPT_VARIANT", "v1").lower()

SYSTEM_V1 = (
    "You are a clinical EEG report annotation assistant. "
    "Follow the annotation instructions exactly and return only valid JSON."
)
SYSTEM_V2 = (
    "You are a very experienced neurologist with deep expertise in evaluating "
    "routine clinical electroencephalography (EEG) recordings."
)
SYSTEM = SYSTEM_V2 if PROMPT_VARIANT == "v2" else SYSTEM_V1


PROMPT_PREFIX = r"""
Assume the role of a neurologist with deep expertise in evaluating routine clinical electroencephalograms (EEG).

Your task is to classify the given routine clinical EEG report according to a structured annotation schema. Transform the unstructured EEG report narrative into five structured numerical labels.

Use the Impression section as the primary source of evidence. Use the Description and Findings sections when the Impression is absent, unclear, incomplete, or ambiguous.

Do not infer abnormalities that are not supported by the EEG report.

The numerical values represent the direction and confidence of the classification, not the clinical severity of the abnormality.

You must classify the report using the following five variables.

A. Overall EEG status: normal versus abnormal

1 = confident normal
2 = low-confidence normal
3 = low-confidence abnormal
4 = confident abnormal

B. Presence of focal epileptiform activity

1 = confident no
2 = low-confidence no
3 = low-confidence yes
4 = confident yes

C. Presence of generalized epileptiform activity

1 = confident no
2 = low-confidence no
3 = low-confidence yes
4 = confident yes

D. Presence of focal non-epileptiform activity

1 = confident no
2 = low-confidence no
3 = low-confidence yes
4 = confident yes

E. Presence of generalized non-epileptiform activity

1 = confident no
2 = low-confidence no
3 = low-confidence yes
4 = confident yes

Definitions:

Epileptiform activity includes spikes, sharp waves, spike-and-wave discharges, polyspikes, periodic epileptiform discharges, seizures, electrographic seizures, or other clearly epileptiform abnormalities.

Focal epileptiform activity refers to epileptiform abnormalities localized to one region, hemisphere, lobe, or electrode region.

Generalized epileptiform activity refers to epileptiform abnormalities that are generalized, bilaterally synchronous, diffuse, or not clearly focal.

Non-epileptiform activity includes slowing, attenuation, asymmetry, discontinuity, suppression, burst suppression, excessive beta activity, background disorganization, encephalopathy, or other abnormalities that are not described as epileptiform.

Focal non-epileptiform activity refers to focal slowing, focal attenuation, focal asymmetry, focal dysfunction, or other localized non-epileptiform abnormalities.

Generalized non-epileptiform activity refers to diffuse slowing, generalized background disorganization, generalized attenuation, encephalopathy, excessive generalized beta activity, or other diffuse non-epileptiform abnormalities.

Annotation rules:

1. First classify the overall EEG status using variable A.

2. If the EEG is normal or probably normal, assign A = 1 or A = 2.

3. If A = 1 or A = 2, variables B, C, D, and E must each be either 1 or 2. Do not assign 3 or 4 to any abnormality subtype when the overall EEG is normal or probably normal.

4. If the EEG is abnormal or probably abnormal, assign A = 3 or A = 4.

5. If A = 3 or A = 4, at least one of B, C, D, or E must be assigned 3 or 4.

6. If any of B, C, D, or E is assigned 3 or 4, then A must also be assigned 3 or 4.

7. If all of B, C, D, and E are assigned 1 or 2, then A must also be assigned 1 or 2.

8. If the report clearly states that a subtype of abnormality is present, assign 4.

9. If the report suggests that a subtype may be present, but the evidence is uncertain, limited, equivocal, or described with uncertainty, assign 3.

10. If the report suggests that a subtype is probably absent, but the wording or quality of the report leaves uncertainty, assign 2.

11. If the report provides no evidence for a subtype, or clearly indicates that the subtype is absent, assign 1.

12. Abnormality types may overlap. A report may contain both epileptiform and non-epileptiform abnormalities and both focal and generalized abnormalities.

13. Evaluate each subtype separately. Do not assign a subtype as present solely because the overall EEG is abnormal.

14. Preserve internal consistency between the overall classification and the four abnormality subtype classifications.

Output requirements:

Return only one valid JSON object. Do not include Markdown, comments, reasoning, evidence, explanations, or text outside the JSON object.

The response must contain exactly these top-level keys in this order:

1. overall_abnormal
2. focal_epileptiform
3. generalized_epileptiform
4. focal_nonepileptiform
5. generalized_nonepileptiform

Each value must be an integer from 1 to 4.

Before returning the JSON, silently verify that:

- if overall_abnormal is 1 or 2, all four subtype variables are 1 or 2;
- if overall_abnormal is 3 or 4, at least one subtype variable is 3 or 4;
- if any subtype variable is 3 or 4, overall_abnormal is 3 or 4;
- if all four subtype variables are 1 or 2, overall_abnormal is 1 or 2;
- all five numerical labels are integers from 1 to 4;
- the output is valid JSON;
- no text appears before or after the JSON object.

EEG report to classify:
""".strip()


PROMPT_PREFIX_V2 = r"""
This is an information-extraction task from the EEG report. Read the full report before assigning labels.

Use the Findings, Description, Body, or EEG Results sections first to identify specific EEG activities:
- focal epileptiform activity
- generalized epileptiform activity
- focal non-epileptiform activity
- generalized non-epileptiform activity

Use the Impression, Interpretation, Conclusion, or Clinical Correlation section as the summary source. The Impression should guide the overall normal/abnormal label, but it may be more conservative than the body of the report, especially for focal epileptiform abnormalities. Therefore, do not ignore specific abnormalities described in the body merely because the Impression summarizes them cautiously or incompletely.

Overall EEG status: Use the Impression or Interpretation section to determine the overall EEG status when it is clear. If the Impression states "normal EEG," "within normal limits," or "no definite abnormality," and the body does not describe convincing abnormal activity, classify the EEG as normal or probably normal.

If the body describes a specific abnormality but the Impression is conservative, equivocal, or does not mention it, do not automatically discard the body finding. Instead, assign the relevant subtype based on the body evidence and adjust confidence according to the level of agreement between the body and Impression.

You must classify the report using the following five variables.

A. Overall EEG status: normal versus abnormal

1 = confident normal
2 = low-confidence normal
3 = low-confidence abnormal
4 = confident abnormal

B. Presence of focal epileptiform activity
C. Presence of generalized epileptiform activity
D. Presence of focal non-epileptiform activity
E. Presence of generalized non-epileptiform activity

For variables B, C, D, and E:
1 = confident no
2 = low-confidence no
3 = low-confidence yes
4 = confident yes

DEFINITIONS

Clinical terminology basis.

Use the terminology below as an operational EEG-report annotation schema. The schema is based on standard clinical EEG terminology, including ACNS EEG-reporting guidance, ACNS standardized EEG terminology for spatial pattern classification, and ILAE terminology distinguishing focal from generalized epileptic phenomena. The four abnormality categories are constructed by crossing two clinical dimensions: spatial distribution, defined as focal/localized versus generalized/diffuse, and physiological interpretation, defined as epileptiform versus non-epileptiform.

Overall abnormality.

Classify the EEG as abnormal when the report states or clearly implies that the recording contains a clinically meaningful abnormal finding. Abnormality may be epileptiform, non-epileptiform, focal, generalized, or mixed. A report may be abnormal even when no seizures or epileptiform discharges are present, for example when it describes focal slowing, diffuse slowing, background disorganization, attenuation, suppression, encephalopathy, or focal cerebral dysfunction. A report should be classified as normal only when the Impression or Interpretation states that the EEG is normal, within normal limits, or shows no definite abnormality, and there is no contradictory abnormal finding elsewhere in the report.

Epileptiform activity.

Epileptiform activity refers to EEG abnormalities whose morphology or interpretation is associated with epileptic cortical irritability or seizures. Count as epileptiform when the report explicitly describes spikes, sharp waves, spike-and-wave discharges, polyspikes, polyspike-and-wave discharges, epileptiform discharges, interictal epileptiform discharges, electrographic seizures, ictal patterns, or periodic/rhythmic patterns interpreted as epileptiform or ictal. Do not classify a waveform as epileptiform merely because it is sharp-looking. Terms such as "sharply contoured," "irregular," "artifact," or "benign variant" should not be treated as epileptiform unless the report explicitly interprets them as epileptiform.

Focal versus generalized distribution.

Use focal when the abnormality is localized to one hemisphere, lobe, region, electrode field, or named anatomic area. Examples include temporal, frontal, central, parietal, occipital, left-sided, right-sided, unilateral, hemispheric, regional, lateralized, multifocal, or bilateral independent findings. Use generalized when the abnormality is described as generalized, diffuse, bilateral synchronous, bilaterally symmetric, widespread, global, or affecting the background as a whole. ILAE seizure terminology treats focal phenomena as originating within one hemisphere and generalized phenomena as appearing apparently simultaneously in both hemispheres. ACNS terminology similarly distinguishes generalized patterns from lateralized, bilateral independent, and multifocal patterns.

Focal epileptiform activity.

Focal epileptiform activity means epileptiform activity localized to a specific region, lobe, hemisphere, or electrode field. Assign this category when the report describes focal spikes, focal sharp waves, focal spike-and-wave discharges, focal epileptiform discharges, temporal sharp waves, frontal spikes, rolandic spikes, occipital spikes, lateralized epileptiform discharges, lateralized periodic discharges interpreted as epileptiform, or focal electrographic seizures. Multifocal spikes and bilateral independent epileptiform discharges should generally be classified as focal epileptiform rather than generalized epileptiform, because they represent multiple localized epileptiform populations rather than a single generalized bilaterally synchronous discharge.

Generalized epileptiform activity.

Generalized epileptiform activity means epileptiform activity that is generalized, bilaterally synchronous, or apparently simultaneous across both hemispheres. Assign this category when the report describes generalized spike-and-wave discharges, generalized polyspike-and-wave discharges, generalized epileptiform discharges, generalized periodic discharges interpreted as epileptiform, generalized electrographic seizures, or a generalized photoparoxysmal response. Do not assign generalized epileptiform activity solely because epileptiform abnormalities occur in more than one region; multifocal or bilateral independent epileptiform abnormalities should usually be classified as focal epileptiform unless the report explicitly describes them as generalized or bilaterally synchronous.

Non-epileptiform activity.

Non-epileptiform activity refers to abnormal EEG findings that indicate altered cerebral function but are not described as epileptiform. The most common non-epileptiform abnormality is slowing. Other non-epileptiform abnormalities include attenuation, asymmetry, suppression, discontinuity, burst-suppression, low-voltage background, poor organization, loss or slowing of the posterior dominant rhythm, abnormal sleep architecture, reduced reactivity, or encephalopathic background patterns. These findings should not be treated as epileptiform unless the report explicitly describes epileptiform discharges or seizures.

Focal non-epileptiform activity.

Focal non-epileptiform activity means localized abnormal cerebral function without epileptiform discharges. Assign this category when the report describes focal slowing, intermittent or persistent regional slowing, temporal slowing, frontal slowing, hemispheric slowing, focal delta activity, focal theta/delta slowing, focal attenuation, focal voltage asymmetry, focal suppression, breach-related asymmetry when described as abnormal, focal background abnormality, or focal cerebral dysfunction. The phrase "focal cerebral dysfunction" is usually sufficient evidence for focal non-epileptiform abnormality even if no epileptiform discharges are reported.

Generalized non-epileptiform activity.

Generalized non-epileptiform activity means diffuse or global abnormal cerebral function without epileptiform discharges. Assign this category when the report describes diffuse slowing, generalized slowing, background slowing, slow posterior dominant rhythm for age/state, poorly organized background, generalized attenuation, generalized suppression, discontinuity, burst-suppression, low-voltage background, lack of reactivity, toxic-metabolic encephalopathy, nonspecific encephalopathy, or mild/moderate/severe diffuse cerebral dysfunction. A report that says "abnormal due to diffuse slowing" or "consistent with encephalopathy" should be classified as generalized non-epileptiform even when it explicitly states that no epileptiform activity or seizures were seen.

Mixed abnormalities.

The four abnormality categories are not mutually exclusive. A single report may contain focal epileptiform activity and generalized non-epileptiform activity, for example "left temporal sharp waves superimposed on diffuse background slowing." A report may also contain focal non-epileptiform and generalized non-epileptiform abnormalities, for example "diffuse slowing with superimposed left temporal slowing." Assign all categories supported by the report text.

Normal variants and artifacts.

Do not classify normal variants, benign variants, or artifacts as epileptiform or abnormal unless the report explicitly says they are abnormal. Examples include eye-blink artifact, muscle artifact, movement artifact, electrode artifact, lambda waves, wicket waves, small sharp spikes/benign epileptiform transients of sleep when explicitly called benign, POSTS, vertex waves, sleep spindles, K-complexes, rhythmic temporal theta of drowsiness, and breach rhythm. "Sharply contoured" activity alone is not enough for epileptiform classification.

Confidence levels.

The numerical score reflects confidence in presence or absence, not severity. Mild diffuse slowing can be a confident generalized non-epileptiform abnormality if clearly stated. Rare spikes can be confident focal epileptiform activity if clearly stated. Use high-confidence positive labels when the report clearly states the abnormality. Use low-confidence positive labels when the report uses uncertain wording such as possible, probable, questionable, suspicious, suggestive, cannot exclude, may represent, limited study, technically limited, or when the Impression and Description are not fully consistent. Use high-confidence negative labels when the report explicitly denies the abnormality or gives no evidence for it. Use low-confidence negative labels when the report is normal/probably normal but technically limited, incomplete, or ambiguous.

Annotation rules:

1. If A = 1 or A = 2 (normal or probably normal), variables B, C, D, and E must each be either 1 or 2.
2. If A = 3 or A = 4 (abnormal or probably abnormal), at least one of B, C, D, or E must be assigned 3 or 4.
3. If any of B, C, D, or E is assigned 3 or 4, then A must also be assigned 3 or 4.
4. If all of B, C, D, and E are assigned 1 or 2, then A must also be assigned 1 or 2.
5. Abnormality types may overlap. Evaluate each subtype separately.

Output requirements:

Return only one valid JSON object. Do not include Markdown, comments, reasoning, evidence, explanations, or text outside the JSON object.

The response must contain exactly these top-level keys in this order:

1. overall_abnormal
2. focal_epileptiform
3. generalized_epileptiform
4. focal_nonepileptiform
5. generalized_nonepileptiform

Each value must be an integer from 1 to 4.

EEG report to classify:
""".strip()


# v3 and v4 are v1 with targeted guidance to raise Focal Epi precision (the class
# where MedGemma trails Mistral-7B — it over-calls focal epileptiform). v3 adds
# explicit exclusions; v4 adds a structured detect-then-localize procedure.
_V3_FOCAL = r"""
Focal epileptiform — precision guidance (apply before scoring focal epileptiform):

Assign focal epileptiform activity as present (3 or 4) ONLY when the report explicitly describes epileptiform discharges — spikes, sharp waves, spike-and-wave, polyspikes, (inter)ictal or epileptiform discharges, lateralized epileptiform discharges, or focal electrographic seizures — that are localized to a region, lobe, hemisphere, or electrode field (for example "left temporal sharp waves", "right frontal spikes"). Multifocal or bilateral-independent epileptiform discharges also count as focal epileptiform.

Do NOT assign focal epileptiform (keep 1 or 2) for:
- epileptiform activity described as generalized, bilaterally synchronous, or diffuse — that is generalized epileptiform, not focal;
- "sharply contoured" activity, sharp transients, wicket spikes, small sharp spikes, or other benign variants, unless the report explicitly calls them epileptiform;
- artifacts;
- focal slowing, focal attenuation, or focal cerebral dysfunction — those are focal NON-epileptiform, not epileptiform.

When epileptiform activity is present but its localization to a specific region is not explicit, do not assign focal epileptiform; prefer 1 or 2.
""".strip()

_V4_PROC = r"""
Epileptiform decision procedure (apply before scoring focal and generalized epileptiform):

Step 1. Is any epileptiform activity explicitly described? Look for spikes, sharp waves, spike-and-wave, polyspikes, (inter)ictal or epileptiform discharges, periodic/lateralized discharges interpreted as epileptiform, or electrographic seizures. If none is explicitly described, set BOTH focal epileptiform and generalized epileptiform to 1 or 2, and do not treat sharply contoured waveforms, benign variants, or artifacts as epileptiform.

Step 2. If epileptiform activity IS present, classify its distribution:
- localized to a region, lobe, hemisphere, or electrode field, or multifocal / bilateral-independent -> focal epileptiform;
- generalized, bilaterally synchronous, or diffuse -> generalized epileptiform.

Step 3. Mark only the matching category as present (3 or 4); keep the other at 1 or 2 unless the report explicitly describes both focal and generalized epileptiform discharges.
""".strip()

PROMPT_PREFIX_V3 = PROMPT_PREFIX.replace(
    "Output requirements:",
    _V3_FOCAL + "\n\nOutput requirements:", 1)

PROMPT_PREFIX_V4 = PROMPT_PREFIX.replace(
    "Output requirements:",
    _V4_PROC + "\n\nOutput requirements:", 1)


# v5 = v3 (keep the Focal-Epi precision gains) + an explicit focal-vs-generalized
# distribution discriminator for the NON-epileptiform (slowing) categories. Error
# analysis showed the dominant error across the whole task is focal<->generalized
# mis-bucketing of slowing: most focal-non FPs are truly generalized-non, and most
# generalized-non FPs are truly focal-non. This block forces the distribution call
# to be read straight from the report wording and forbids double-flagging one finding.
_V5_DISTRIBUTION = r"""
Focal versus generalized — distribution guidance for non-epileptiform activity (apply before scoring focal non-epileptiform and generalized non-epileptiform):

Non-epileptiform findings (slowing, attenuation, disorganization, dysfunction) must be assigned to the focal category OR the generalized category strictly according to how the report describes their spatial distribution.

Assign FOCAL non-epileptiform (3 or 4) when the finding is localized — described with a region, lobe, hemisphere, side, or electrode field, for example "left temporal slowing", "right frontal attenuation", "focal delta", "focal cerebral dysfunction", "hemispheric slowing".

Assign GENERALIZED non-epileptiform (3 or 4) when the finding is described as diffuse, generalized, bilateral and symmetric, widespread, background-wide, a diffusely slow posterior dominant rhythm, or encephalopathy.

Do NOT assign both focal and generalized non-epileptiform for the same finding:
- diffuse or generalized slowing is generalized ONLY — do not also mark it focal;
- regional or one-sided slowing is focal ONLY — do not also mark it generalized;
- assign BOTH only when the report explicitly describes a separate localized abnormality AND a separate diffuse abnormality (for example "focal left temporal slowing superimposed on diffuse background slowing").

Do not infer a generalized abnormality merely because several focal findings are listed, and do not infer a focal abnormality from a purely diffuse one.
""".strip()

PROMPT_PREFIX_V5 = PROMPT_PREFIX.replace(
    "Output requirements:",
    _V3_FOCAL + "\n\n" + _V5_DISTRIBUTION + "\n\nOutput requirements:", 1)


# v6 = v3 + a prompt-only consistency reconciliation step. Error analysis found ~34
# reports where the model marked a subtype present (3/4) yet still called the EEG
# normal (overall_abnormal 1/2) — a violation of the schema's own rule. Rather than
# repair this in post-processing, v6 pushes the model to actively fix contradictions
# itself, as a mandatory final step, without changing anything else (so the rest of
# the performance should be preserved). Built on v3 so the consistency effect is a
# clean, isolated addition over the same base as v5.
_V6_RECONCILE = r"""
Consistency reconciliation (perform this as the final step before writing the JSON; you must actively ADJUST the five values, not merely check them):

A self-contradictory answer is always wrong. After assigning all five values, reconcile the overall status with the four subtypes so they agree:

1. If you assigned 3 or 4 to ANY subtype (focal epileptiform, generalized epileptiform, focal non-epileptiform, or generalized non-epileptiform), then the EEG contains an abnormality, so overall_abnormal MUST be 3 or 4. Never leave overall_abnormal at 1 or 2 while any subtype is 3 or 4 — raise overall_abnormal to at least 3.

2. If overall_abnormal is 3 or 4, at least one subtype must be 3 or 4. If every subtype is currently 1 or 2, either raise the single best-supported subtype to 3, or — if the report truly gives no subtype evidence — lower overall_abnormal to 1 or 2.

3. If all four subtypes are 1 or 2, then overall_abnormal MUST be 1 or 2.

Apply these adjustments silently and output only the final, reconciled JSON.
""".strip()

PROMPT_PREFIX_V6 = PROMPT_PREFIX_V3.replace(
    "Output requirements:",
    _V6_RECONCILE + "\n\nOutput requirements:", 1)


# v7 = v5 (focal-epi exclusions + slowing discriminator) + a body-aware abnormality
# instruction. The largest remaining gap to the human annotator is Abnormality: the
# model misses ~77 truly-abnormal EEGs, almost all slowing described in the report
# BODY while the Impression stays conservative. This is the professor's v2 principle,
# but now safe to add because the focal-epi exclusions + grammar-enforced consistency
# prevent the over-calling collateral that v2 caused. Run with ENFORCE_CONSISTENCY=1.
# The instruction is a general clinical-annotation rule, not tuned to any annotator.
_V7_ABNORMALITY = r"""
Overall abnormality — read the whole report, not only the Impression:

The Impression may be conservative, brief, or incomplete. If the Description, Findings, or body of the report clearly describes an abnormality — focal or diffuse slowing, attenuation, asymmetry, focal cerebral dysfunction, background disorganization, or epileptiform discharges — classify the EEG as abnormal (overall_abnormal 3 or 4) even when the Impression is cautious or does not restate it, and assign the matching subtype. Classify the EEG as normal (1 or 2) only when neither the Impression nor the body describes a convincing abnormality.
""".strip()

PROMPT_PREFIX_V7 = PROMPT_PREFIX_V5.replace(
    "Output requirements:",
    _V7_ABNORMALITY + "\n\nOutput requirements:", 1)


# v8 = a deliberately SIMPLIFIED prompt (the professor's other request). Every prior
# variant only added text; v8 tests the opposite hypothesis — that a short prompt that
# spends its words only on the two real decision boundaries (epileptiform vs
# non-epileptiform; focal vs generalized), with consistency delegated to the grammar,
# generalizes at least as well as the long prompts and is less over-fit. Run with
# ENFORCE_CONSISTENCY=1 (the grammar supplies the consistency rules this prompt omits).
PROMPT_PREFIX_V8 = r"""
You are a neurologist classifying a routine clinical EEG report into five labels. Use the Impression as the primary source and the Description or Findings when the Impression is unclear or incomplete. Do not infer anything the report does not support.

Score each variable on this scale:
1 = confident no / normal, 2 = low-confidence no / normal, 3 = low-confidence yes / abnormal, 4 = confident yes / abnormal.

The five variables:
- overall_abnormal: is the EEG abnormal at all.
- focal_epileptiform: epileptiform discharges (spikes, sharp waves, spike-and-wave, epileptiform or periodic discharges, electrographic seizures) localized to a region, lobe, hemisphere, or electrode field; multifocal or bilateral-independent discharges also count here.
- generalized_epileptiform: epileptiform discharges that are generalized, bilaterally synchronous, or diffuse.
- focal_nonepileptiform: non-epileptiform disturbance (slowing, attenuation, asymmetry, focal cerebral dysfunction) localized to a region, lobe, hemisphere, or one side.
- generalized_nonepileptiform: non-epileptiform disturbance that is diffuse, generalized, bilaterally symmetric, or encephalopathic.

Two distinctions decide most cases:
1. Epileptiform vs non-epileptiform: only spikes, sharp waves, and explicit epileptiform discharges are epileptiform; slowing and attenuation are non-epileptiform. "Sharply contoured" waveforms, benign variants, and artifacts are not epileptiform unless the report explicitly says so.
2. Focal vs generalized: mark focal when the finding is localized or one-sided, generalized when it is diffuse or bilateral. Do not mark both for the same finding unless the report describes a separate localized abnormality and a separate diffuse one.

Return only one JSON object with exactly these integer keys valued 1-4: overall_abnormal, focal_epileptiform, generalized_epileptiform, focal_nonepileptiform, generalized_nonepileptiform. No other text.

EEG report to classify:
""".strip()


OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        field: {
            "type": "integer",
            "enum": [1, 2, 3, 4],
        }
        for field in OUTPUT_FIELDS
    },
    "required": list(OUTPUT_FIELDS),
    "additionalProperties": False,
}


def build_prompt(report_text: str) -> str:
    report_text = report_text.strip()

    if not report_text:
        raise ValueError("EEG report text is empty.")

    prefix = {
        "v2": PROMPT_PREFIX_V2,
        "v3": PROMPT_PREFIX_V3,
        "v4": PROMPT_PREFIX_V4,
        "v5": PROMPT_PREFIX_V5,
        "v6": PROMPT_PREFIX_V6,
        "v7": PROMPT_PREFIX_V7,
        "v8": PROMPT_PREFIX_V8,
    }.get(PROMPT_VARIANT, PROMPT_PREFIX)
    return prefix + "\n\n" + report_text


# When ENFORCE_CONSISTENCY is set, build_grammar() emits a grammar that makes a
# self-contradictory answer physically impossible to decode (rather than only asking
# for consistency in the prompt, as v6 does). The four subtypes are emitted FIRST and
# overall_abnormal LAST, so the overall label is forced to agree with the subtypes the
# model already committed to — the strong subtype detection drives the overall call,
# and the "subtype present but EEG normal" contradiction cannot occur. Parsing is by
# JSON key name (see cpu/evaluator.find_field_token), so reordering keys is safe.
ENFORCE_CONSISTENCY = os.environ.get("ENFORCE_CONSISTENCY", "").lower() in {"1", "true", "yes"}


def build_grammar() -> str:
    """GBNF grammar hard-constraining output to the five fields.

    Unlike a json_schema "hint" (which llama.cpp does not strictly enforce),
    a GBNF grammar makes it impossible for the model to omit a field or emit
    malformed JSON. Matches the paper's llama.cpp grammar-constrained setup.
    Generated from OUTPUT_FIELDS so it can never drift from the schema.

    With ENFORCE_CONSISTENCY, the grammar additionally guarantees the schema's
    bidirectional consistency rule: overall_abnormal is high (3/4) iff at least one
    subtype is high. Subtypes are placed first and overall_abnormal last.
    """
    if not ENFORCE_CONSISTENCY:
        pairs = " \",\" ws ".join(
            f'"\\"{field}\\":" ws num' for field in OUTPUT_FIELDS
        )
        return (
            f'root ::= "{{" ws {pairs} ws "}}"\n'
            "num ::= [1-4]\n"
            "ws ::= [ \\t\\n]*\n"
        )

    subs = [f for f in OUTPUT_FIELDS if f != "overall_abnormal"]  # the four subtypes
    sep = ' "," ws '

    def kv(field: str, valrule: str) -> str:
        return f'"\\"{field}\\":" ws {valrule}'

    # normal branch: every subtype low (1-2) -> overall_abnormal low (1-2)
    normal_body = sep.join(kv(s, "low") for s in subs)
    normal = f'"{{" ws {normal_body}{sep}{kv("overall_abnormal", "low")} ws "}}"'

    # abnormal branches: at least one subtype high, enumerated by first-high position
    # -> overall_abnormal high (3-4)
    abnormal = []
    for i in range(len(subs)):
        vals = ["low"] * i + ["high"] + ["anyv"] * (len(subs) - i - 1)
        body = sep.join(kv(s, v) for s, v in zip(subs, vals))
        abnormal.append(
            f'"{{" ws {body}{sep}{kv("overall_abnormal", "high")} ws "}}"')

    root = "root ::= " + normal + " | " + " | ".join(abnormal) + "\n"
    return (
        root
        + "low ::= [1-2]\n"
        + "high ::= [3-4]\n"
        + "anyv ::= [1-4]\n"
        + "ws ::= [ \\t\\n]*\n"
    )


def output_to_internal_labels(
    parsed: dict[str, Any],
) -> dict[str, int]:
    labels: dict[str, int] = {}

    for output_field, internal_field in OUTPUT_TO_INTERNAL.items():
        value = parsed.get(output_field)

        if type(value) is not int or value not in {1, 2, 3, 4}:
            raise ValueError(
                f"Invalid value for {output_field}: {value!r}"
            )

        labels[internal_field] = value

    return labels


def check_output_consistency(
    parsed: dict[str, Any],
) -> tuple[bool, str]:
    labels = {
        field: parsed.get(field)
        for field in OUTPUT_FIELDS
    }

    for field, value in labels.items():
        if type(value) is not int or value not in {1, 2, 3, 4}:
            return False, f"{field} is not an integer from 1 to 4."

    overall_positive = labels["overall_abnormal"] >= 3
    subtype_positive = any(
        labels[field] >= 3
        for field in OUTPUT_FIELDS[1:]
    )

    if overall_positive and not subtype_positive:
        return (
            False,
            "Overall EEG is abnormal but no subtype is positive.",
        )

    if subtype_positive and not overall_positive:
        return (
            False,
            "A subtype is positive but the overall EEG is normal.",
        )

    model_check = parsed.get("consistency_check")

    if not isinstance(model_check, dict):
        return False, "consistency_check is missing."

    if model_check.get("passed") is not True:
        return False, "Model consistency_check.passed is not true."

    return True, "Labels satisfy bidirectional consistency rules."
