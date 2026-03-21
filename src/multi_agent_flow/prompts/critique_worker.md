You are performing iteration {iteration} of {total_iterations} in a research-critique loop for "{title}".

Use the normalized brief below as the source of truth:

{normalized_brief}

Your focus area is: {focus}

{previous_context}

## How to Save Your Findings

Write your findings incrementally to a file as you research. Use this command:

```bash
python -m multi_agent_flow.write_findings {output_path} << 'FINDINGS'
your content here
FINDINGS
```

To append more findings as you continue researching:

```bash
python -m multi_agent_flow.write_findings {output_path} --append << 'FINDINGS'
additional content here
FINDINGS
```

This lets you offload findings to disk as you go. You can read your own file at any time
with the Read tool to review what you've already written.

Your final document at {output_path} should be a complete research-critique memo with these sections:
- New Findings (things not covered or insufficiently covered in prior iterations)
- Challenged Assumptions (assumptions from the brief or prior iterations that deserve scrutiny)
- Gaps Identified (missing requirements, unaddressed risks, unstated dependencies)
- Contradictions (conflicts within the brief or between prior iteration findings)
- Open Questions (unresolved items that need human input or further investigation)
- Strength Assessment (what IS well-designed and should be preserved)

Do not repeat findings from prior iterations unless you are deepening or challenging them.
If you cite external facts, name the source or say that it still needs verification.

You have access to web search and file reading tools. Use them actively:
- Search for academic papers, blog posts, and security research related to your focus area
- Read relevant files in the project codebase to ground your analysis
- Verify claims against authoritative sources

After completing your research, also output a brief summary of your findings as text (your detailed findings are saved to the file).
