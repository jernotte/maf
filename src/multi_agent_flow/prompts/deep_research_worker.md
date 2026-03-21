You are performing iteration {iteration} of {total_iterations} in a deep research loop for "{title}".

Your mission is to **find, fetch, and cite external sources** that provide evidence, context, and diverse perspectives on this topic.

Use the research brief below as your starting point:

{normalized_brief}

Your focus area is: {focus}

{previous_context}

{prefetch_context}

## How to Fetch Source Content

For every promising URL you find, fetch its full content using this tool:

```bash
python -m multi_agent_flow.fetch_source "URL" {sources_dir}/source-NNN.md --snippet "search result preview text"
```

- Replace NNN with a sequential number (001, 002, 003, ...)
- Always include `--snippet` with the search result preview text as a fallback
- The tool tries multiple fetch methods automatically (direct HTTP, wget, Jina Reader, Google Cache, Wayback Machine)
- If all methods fail, it saves the snippet as a fallback

## How to Save Your Findings

Write your findings incrementally to a file as you research:

```bash
python -m multi_agent_flow.write_findings {output_path} << 'FINDINGS'
your content here
FINDINGS
```

To append more findings:

```bash
python -m multi_agent_flow.write_findings {output_path} --append << 'FINDINGS'
additional content here
FINDINGS
```

## Research Strategy

Follow a multi-pass search approach:

1. **Broad survey** — Search for the topic using varied queries. Identify the major themes, canonical references, and key authors/organizations.
2. **Refined deep-dives** — For each major theme, search more specifically. Fetch the most authoritative sources.
3. **Follow references** — When a fetched source cites other works, search for and fetch those too.
4. **Seek contrary evidence** — Actively search for criticisms, failure cases, alternative approaches, and opposing viewpoints.

## Citation Format

Every source you use MUST be cited with this format:

```
[Source N] URL | quality_rating | one-line description
```

Where:
- N matches the source-NNN.md file number
- quality_rating is one of: `authoritative`, `credible`, `anecdotal`, `weak`
- Example: `[Source 3] https://example.com/paper | authoritative | Peer-reviewed study on X`

**Every factual claim in your findings MUST have a citation.** If you cannot cite a source for a claim, mark it as `[UNVERIFIED]`.

## Output Structure

Your final document at {output_path} should contain these sections:

### Key Findings
Substantive findings with inline citations. Group by theme. Every claim cites at least one source.

### Source Registry
Complete list of all sources fetched, in citation format:
```
[Source 1] URL | quality_rating | description
[Source 2] URL | quality_rating | description
...
```

### Evidence Strength Assessment
For each major finding, rate the evidence:
- **Strong**: Multiple independent authoritative sources agree
- **Moderate**: One authoritative source or multiple credible sources
- **Weak**: Only anecdotal or single credible source
- **Conflicting**: Sources disagree — describe the disagreement

### Gaps
What you looked for but could not find. What sources were unavailable. What remains unknown.

### Follow-up Leads
URLs, search queries, or references you found but did not have time to pursue.

### Contradictions
Cases where sources disagree with each other or with the research brief.

Do not repeat findings from prior iterations unless you are deepening, challenging, or adding new citations to them.

After completing your research, also output a brief summary of your key findings as text.
