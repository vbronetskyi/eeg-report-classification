import argparse
import json
import math
import re
from pathlib import Path
from openai import OpenAI

MODEL = "/scratch/brovik/hf/medgemma-27b-text-it"

client = OpenAI(
    base_url="http://127.0.0.1:8000/v1",
    api_key="EMPTY",
)

FIELD_CONFIGS = {
    "abnormality": {
        "instruction": """
Read the EEG report and score only the field 'abnormality'.

Scale:
1 = confident normal
2 = low-confidence normal
3 = low-confidence abnormal
4 = confident abnormal

Return only the JSON object.
""".strip(),
        "reports": [
            {
                "report_id": "normal_eeg",
                "text": (
                    "This EEG is within normal limits in wakefulness and drowsiness. "
                    "No focal slowing. No epileptiform discharges. No generalized abnormalities."
                ),
            },
            {
                "report_id": "generalized_slowing",
                "text": (
                    "This EEG is abnormal. There is diffuse generalized slowing of background activity. "
                    "No epileptiform discharges are seen."
                ),
            },
            {
                "report_id": "focal_slowing",
                "text": (
                    "This EEG is abnormal due to intermittent focal slowing over the left temporal region. "
                    "No epileptiform discharges are identified."
                ),
            },
            {
                "report_id": "focal_epileptiform",
                "text": (
                    "This EEG is abnormal. Frequent sharp waves are seen in the right temporal region, "
                    "consistent with focal epileptiform activity. No generalized epileptiform discharges."
                ),
            },
            {
                "report_id": "generalized_epileptiform",
                "text": (
                    "This EEG is abnormal. Generalized spike-and-wave discharges are present. "
                    "No focal epileptiform abnormalities are identified."
                ),
            },
        ],
    },
    "focal_epileptiform_activity": {
        "instruction": """
Read the EEG report and score only the field 'focal_epileptiform_activity'.

Scale:
1 = confident absence of focal epileptiform activity
2 = low-confidence absence of focal epileptiform activity
3 = low-confidence presence of focal epileptiform activity
4 = confident presence of focal epileptiform activity

Return only the JSON object.
""".strip(),
        "reports": [
            {
                "report_id": "normal_eeg",
                "text": (
                    "This EEG is within normal limits in wakefulness and drowsiness. "
                    "No focal slowing. No epileptiform discharges."
                ),
            },
            {
                "report_id": "focal_epileptiform",
                "text": (
                    "Frequent sharp waves are seen in the right temporal region, "
                    "consistent with focal epileptiform activity."
                ),
            },
            {
                "report_id": "generalized_epileptiform",
                "text": (
                    "Generalized spike-and-wave discharges are present. "
                    "No focal epileptiform abnormalities are identified."
                ),
            },
        ],
    },
    "generalized_epileptiform_activity": {
        "instruction": """
Read the EEG report and score only the field 'generalized_epileptiform_activity'.

Scale:
1 = confident absence of generalized epileptiform activity
2 = low-confidence absence of generalized epileptiform activity
3 = low-confidence presence of generalized epileptiform activity
4 = confident presence of generalized epileptiform activity

Return only the JSON object.
""".strip(),
        "reports": [
            {
                "report_id": "normal_eeg",
                "text": (
                    "This EEG is within normal limits. No epileptiform discharges."
                ),
            },
            {
                "report_id": "generalized_epileptiform",
                "text": (
                    "Generalized spike-and-wave discharges are present."
                ),
            },
            {
                "report_id": "focal_epileptiform",
                "text": (
                    "Frequent sharp waves are seen in the right temporal region. "
                    "No generalized epileptiform discharges."
                ),
            },
        ],
    },
    "focal_non_epileptiform_activity": {
        "instruction": """
Read the EEG report and score only the field 'focal_non_epileptiform_activity'.

Scale:
1 = confident absence of focal non-epileptiform activity
2 = low-confidence absence of focal non-epileptiform activity
3 = low-confidence presence of focal non-epileptiform activity
4 = confident presence of focal non-epileptiform activity

Examples include focal slowing.

Return only the JSON object.
""".strip(),
        "reports": [
            {
                "report_id": "normal_eeg",
                "text": (
                    "This EEG is within normal limits. No focal slowing."
                ),
            },
            {
                "report_id": "focal_slowing",
                "text": (
                    "Intermittent focal slowing is present over the left temporal region."
                ),
            },
            {
                "report_id": "generalized_slowing",
                "text": (
                    "Diffuse generalized slowing is present. No focal slowing."
                ),
            },
        ],
    },
    "generalized_non_epileptiform_activity": {
        "instruction": """
Read the EEG report and score only the field 'generalized_non_epileptiform_activity'.

Scale:
1 = confident absence of generalized non-epileptiform activity
2 = low-confidence absence of generalized non-epileptiform activity
3 = low-confidence presence of generalized non-epileptiform activity
4 = confident presence of generalized non-epileptiform activity

Examples include generalized slowing.

Return only the JSON object.
""".strip(),
        "reports": [
            {
                "report_id": "normal_eeg",
                "text": (
                    "This EEG is within normal limits. No generalized abnormalities."
                ),
            },
            {
                "report_id": "generalized_slowing",
                "text": (
                    "Diffuse generalized slowing of background activity is present."
                ),
            },
            {
                "report_id": "focal_slowing",
                "text": (
                    "Intermittent focal slowing is present over the left temporal region. "
                    "No generalized slowing."
                ),
            },
        ],
    },
}


