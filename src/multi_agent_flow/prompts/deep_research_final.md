You are producing the final consolidated research report for "{title}" after {total_iterations} iterations of deep research.

The original research brief:

{normalized_brief}

{syntheses_manifest}

## Strategy

- Read ALL iteration syntheses using the Read tool, starting from iteration 1
- Process each synthesis before reading the next — track how evidence and findings evolved across iterations
- Later iterations built on earlier ones but earlier iterations may contain unique sources not carried forward
- Use Grep to search for specific themes or source URLs across all syntheses when needed
- Check the source directories for fetched content if you need to verify a citation

## Output Structure

Produce a single, definitive research report with these sections:

### Executive Summary
The most important evidence-backed findings across all iterations, prioritized by impact and evidence strength.

### Key Findings
Comprehensive findings organized by theme. Each finding includes:
- The conclusion, stated clearly
- Supporting evidence with citations
- Evidence strength rating (strong/moderate/weak/conflicting)
- Which iterations contributed to this finding

### Complete Source Registry
All sources cited across all iterations, deduplicated and annotated:
```
[Source N] URL | quality_rating | description | iterations: 1, 3 | fetch_tier: direct
```

### Evidence Assessment
For each major finding, a structured assessment:
- **Strong evidence**: Multiple independent authoritative sources across iterations
- **Moderate evidence**: Consistent but limited sourcing
- **Weak evidence**: Single-sourced or anecdotal only
- **Conflicting evidence**: Sources disagree — present both sides

### Counterarguments and Limitations
Opposing viewpoints, criticisms, and failure cases found during research. These are as important as supporting evidence.

### Gaps and Unknowns
What remains unknown after {total_iterations} iterations. What sources were sought but not found. What questions remain open.

### Methodology Notes
- Total sources attempted vs. successfully fetched
- Fetch success rate by tier (direct, wget, jina, cache, wayback, snippet, failed)
- Coverage assessment: which aspects of the topic have strong coverage vs. sparse coverage
- Any systematic biases in the sources found (e.g., all from one perspective, all from one time period)

### Iteration Progression
Brief summary of how the evidence base grew across iterations:
- Iteration 1: what was found
- Iteration 2: what was added or corrected
- ...

### Recommendations
If applicable, concrete recommendations based on the evidence. Each recommendation must cite the evidence that supports it.

## Rules

- Prioritize by evidence strength. Lead with the strongest-supported findings.
- Deduplicate aggressively — if the same source appeared in multiple iterations, consolidate it.
- Preserve the strongest evidence and best citations from whichever iteration produced them.
- Do not pad. If a section has nothing meaningful, say so in one line.
- Every factual claim must have a citation. Uncited claims must be marked `[UNVERIFIED]`.
- This document should be usable as a standalone research brief.

Output your final report directly as text. Do NOT use the Write tool to create files.
