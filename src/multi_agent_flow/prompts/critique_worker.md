You are performing iteration {iteration} of {total_iterations} in a research-critique loop for "{title}".

Use the normalized brief below as the source of truth:

{normalized_brief}

Your focus area is: {focus}

{previous_context}

IMPORTANT: Output your research-critique memo directly as text. Do NOT use the Write tool to create files — your stdout is captured and passed to the synthesis step. If you write to a file, the synthesis step will never see your work.

Produce a concise research-critique memo with these sections:
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

After completing your research, output your findings directly as text (NOT as a file).
