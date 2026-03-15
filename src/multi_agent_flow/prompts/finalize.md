You are finalizing "{title}" after independent review. Your job is to fix validated findings by actually modifying the code, then produce a disposition summary.

You MUST use your tools (Read, Write, Edit, Bash, Glob, Grep) to apply fixes. Do NOT just describe what to fix — actually fix it.

## Instructions

1. **Read the reviews.** Analyze the Gemini and Codex review findings below.
2. **Triage each finding.** Accept findings that are valid and actionable. Reject findings that are false positives, out of scope, or based on incorrect assumptions. Do not invent findings that were not present in the reviews.
3. **Fix accepted findings.** Use Read/Edit/Write/Bash to apply the fixes to the codebase. Follow the approved spec as the source of truth for what the code should do.
4. **Run validation.** Execute the validation commands below and fix any issues introduced by your changes.

## Approved Spec

{approved_spec}

## Gemini Review JSON

{gemini_review}

## Codex Review JSON

{codex_review}

## Validation Commands

{validation_commands}

## Output

After applying all fixes and running validation, write the following JSON to stdout:

```json
{{
  "summary": "short final summary",
  "accepted_findings": ["F1", "F2"],
  "rejected_findings": [
    {{
      "id": "F3",
      "reason": "why it was rejected"
    }}
  ],
  "fixes_applied": ["brief description of each fix"],
  "next_steps": ["optional follow-up"]
}}
```
