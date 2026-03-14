Review the implementation for "{title}" against the approved spec.

Approved spec:

{approved_spec}

Implementation log:

{implementation_log}

Changed files metadata:

{changed_files}

Return JSON with this structure:

{
  "summary": "short summary",
  "findings": [
    {
      "id": "F1",
      "category": "spec mismatch | missing edge case | security concern | correctness bug | test gap | code quality concern | unsupported claim",
      "severity": "low | medium | high",
      "files": ["relative/path"],
      "rationale": "why this is a finding",
      "suggested_fix": "what to change",
      "confidence": "low | medium | high"
    }
  ]
}

If there are no findings, return an empty findings array.

