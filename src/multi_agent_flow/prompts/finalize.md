You are finalizing "{title}" after independent review.

Approved spec:

{approved_spec}

Gemini review JSON:

{gemini_review}

Codex review JSON:

{codex_review}

Validation commands to rerun:

{validation_commands}

Return JSON with this structure:

{
  "summary": "short final summary",
  "accepted_findings": ["F1", "F2"],
  "rejected_findings": [
    {
      "id": "F3",
      "reason": "why it was rejected"
    }
  ],
  "next_steps": ["optional follow-up"]
}

Do not invent findings that were not present in the reviews.

