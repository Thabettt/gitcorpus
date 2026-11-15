"""Plain-language explanations for the analysis dashboard figures.

The dashboard is read by people who know how to read a chart but not
necessarily how this corpus defines adoption, evidence, or coverage.  Each
entry therefore answers a fixed sequence of questions: what question the
figure is for, what data stands behind it, how to read the marks, what a
concrete reading looks like, and what it cannot establish.  Shared jargon is
defined once in ``CHART_GLOSSARY`` and referenced by key so definitions stay
consistent across figures.
"""

from __future__ import annotations

from typing import Any

CHART_GLOSSARY: dict[str, tuple[str, str]] = {
    "agent": (
        "Coding agent",
        "A named AI coding tool or assistant tracked by the corpus. One repository "
        "can show evidence for several agents.",
    ),
    "frame": (
        "Eligible frame",
        "The repositories this run can legitimately analyse: a usable detection "
        "document exists and every selected detection channel succeeded. "
        "Repositories outside the frame stay visible in coverage tables but do not "
        "enter adoption denominators.",
    ),
    "channel": (
        "Detection channel",
        "One way the scanner looks for agent evidence, such as a committed config "
        "file, an author or commit trailer, or pull-request metadata. Different "
        "channels see different parts of the same usage.",
    ),
    "broad": (
        "Broad evidence",
        "At least one non-bot detection channel found a trace of the agent. This is "
        "the most permissive headline definition.",
    ),
    "strict": (
        "Strict evidence",
        "Evidence from a behavioural channel (author, commit trailer, or PR metadata) "
        "or corroboration from at least two channel families. It is designed to "
        "exclude structural traces that may not reflect actual use.",
    ),
    "wilson": (
        "95% Wilson interval",
        "A range around an observed share that accounts for sample size. Small "
        "denominators produce wide intervals; a wide interval means the exact value "
        "is uncertain.",
    ),
    "repo_weighted": (
        "Repo-weighted",
        "Every eligible repository counts equally. An owner with 500 repositories "
        "contributes 500 times as much as a single-repository owner.",
    ),
    "owner": (
        "Owner",
        "The GitHub account, either a User or an Organization, that owns a "
        "repository. User and Organization results are never pooled.",
    ),
    "marker": (
        "Shared marker",
        "Evidence of a convention rather than a product: AGENTS.md, an “AI "
        "Assistant” identity, or an “ai-generated” label. Shared markers are shown "
        "for completeness but never counted as agent adoption.",
    ),
    "coverage": (
        "Coverage",
        "The share of repositories for which a measure could actually be computed. "
        "It tells you whether a denominator is trustworthy, not whether adoption is "
        "high.",
    ),
    "commit_ratio": (
        "Commit ratio",
        "The share of eligible inspected commits attributed to an agent. Commits "
        "that cannot be attributed, and merge commits where the scanner excludes "
        "them, stay outside the denominator.",
    ),
    "pervasive": (
        "Pervasive use",
        "At least 20% of eligible inspected commits were attributed to an agent. The "
        "threshold is a reporting convention, not a natural boundary.",
    ),
    "ecdf": (
        "Empirical cumulative distribution",
        "An ECDF plots, for each intensity value, the share of adopters at or below "
        "it. It shows the whole distribution without choosing bins.",
    ),
    "history_window": (
        "History window",
        "The portion of the default branch that the run actually inspected. History "
        "coverage is that window divided by the frozen total commit count.",
    ),
    "fingerprint": (
        "Fingerprint",
        "A concrete repository-visible trace, such as a specific config filename, "
        "dependency marker, or commit pattern, linked to one detection channel.",
    ),
    "cohort": (
        "Creation cohort",
        "A group of repositories defined by creation date: the installed base before "
        "the study cutoff, or a later creation quarter.",
    ),
    "percentile": (
        "Percentile",
        "The value below which a given share of observations fall. P50 is the "
        "median; P10 is the value below which 10% fall.",
    ),
    "bounded_date": (
        "Bounded date",
        "The earliest date observable inside this run's window. It is not an agent's "
        "true first use.",
    ),
    "gdp_pc": (
        "GDP per capita",
        "A country-level economic measure matched to the repository owner's country. "
        "It describes the country, not the individual developer.",
    ),
    "sensitivity_gap": (
        "Sensitivity gap",
        "The difference between two evidence definitions on the same denominator. It "
        "is not a confidence interval.",
    ),
    "unknown_metadata": (
        "Unknown stratum",
        "Missing or unresolved metadata is kept as its own group, usually labelled "
        "“Unknown”, instead of being dropped or silently treated as zero.",
    ),
    "detected": (
        "Detected repository",
        "A repository with at least one observed non-bot agent trace, even if it "
        "falls outside the fully eligible frame.",
    ),
    "star": (
        "Star",
        "GitHub's public bookmark count. Stars measure attention, not code volume, "
        "team size, or adoption intent.",
    ),
}


