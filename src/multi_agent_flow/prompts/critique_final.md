You are producing the final consolidated critique for "{title}" after {total_iterations} iterations of research-critique.

The original brief:

{normalized_brief}

{syntheses_manifest}

Strategy:
- Read ALL iteration syntheses using the Read tool, starting from iteration 1
- Process each synthesis before reading the next — track how findings evolved across iterations
- Later iterations built on earlier ones but earlier iterations may contain unique findings later dropped
- Use Grep to search for specific themes across all syntheses when needed

Produce a single, definitive critique document with these sections:

- Executive Summary (the most important findings across all iterations, prioritized by impact)
- Design Strengths (what consistently held up under repeated scrutiny across iterations)
- Critical Weaknesses (high-impact problems that surfaced and were reinforced across iterations)
- Gaps and Missing Requirements (requirements the design does not address)
- Contradictions and Tensions (unresolved conflicts within the design)
- Risk Assessment (prioritized risks with severity and likelihood)
- Open Questions (the most important unresolved questions, prioritized)
- Concrete Recommendations (actionable changes to the design, prioritized by impact)
- Iteration Progression Summary (brief note on how the critique evolved — what each round added)

Rules:
- Prioritize by impact. Lead with what matters most.
- Deduplicate aggressively — if the same finding appeared in multiple iterations, consolidate it.
- Preserve the strongest evidence and reasoning from whichever iteration produced it.
- Do not pad. If a section has nothing meaningful, say so in one line.
- This document should be usable as a direct input to revise the original design.

Output your final critique directly as text. Do NOT use the Write tool to create files.