SYSTEM = "You are a clinical EEG report annotation assistant."


def extract_json_text(text: str) -> str:
    if text is None:
        raise RuntimeError("message.content is None")

    text = text.strip()
    fence_match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, flags=re.DOTALL)
    if fence_match:
        return fence_match.group(1).strip()
    return text


def classify(field: str, instruction: str, report_text: str):
    schema = {
        "type": "object",
        "properties": {
            field: {"type": "integer", "enum": [1, 2, 3, 4]}
        },
        "required": [field],
        "additionalProperties": False,
    }

    return client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": instruction + "\n\nREPORT:\n" + report_text},
        ],
        temperature=0,
        max_tokens=32,
        logprobs=True,
        top_logprobs=20,
        extra_body={"guided_json": schema},
    )


def extract_digit_distribution(token_info) -> dict[int, float]:
    probs = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}

    chosen = token_info.token.strip()
    if chosen in {"1", "2", "3", "4"}:
        probs[int(chosen)] = max(probs[int(chosen)], math.exp(token_info.logprob))

    for alt in token_info.top_logprobs or []:
        tok = alt.token.strip()
        if tok in {"1", "2", "3", "4"}:
            probs[int(tok)] = max(probs[int(tok)], math.exp(alt.logprob))

    total = sum(probs.values()) or 1.0
    return {k: v / total for k, v in probs.items()}


def single_field_probs(resp, field: str):
    content = resp.choices[0].message.content
    json_text = extract_json_text(content)
    parsed = json.loads(json_text)

    toks = resp.choices[0].logprobs.content or []

    for t in toks:
        digit = t.token.strip()
        if digit in {"1", "2", "3", "4"}:
            dist = extract_digit_distribution(t)
            return {
                "pred": parsed[field],
                "p1": dist[1],
                "p2": dist[2],
                "p3": dist[3],
                "p4": dist[4],
                "p_presence": dist[3] + dist[4],
                "raw_content": content,
                "parsed_json": parsed,
            }

    raise RuntimeError(f"Could not find {field} value token in logprobs.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--field", required=True, choices=FIELD_CONFIGS.keys())
    args = parser.parse_args()

    cfg = FIELD_CONFIGS[args.field]
    rows = []

    for item in cfg["reports"]:
        report_id = item["report_id"]
        report_text = item["text"]

        resp = classify(args.field, cfg["instruction"], report_text)
        result = single_field_probs(resp, args.field)

        print("=" * 80)
        print(f"FIELD: {args.field}")
        print(f"REPORT: {report_id}")
        print(report_text)
        print("raw_content:", result["raw_content"])
        print(
            f"pred={result['pred']}  "
            f"P(presence)={result['p_presence']:.3f}  "
            f"dist={{1:{result['p1']:.3f}, 2:{result['p2']:.3f}, 3:{result['p3']:.3f}, 4:{result['p4']:.3f}}}"
        )

        rows.append({
            "field": args.field,
            "report_id": report_id,
            **result,
        })

    out_path = Path(f"single_{args.field}_results.json")
    out_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False))
    print("=" * 80)
    print(f"Saved to {out_path}")


if __name__ == "__main__":
    main()