CHART_EXPLANATIONS: dict[str, dict[str, Any]] = {
    "agent-share": {
        "kind": "Headline measure",
        "question": (
            "How widely is each coding agent observed across the repositories in " "this corpus?"
        ),
        "context": (
            "This compares two prevalence estimates for the same agents. The scanned "
            "denominator includes every repository in the frozen detection run; the "
            "readable denominator keeps only repositories with a usable detection "
            "document. The distance between the two dots shows how much "
            "non-analysable repositories affect the headline. Prevalence here means "
            "“evidence was observed”, not “the developer says they use it”."
        ),
        "how": [
            "Each row is one agent; the two dots are the scanned and readable estimates.",
            "Horizontal position is a percentage. A dot further right means more "
            "repositories with observed evidence.",
            "Whiskers are 95% intervals. Overlapping intervals mean the ordering of "
            "close agents is not reliable.",
            "Rows are sorted for readability, so compare values rather than rank alone.",
            "A repository can count toward several agents, so shares may sum past 100%.",
        ],
        "example": (
            "An agent at 12% on both dots has evidence in roughly 12 of every 100 "
            "repositories under each denominator. A much lower readable estimate would "
            "mean unreadable repositories were disproportionately important to the "
            "scanned number."
        ),
        "terms": ["agent", "frame", "wilson", "channel"],
        "caveat": (
            "These are observed traces, not a survey of developer intent. An agent "
            "used without leaving a detectable trace is invisible here."
        ),
    },
    "generic-markers": {
        "kind": "Validity diagnostic",
        "question": (
            "How much shared, vendor-neutral evidence exists, and how is it kept out "
            "of the agent counts?"
        ),
        "context": (
            "Some evidence does not identify a product. An AGENTS.md file, an “AI "
            "Assistant” author identity, or an “ai-generated” pull-request label "
            "shows that a repository participates in an AI convention without saying "
            "which agent is used. Treating that evidence as an agent would create a "
            "phantom product and inflate every adoption share. The top dataset lists "
            "these shared markers; the second dataset, when present, lists agents "
            "inferred from a single explicit addressee inside a shared file."
        ),
        "how": [
            "Each lollipop is one marker and the number of repositories that show it.",
            "Colour groups the marker by source: file, author identity, or label.",
            "Switch datasets with the selector: shared markers are the common case; "
            "content fallbacks are rare and always marked as such.",
            "Shared markers never appear in agent prevalence, agent counts, or "
            "adoption denominators.",
            "A repository can carry several markers, so marker counts are not "
            "mutually exclusive.",
        ],
        "example": (
            "If AGENTS.md appears in 1,200 repositories but no product is named, those "
            "repositories show a shared marker and zero agents. The lollipop records "
            "the practice without adding 1,200 phantom adopters."
        ),
        "terms": ["marker", "agent", "channel"],
        "caveat": (
            "A missing marker is not evidence of absence: a repository may use an "
            "agent without committing an AGENTS.md file or using a labelled identity. "
            "Content fallbacks are conservative and deliberately cover only files "
            "that address exactly one named agent."
        ),
    },
    "agents-country": {
        "kind": "Headline measure",
        "question": "Which agents appear in which countries, and where are they concentrated?",
        "context": (
            "Rows are countries and columns are agents. Each cell divides repositories "
            "with evidence for that agent by all readable repositories from that "
            "country, so large and small countries can be compared on the same scale. "
            "The matrix maps this corpus; it is not a representative sample of the "
            "world's developers."
        ),
        "how": [
            "Read across a row to compare agents within one country.",
            "Read down a column to compare one agent across countries.",
            "Darker cells and larger numbers mean a larger share; the n column is the "
            "row denominator.",
            "Hover a cell for the exact percentage and repository count.",
            "Treat strong colours in rows with small n as noisy evidence.",
        ],
        "example": (
            "A cell showing 18% with n=250 means 45 of that country's 250 readable "
            "repositories carried evidence for that agent."
        ),
        "terms": ["agent", "frame", "unknown_metadata"],
        "caveat": (
            "Country is the owner's public location, not where the code is written. "
            "Organization-owned repositories are attributed to the organization's "
            "registered country."
        ),
    },
    "adoption": {
        "kind": "Headline measure",
        "question": "What mix of commit-intensity tiers does the observed corpus show?",
        "context": (
            "The bar divides observed repositories into ordered tiers based on the "
            "share of eligible commits attributed to an agent: none, limited, "
            "moderate, or pervasive. It is a composition chart, so the whole bar is "
            "one denominator and the segments are mutually exclusive. The statistic "
            "strip repeats the same picture for the eligible and scanned frames."
        ),
        "how": [
            "The leftmost segment is the lowest intensity, usually no observed agent "
            "use; the rightmost is pervasive use.",
            "Segment width is that tier's share of repositories, so the widths add " "to 100%.",
            "Hover a segment for its exact share and count.",
            "Use “Unavailable” in the stat strip to see how much of the frame could "
            "not be classified.",
            "Open the adoption-intensity panel for the full distribution among " "adopters.",
        ],
        "example": (
            "If “No agent” fills 55% of the bar, just under half of the observed frame "
            "shows at least some agent evidence; the remaining segments show how heavy "
            "that use is."
        ),
        "terms": ["commit_ratio", "pervasive", "frame", "agent"],
        "caveat": (
            "The tiers describe attributed commits inside the inspected window. They "
            "do not measure the share of code written by AI or the importance of the "
            "agent to the project."
        ),
    },
    "country-adoption": {
        "kind": "Headline measure",
        "question": "How does agent-use prevalence differ across countries?",
        "context": (
            "Each row is a country with at least one eligible repository. The estimate "
            "is repo-weighted, so every eligible repository counts once regardless of "
            "owner. Countries with few repositories get wide intervals, which is the "
            "main reason two similar point estimates may not be meaningfully different."
        ),
        "how": [
            "Move down the rows to compare countries; the dot is the point estimate.",
            "The horizontal line is a 95% interval, and a triangle marks fewer than "
            "10 eligible repositories.",
            "Look at interval width before comparing small differences between dots.",
            "Treat overlapping intervals as compatible with the same underlying rate.",
            "Use the data tables for exact counts and the unsorted country list.",
        ],
        "example": (
            "Two countries at 20% and 24% with overlapping intervals should be read as "
            "similar. A four-point gap with narrow, non-overlapping intervals is "
            "stronger evidence of a difference in this corpus."
        ),
        "terms": ["wilson", "repo_weighted", "frame", "unknown_metadata"],
        "caveat": (
            "These are repo-weighted country associations, not representative national "
            "estimates. Repositories cluster within owners, so the intervals understate "
            "real-world dependence."
        ),
    },
    "size-adoption": {
        "kind": "Headline measure",
        "question": "Does agent use change with repository size?",
        "context": (
            "Repositories are grouped into frozen disk-size bands. The chart shows "
            "whether larger codebases are more or less likely to carry agent evidence. "
            "Size is measured once from the source snapshot, so later edits do not "
            "change a repository's band."
        ),
        "how": [
            "The horizontal axis runs from smaller to larger size bands.",
            "Choose “Any signal” or a specific agent from the selector.",
            "The dot is prevalence and the whisker is its 95% interval.",
            "A flat profile means size is a weak differentiator; a steady slope means "
            "use rises or falls with size.",
            "A gap in the line means the band had no eligible repositories.",
        ],
        "example": (
            "If prevalence climbs steadily from the smallest to the largest band while "
            "the intervals stay narrow, large repositories are more likely to show "
            "agent evidence. If the intervals overlap heavily, the pattern is weak."
        ),
        "terms": ["frame", "wilson", "agent"],
        "caveat": (
            "Disk size is a rough proxy for project scale. It includes vendored code, "
            "generated files, and assets, so it is not a measure of team size or code "
            "complexity."
        ),
    },
    "agent-debuts": {
        "kind": "Headline measure",
        "question": "When do agents first become visible in this corpus?",
        "context": (
            "For each agent, the line runs from the earliest creation date among "
            "repositories carrying it to the earliest observed signal in this run. "
            "Both endpoints are bounded by what the run could see. The left endpoint "
            "describes the repositories; the right endpoint describes the first "
            "observed trace."
        ),
        "how": [
            "Each row is one agent; the left endpoint is earliest repository creation.",
            "The right endpoint is the earliest observed signal date for that agent.",
            "A long line means the agent appeared on repositories that had already "
            "existed for a while.",
            "The repos and dated columns show how many repositories support the row.",
            "Rows are chronological, so rows near the top are the earliest observations.",
        ],
        "example": (
            "A line that starts in 2019 and ends in 2024 does not mean the agent existed "
            "in 2019. It means the agent was first observed in this run on repositories "
            "created as early as 2019."
        ),
        "terms": ["bounded_date", "agent", "coverage"],
        "caveat": (
            "Earliest observed signal is not true first use. Public visibility, "
            "repository sampling, and channel coverage can all hide earlier adoption."
        ),
    },
    "fingerprints": {
        "kind": "Headline measure",
        "question": "Which concrete repository traces identify an agent?",
        "context": (
            "A fingerprint is a repository-visible marker linked to one detection "
            "channel, such as a config filename, dependency, or commit pattern. The "
            "chart ranks the five fingerprints found in the most repositories for the "
            "selected agent. It describes the detection surface, not the agent's "
            "capabilities or the quality of its use."
        ),
        "how": [
            "Select an agent from the selector.",
            "Each bar counts repositories where that fingerprint appeared; a longer "
            "bar means a more widespread trace.",
            "The tooltip names the channel and the earliest observed date for that " "fingerprint.",
            "Fingerprints overlap, so one repository can contribute to several bars.",
            "Compare mixes across agents to see which traces dominate each agent's " "evidence.",
        ],
        "example": (
            "If a config-file fingerprint leads with 800 repositories and a commit-"
            "trailer fingerprint follows with 120, the agent is mostly detected through "
            "committed configuration in this corpus."
        ),
        "terms": ["fingerprint", "channel", "agent"],
        "caveat": (
            "Fingerprints reveal detectable traces, not depth of use. A widely copied "
            "config can outrank meaningful but sparsely documented adoption."
        ),
    },
    "country-wealth": {
        "kind": "Headline measure",
        "question": ("Do countries with higher GDP per capita also show higher agent adoption?"),
        "context": (
            "Each bubble is a country. GDP per capita comes from a country-level "
            "economic series matched to the owner's country, and adoption is "
            "repo-weighted within that country. The fitted line is unweighted, so each "
            "qualifying country contributes one point regardless of how many "
            "repositories it has."
        ),
        "how": [
            "Horizontal position is GDP per capita on a log scale; vertical position is "
            "observed adoption.",
            "Bubble area reflects readable repository count, and the whisker is the "
            "country's 95% interval.",
            "The straight line is a least-squares fit across countries above the "
            "minimum-size threshold.",
            "A positive slope means richer countries show higher adoption in this " "corpus.",
            "Tooltips flag influential countries by Cook's distance; check whether "
            "removing one country changes the story.",
        ],
        "example": (
            "A fit rising from about 8% at $10k GDP per capita to 25% at $50k is a "
            "positive ecological association. It is not evidence that raising income "
            "raises adoption."
        ),
        "terms": ["gdp_pc", "repo_weighted", "wilson"],
        "caveat": (
            "Country-level association cannot establish causation and can be driven by "
            "a handful of countries. The bootstrap and leave-one-out ranges show how "
            "fragile the fit is."
        ),
    },
    "creation-cohorts": {
        "kind": "Headline measure",
        "question": "Is agent use different in older versus newer repositories?",
        "context": (
            "Repositories are grouped by creation date: the installed base before the "
            "study cutoff and quarterly cohorts after it. This is a cross-sectional "
            "snapshot, not a longitudinal study that follows the same repositories over "
            "time. Cohort differences mix age with selection into the corpus."
        ),
        "how": [
            "Cohorts run from oldest to newest along the horizontal axis.",
            "Each line is an evidence definition: any signal, committed configuration, "
            "or recent commit use.",
            "Dots are prevalence and whiskers are 95% intervals.",
            "Check interval overlap before treating a dip or rise as a real cohort " "difference.",
            "Use the data tables for exact cohort counts and small-sample flags.",
        ],
        "example": (
            "If recent commit use rises in newer cohorts while any-signal evidence "
            "stays flat, newer repositories may be using agents more intensively "
            "without a larger share ever showing a trace."
        ),
        "terms": ["cohort", "frame", "wilson", "channel"],
        "caveat": (
            "Newer repositories have had less time to accumulate history, and older "
            "ones may be archived or transferred. Cohort patterns describe this frozen "
            "snapshot, not a trend over calendar time. Repositories with no recorded "
            "creation date (currently CSV-import placeholders) are excluded and counted "
            "in the figure subtitle."
        ),
    },
    "star-tiers": {
        "kind": "Headline measure",
        "question": "Are popular repositories more likely to show agent use?",
        "context": (
            "Stars are grouped into log-scaled popularity bands. The chart compares "
            "prevalence across those bands under three evidence definitions. Stars "
            "measure public attention, not code volume, team size, or adoption intent, "
            "so the pattern is descriptive."
        ),
        "how": [
            "The horizontal axis runs from few stars to many.",
            "Each line is one evidence definition; isolate a line with the selector when "
            "they overlap.",
            "Dots are prevalence and whiskers are 95% intervals.",
            "A rising line means popular repositories are more likely to show agent " "evidence.",
            "Check whether the pattern holds across all three definitions before " "trusting it.",
        ],
        "example": (
            "If all three lines rise from the lowest to the highest band, the popularity "
            "gradient is consistent. If only broad evidence rises, the pattern may "
            "reflect more config files rather than more actual use."
        ),
        "terms": ["star", "wilson", "broad", "strict"],
        "caveat": (
            "Popularity correlates with visibility, project type, and contributor count. "
            "The gradient is not a causal effect of stars."
        ),
    },
    "commit-depth": {
        "kind": "Headline measure",
        "question": "Does agent use differ between shallow and deep repositories?",
        "context": (
            "Repositories are grouped by lifetime default-branch commit count. The first "
            "series measure adoption; the last two describe how much of each "
            "repository's history the run actually inspected. An adoption number is only "
            "credible when the inspected window is large enough to represent the "
            "repository."
        ),
        "how": [
            "The horizontal axis is an ordered lifetime commit-count band.",
            "The first three lines are different evidence definitions for adoption.",
            "“Median history coverage” is the typical inspected share within a band.",
            "“Full-history coverage” is the share whose inspected window reached the "
            "frozen total.",
            "n/a means this run did not record coverage metadata, not that coverage was " "zero.",
        ],
        "example": (
            "A deep-commit band with high adoption but low median coverage may be "
            "measuring only a small inspected window. Read it cautiously until coverage "
            "is shown to be adequate."
        ),
        "terms": ["history_window", "coverage", "broad", "strict"],
        "caveat": (
            "Commit depth proxies maturity and repository conventions. Large monorepos "
            "and small active projects can share a band while differing in how agents "
            "are used."
        ),
    },
    "language-adoption": {
        "kind": "Headline measure",
        "question": "How does agent use vary by primary repository language?",
        "context": (
            "Each row is a primary language from the frozen source snapshot. Prevalence "
            "is repo-weighted within language, and the extra series shows which agent "
            "has the largest share of observed use there. A single primary label hides "
            "repositories that mix several languages."
        ),
        "how": [
            "Read down the rows to compare languages; the dot is prevalence.",
            "The line is a 95% interval; wide intervals mean the estimate rests on few "
            "repositories.",
            "“Top-agent share” identifies the leading agent within each language.",
            "Use the data tables for exact counts and the full language list.",
            "A high top-agent share means that agent dominates observed traces, not that "
            "it is better.",
        ],
        "example": (
            "If Python shows 30% prevalence with a top-agent share of 45%, the leading "
            "agent accounts for just under half of Python's observed agent evidence."
        ),
        "terms": ["frame", "wilson", "repo_weighted", "agent"],
        "caveat": (
            "Primary language is one label assigned from the snapshot. Polyglot "
            "repositories and generated code can distort the grouping."
        ),
    },
    "diagnostic-evidence-robustness": {
        "kind": "Validity diagnostic",
        "question": "Does the adoption headline survive a stricter definition of evidence?",
        "context": (
            "The same eligible repositories are scored under several predeclared "
            "evidence rules. Broad evidence accepts any non-bot trace; behavioural "
            "evidence requires author, trailer, or PR metadata; corroborated evidence "
            "requires two channel families; strict evidence combines behavioural and "
            "corroborated. The chart shows how much the conclusion depends on the rule."
        ),
        "how": [
            "Each row is an evidence definition; the dot is its prevalence.",
            "Whiskers are 95% intervals for the binomial estimate.",
            "The sensitivity gap is broad minus strict, in percentage points.",
            "A small gap means the headline is robust to the rule; a large gap means "
            "loose evidence drives it.",
            "Do not interpret the gap as a confidence interval.",
        ],
        "example": (
            "If broad is 22% and strict is 14%, eight points of the headline depend on "
            "evidence that is structural or uncorroborated. Report that gap alongside "
            "the headline."
        ),
        "terms": ["broad", "strict", "channel", "wilson", "sensitivity_gap"],
        "caveat": (
            "The rules are fixed before looking at results, but they remain judgement "
            "calls. A strict rule can undercount real use that left weak documentation."
        ),
    },
    "diagnostic-observation-coverage": {
        "kind": "Validity diagnostic",
        "question": "Where can this corpus actually support the adoption estimates?",
        "context": (
            "Adoption is only meaningful where the data could be observed. This matrix "
            "shows, for each stratum, what share of repositories passed each "
            "prerequisite: readable, complete channels, successful file scan, valid "
            "commit denominator, history observed, and full history. It is a data-quality "
            "map, not an outcome measure."
        ),
        "how": [
            "Choose a dimension (country, language, star tier, or commit tier) and how "
            "many strata to show.",
            "Each column is a coverage measure; each cell is eligible repositories "
            "divided by all repositories in that stratum.",
            "Darker cells mean higher coverage.",
            "n/a means the channel was not selected or the run did not record the field.",
            "Low coverage warns that the corresponding outcome is based on a smaller or "
            "biased subset, not that adoption is low.",
        ],
        "example": (
            "A country with 99% readable coverage but 40% history coverage can support a "
            "prevalence estimate, yet its intensity estimates rest on a smaller and "
            "possibly biased subset."
        ),
        "terms": ["coverage", "frame", "history_window", "channel"],
        "caveat": (
            "High coverage means the denominator is trustworthy; it says nothing about "
            "whether adoption is high or low. Coverage can also differ systematically "
            "between strata."
        ),
    },
    "diagnostic-owner-cluster": {
        "kind": "Validity diagnostic",
        "question": "Does the answer change when owners rather than repositories are the unit?",
        "context": (
            "A repository-weighted rate treats every repository equally. An "
            "owner-weighted rate first computes each owner's adoption, then treats every "
            "owner equally. The chart compares both for GitHub Users and Organizations "
            "separately, so a few large owners cannot silently dominate the story."
        ),
        "how": [
            "Each account type has two dots: repo-weighted and owner-weighted.",
            "A gap means multi-repository owners pull the repo-weighted result away from "
            "the typical owner.",
            "When at least 10 owners exist, whiskers resample whole owner clusters and "
            "preserve within-owner dependence.",
            "Read Users and Organizations separately; never pool them into a person-level "
            "claim.",
            "Use the data tables for owner counts, repositories per owner, and " "concentration.",
        ],
        "example": (
            "If repo-weighted adoption is 30% but owner-weighted adoption is 12%, a small "
            "set of owners with many repositories is driving most of the observed "
            "adoption."
        ),
        "terms": ["repo_weighted", "owner", "frame"],
        "caveat": (
            "Owner clusters model dependence within one account, not dependence across "
            "the wider ecosystem. Organizations are not people."
        ),
    },
    "diagnostic-robust-debut": {
        "kind": "Validity diagnostic",
        "question": (
            "When does each agent's observed use begin, without relying on one extreme " "date?"
        ),
        "context": (
            "For each agent, repositories carrying it contribute one bounded observed "
            "date. The chart reports P0, P10, and P50 across those dates, so a single "
            "unusually early repository cannot define the debut. Dated coverage shows how "
            "many contributing repositories actually had a usable date."
        ),
        "how": [
            "P0 is the earliest observed signal, P10 is the 10th percentile, and P50 is "
            "the median.",
            "Each dot is one percentile for one agent; read across a row to see the " "spread.",
            "A large gap between P0 and P50 means the earliest observation is an outlier "
            "relative to the typical repository.",
            "Dated coverage is the share of contributing repositories with a usable date.",
            "Compare agents by the median, not by P0 alone.",
        ],
        "example": (
            "If P0 is 2023 but P50 is 2025, the agent was first seen in 2023, yet half of "
            "its contributing repositories only show it from 2025 onward."
        ),
        "terms": ["bounded_date", "percentile", "coverage", "agent"],
        "caveat": (
            "These are observed dates inside the run's window, not true first use. "
            "Evidence rows in this run do not carry per-evidence timestamps, so the "
            "repository-level date is the finest available."
        ),
    },
    "diagnostic-adoption-intensity": {
        "kind": "Validity diagnostic",
        "question": "Among repositories that use agents, how heavily do they use them?",
        "context": (
            "The ECDF plots the whole distribution of commit intensity rather than a few "
            "summary bars. Intensity is the share of eligible inspected commits "
            "attributed to an agent in each repository. Repositories with zero recent use "
            "are excluded from the curve and reported separately, because they answer a "
            "different question: whether adoption happened at all."
        ),
        "how": [
            "The horizontal axis is intensity from 0% to 100%; the vertical axis is the "
            "cumulative share of recent adopters.",
            "A steep rise on the left means most adopters use agents lightly. A curve "
            "that stays low and climbs late means a minority use them heavily.",
            "Choose a population from the selector to compare overall, star, commit, "
            "cohort, language, or country subsets.",
            "Read the stat strip for P25, P50, P75, P90, zero recent use, and the "
            "pervasive share.",
            "Use the curve for shape and the percentiles for exact comparisons.",
        ],
        "example": (
            "If the curve reaches 80% by intensity 25%, four out of five recent adopters "
            "attribute at most a quarter of their eligible commits to an agent. The "
            "heavy tail beyond that is small."
        ),
        "terms": ["ecdf", "commit_ratio", "pervasive", "frame"],
        "caveat": (
            "The measure conditions on recent adopters with a valid commit denominator. "
            "The 20% pervasive threshold is a reporting convention: changing it changes "
            "the headline share, not the underlying distribution."
        ),
    },
    "diagnostic-multi-agent-co-use": {
        "kind": "Validity diagnostic",
        "question": (
            "How often do multiple agents appear in the same repository or under the " "same owner?"
        ),
        "context": (
            "The top strip counts distinct observed agents per detected repository. The "
            "tables aggregate each owner's canonical agent union across every repository "
            "that owner has in the run. This is about coexistence of traces, not about "
            "agents collaborating on one task."
        ),
        "how": [
            "Read the strip left to right: 1 agent, 2–5, 6–9, 10+.",
            "A long “1” segment means most detected repositories show a single agent.",
            "Use the account selector to switch between Users and Organizations.",
            "Use the band selector to inspect exact agent sets for owners with a given "
            "number of agents.",
            "Rankings are exact sets ordered by owner count; ties break lexically.",
        ],
        "example": (
            "If 70% of detected repositories show one agent and the 2–5 band carries most "
            "of the rest, multi-agent coexistence is present but not the typical case."
        ),
        "terms": ["agent", "owner", "detected"],
        "caveat": (
            "Co-use counts observed traces. It does not prove the agents worked on the "
            "same task, at the same time, or with the same intensity, and owner unions "
            "span all their repositories in this run."
        ),
    },
}


def explanation_for(key: str) -> dict[str, Any] | None:
    """Return one chart's explanation with glossary entries resolved."""

    explanation = CHART_EXPLANATIONS.get(key)
    if explanation is None:
        return None
    return {
        **explanation,
        "terms": [
            {"term": CHART_GLOSSARY[term_key][0], "meaning": CHART_GLOSSARY[term_key][1]}
            for term_key in explanation.get("terms", ())
        ],
    }
