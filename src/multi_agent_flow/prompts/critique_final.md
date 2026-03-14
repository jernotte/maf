You are producing the final consolidated critique for "{title}" after {total_iterations} iterations of research-critique.

The original brief:

{normalized_brief}

Below are the synthesis documents from each iteration. Each built on the previous one, going progressively deeper.

{all_syntheses}

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

IMPORTANT: Output ONLY valid markdown. Do not emit tool calls, XML tags, JSON tool invocations, or any non-markdown content. Do not attempt to read files or use tools. Your entire response must be a single markdown document.
