"""Generate the 2026-11-15 trace-pack catalogue (schema v2).

The pack is built, never hand-edited, from three inputs:

1. **Baseline floor** — the published *Agentic Much?* heuristics (Robbes et al.,
   arXiv 2601.18341 §4.1.2; MSR '26 arXiv 2601.18345 Table 1), as frozen in the
   2026-10-19 CSVs. Every baseline pattern must end up either covered by a rule or
   explained by an entry in the rejection ledger. Nothing is dropped silently.
2. **2026-11-14 catalogue** — the lifecycle-aware re-audit (families, lineage,
   rejections, structured rules). Its rules are kept; root-only path rules are
   widened when that is what it takes to keep a baseline match (nested
   configuration, truncated-tree directory probes).
3. **Extended surfaces** — the curated additions in ``EXTENDED`` below: co-author
   trailers, agent-opened PRs, review bots and GitHub App identities that the
   literature shows carry most agent attribution (docs/findings/2026-11-15-trace-pack-audit.md).

Every rule carries ``provenance.cohort`` (``agentic-much-baseline``,
``2026-11-14``, or ``extended``) and ``provenance.validation``. A baseline-only
count is available from any run by filtering on cohort; an exact replication
of the papers' heuristic set remains pack 2026-10-19.

Usage::

    python scripts/build_trace_pack_2026_11_15.py \
        --baseline packs/patterns \
        --previous ../../packs/sources/2026-11-14/catalogue.json \
        --out packs/sources/2026-11-15/catalogue.json \
        --mapping packs/sources/2026-11-15/baseline-mapping.csv
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
import re
from collections import Counter
from pathlib import Path

VERSION = "2026-11-15"
CHECKED_AT = "2026-11-15"
PAPER_URL = "https://arxiv.org/abs/2601.18341"
PAPER_REF = (
    "Robbes et al., 'Agentic Much?' (arXiv 2601.18341) §4.1.2; heuristics from "
    "'Promises, Perils, and (Timely) Heuristics for Mining Coding Agent Activity' "
    "(MSR '26, arXiv 2601.18345) Table 1"
)
AUDIT_REF = "docs/findings/2026-11-15-trace-pack-audit.md"

# Legacy (v1) subtype -> 2026-11-14 canonical family id.
FAMILY_OF = {
    "Aider": "aider",
    "Alibaba Lingma": "qoder",
    "Amazon Q": "amazon-q-ide",
    "AmazonQ": "amazon-q-ide",
    "Amp": "amp",
    "Atlassian Rovodev": "atlassian-rovo-cli",
    "Augment Code": "augment-code",
    "Baidu Comate": "baidu-comate",
    "Brokk": "brokk",
    "Charlie": "charlie",
    "ChatGPT": "chatgpt",
    "Claude Code": "claude-code",
    "Cline": "cline",
    "Codebuddy": "codebuddy",
    "Codegen": "codegen",
    "Coderabbit": "coderabbit",
    "Codex": "codex",
    "Continue": "continue",
    "Copilot": "copilot",
    "Crush": "crush",
    "Cursor": "cursor",
    "Deepsource": "deepsource",
    "Devin": "devin",
    "Factory": "factory-droid",
    "Factory Droid": "factory-droid",
    "Fly": "phoenix-new",
    "Gemini": "google-antigravity",
    "Generic": "generic",
    "Goose": "goose",
    "GPT-Engineer": "gpt-engineer",
    "Gru": "gru",
    "Jules": "jules",
    "Junie": "junie",
    "Kilo Code": "kilo-code",
    "Kimi Code": "kimi-code-cli",
    "Kiro": "kiro",
    "Langchain Open SWE": "langchain-open-swe",
    "Letta Code": "letta-code",
    "Microsoft Amplifier": "microsoft-amplifier",
    "Mistral Vibe": "mistral-vibe",
    "Ona": "ona",
    "Opencode": "opencode",
    "OpenHands": "openhands",
    "Pi": "pi",
    "Plandex": "plandex",
    "Qodo": "qodo",
    "Qwen Coder": "qwen-coder",
    "Roo Code": "zoo-code",
    "Rulesync": "rulesync",
    "Sentry Seer": "sentry-seer",
    "Serena": "serena",
    "Sketch": "shelley",
    "Sourcery": "sourcery",
    "SpecKit": "speckit",
    "Sweep": "sweep",
    "Taskmaster": "taskmaster",
    "Tessl": "tessl",
    "Trae": "trae",
    "Verd": "verdent",
    "Verdent": "verdent",
    "Warp": "warp",
    "Windsurf": "devin",
    "Abacus": "abacus-ai-agent",
}
# Identity patterns that belong to a different 2026-11-14 family than their v1 label.
FAMILY_OVERRIDE = {
    "roomote-agent": "roomote",
    r"roomote@roocode\.com": "roomote",
    "roomote": "roomote",
}
VARIANT_OF = {"Windsurf": "Windsurf", "Factory": None, "Fly": "Fly.io", "Sketch": "Sketch"}

SEMANTICS = {
    "configuration": {
        "evidence": "configuration",
        "counts_as_repository_presence": True,
        "counts_as_current_presence": True,
        "counts_as_activity": False,
        "counts_as_authorship": False,
        "counts_as_generated_code": False,
        "counts_in_current_ratio": False,
        "counts_as_historical_attribution": False,
    },
    "authorship": {
        "evidence": "authorship",
        "counts_as_repository_presence": True,
        "counts_as_current_presence": True,
        "counts_as_activity": True,
        "counts_as_authorship": True,
        "counts_as_generated_code": True,
        "counts_in_current_ratio": True,
        "counts_as_historical_attribution": False,
    },
    "activity": {
        "evidence": "activity",
        "counts_as_repository_presence": True,
        "counts_as_current_presence": True,
        "counts_as_activity": True,
        "counts_as_authorship": False,
        "counts_as_generated_code": False,
        "counts_in_current_ratio": False,
        "counts_as_historical_attribution": False,
    },
    "review": {
        "evidence": "review_participation",
        "counts_as_repository_presence": True,
        "counts_as_current_presence": True,
        "counts_as_activity": True,
        "counts_as_authorship": False,
        "counts_as_generated_code": False,
        "counts_in_current_ratio": False,
        "counts_as_historical_attribution": False,
    },
    # Recorded for analysis, never counted as adoption (e.g. Copilot Autofix).
    "recorded": {
        "evidence": "generated_code",
        "counts_as_repository_presence": False,
        "counts_as_current_presence": False,
        "counts_as_activity": False,
        "counts_as_authorship": False,
        "counts_as_generated_code": False,
        "counts_in_current_ratio": False,
        "counts_as_historical_attribution": False,
    },
}
SURFACE = {
    "file": "file",
    "workflow": "workflow",
    "author": "git_identity",
    "committer": "git_identity",
    "co_author": "co_author",
    "custom_trailer": "custom_trailer",
    "branch": "branch",
    "label": "pull_request_label",
    "pr_author": "pull_request_author",
    "pr_reviewer": "pull_request_reviewer",
    "pr_commenter": "pull_request_comment",
    "issue_author": "issue_author",
    "issue_commenter": "issue_comment",
    "service_account": "service_account",
    "bot": "bot",
}
ROLE = {
    "author": "commit_author",
    "committer": "commit_committer",
    "co_author": "co_author",
    "branch": None,
    "label": "workflow_label",
    "pr_author": "pr_author",
    "pr_reviewer": "pr_reviewer",
    "pr_commenter": "pr_commenter",
    "issue_author": "issue_author",
    "issue_commenter": "issue_commenter",
}

# Agentic Much? heuristics deliberately not carried forward, each with the
# 2026-11-14 ledger entry (or a new ledger entry below) that explains why.
BASELINE_REJECTED = {
    ("authors", "Claude"): "broad-identity.claude",
    ("authors", "ChatGPT"): "broad-identity.chatgpt",
    ("authors", "Codex"): "broad-identity.codex",
    ("authors", "cursor"): "broad-identity.cursor",
    ("authors", "AI [Aa]ssistant"): "broad-identity.ai-assistant",
    ("authors", "Copilot"): "broad-identity.copilot",
    ("authors", "cline"): "broad-identity.cline",
    ("authors", "junie"): "broad-identity.junie",
    ("authors", "aider"): "baseline.rejected.bare-aider",
    ("authors", r"cline@example\.com"): "baseline.rejected.cline-placeholder-email",
    ("authors", r"abacus-ai-automation\[bot\]"): "abacus.release-bot",
    ("branches", "claudecode/"): "duplicate.claudecode-branch",
    ("files", "CURSOR.md"): "cursor.unsupported-cursor-md",
}

NEW_REJECTIONS = [
    {
        "id": "baseline.rejected.bare-aider",
        "channel": "author",
        "match": {"field": "name", "regex": "^aider$"},
        "note": (
            "Agentic Much? substring 'aider' matches unrelated names and logins (e.g. "
            "'raider', 'aiders'). Replaced by the exact '(aider)' author-name suffix and "
            "aider@aider.chat identities."
        ),
    },
    {
        "id": "baseline.rejected.cline-placeholder-email",
        "channel": "author",
        "match": {"field": "email", "regex": "^cline@example\\.com$"},
        "note": (
            "example.com is a documentation placeholder domain, not a product identity; "
            "no Cline contract uses it."
        ),
    },
]

# --- extended surfaces -------------------------------------------------------
# (family, channel, id suffix, match, semantics, note, source_url, source_type, extra)
APP = r"^\d+\+{login}\[bot\]@users\.noreply\.github\.com$"


def app_email(login: str) -> str:
    return APP.format(login=re.escape(login))


EXTENDED: list[dict] = []


def ext(
    family,
    channel,
    rid,
    match,
    semantics,
    source_url,
    *,
    note=None,
    source_type="official_documentation",
    variant=None,
    layer=None,
    confidence="strong",
    collision="low",
):
    EXTENDED.append(
        {
            "family": family,
            "channel": channel,
            "id": f"{family}.{rid}",
            "match": match,
            "semantics": semantics,
            "note": note,
            "source_url": source_url,
            "source_type": source_type,
            "variant": variant,
            "layer": layer,
            "confidence": confidence,
            "collision": collision,
        }
    )


def ext_identity(family, rid, email_regex, source_url, **kw):
    """One identity: commit author, committer and co-author trailer rules."""
    ext(
        family,
        "author",
        f"{rid}.author",
        {"field": "email", "regex": email_regex, "mode": "fullmatch"},
        "authorship",
        source_url,
        **kw,
    )
    ext(
        family,
        "committer",
        f"{rid}.committer",
        {"field": "email", "regex": email_regex, "mode": "fullmatch"},
        "authorship",
        source_url,
        **kw,
    )
    ext(
        family,
        "co_author",
        f"{rid}.co-author",
        {"token": "Co-Authored-By", "email": email_regex.strip("^$")},
        "authorship",
        source_url,
        **kw,
    )


def ext_login(family, rid, login_regex, channels, semantics, source_url, **kw):
    for channel in channels:
        ext(
            family,
            channel,
            f"{rid}.{channel.replace('_', '-')}",
            {"login_regex": login_regex},
            semantics,
            source_url,
            **kw,
        )


GH_COPILOT = "https://docs.github.com/copilot/concepts/coding-agent/about-copilot-coding-agent"
CENSUS = "https://arxiv.org/abs/2606.24429"
DEBT = "https://github.com/yueyueL/tech-debt-ai-coding/blob/main/collection/config/tools.py"

# Claude Code
ext_identity(
    "claude-code",
    "github-app",
    app_email("claude"),
    DEBT,
    source_type="published_heuristic",
    note="Claude GitHub App commit identity.",
)
ext_login(
    "claude-code",
    "github-app",
    r"claude(?:\[bot\])?",
    ["pr_author", "pr_commenter"],
    "activity",
    "https://docs.anthropic.com/en/docs/claude-code/github-actions",
    confidence="corroborating",
    collision="medium",
    note=(
        "Claude GitHub App opens PRs and replies on @claude mentions. GraphQL drops the "
        "[bot] suffix, so a human account named 'claude' could collide."
    ),
)
ext(
    "claude-code",
    "custom_trailer",
    "generated-footer",
    {
        "footer_regex": r"^(?:\U0001F916\s*)?Generated with \[?Claude Code\]?(?:\(https?://[^)]+\))?\s*$"
    },
    "authorship",
    "https://docs.anthropic.com/en/docs/claude-code/settings",
    note="Default Claude Code commit footer; disabled by includeCoAuthoredBy=false.",
)
ext(
    "claude-code",
    "pr_author",
    "generated-pr-body",
    {"body_regex": r"Generated with \[?Claude Code\]?"},
    "activity",
    "https://docs.anthropic.com/en/docs/claude-code/settings",
    note="Default Claude Code PR-body footer.",
)

# GitHub Copilot coding agent
ext_identity(
    "copilot",
    "swe-agent",
    r"^\d+\+Copilot@users\.noreply\.github\.com$",
    GH_COPILOT,
    note="Copilot coding agent commit identity (copilot-swe-agent[bot]).",
)
ext_login(
    "copilot",
    "swe-agent",
    r"(?:Copilot|copilot-swe-agent(?:\[bot\])?)",
    ["pr_author"],
    "activity",
    GH_COPILOT,
    note="PRs opened by the Copilot coding agent; GraphQL reports the actor as 'Copilot'.",
)
ext(
    "copilot",
    "co_author",
    "autofix",
    {"token": "Co-Authored-By", "name": "Copilot Autofix powered by AI"},
    "recorded",
    DEBT,
    source_type="published_heuristic",
    variant="Copilot Autofix",
    layer="reviewer",
    note=(
        "Code-scanning Autofix (github-advanced-security[bot]). Recorded as a Copilot "
        "variant but not counted as coding-agent adoption by default (audit decision 1)."
    ),
)

# Devin (PR author/commenter logins come from the baseline 'devin-ai-integration')
ext_identity(
    "devin",
    "github-app",
    app_email("devin-ai-integration"),
    DEBT,
    source_type="published_heuristic",
    note="Devin GitHub App commit identity.",
)

# Codex
ext_login(
    "codex",
    "connector",
    r"chatgpt-codex-connector(?:\[bot\])?",
    ["pr_author"],
    "activity",
    "https://developers.openai.com/codex/cloud",
    note="PRs opened through the ChatGPT Codex connector.",
)
ext_login(
    "codex",
    "connector-review",
    r"chatgpt-codex-connector(?:\[bot\])?",
    ["pr_reviewer", "pr_commenter"],
    "review",
    "https://developers.openai.com/codex/cloud",
    layer="reviewer",
    note="Codex code review; review participation, not authorship.",
)

# Gemini / Google
ext_identity(
    "google-antigravity",
    "gemini-cli-app",
    app_email("gemini-cli"),
    DEBT,
    source_type="published_heuristic",
    note="Gemini CLI GitHub App identity.",
)
ext_login(
    "google-antigravity",
    "code-assist-review",
    r"gemini-code-assist(?:\[bot\])?",
    ["pr_reviewer"],
    "review",
    "https://developers.google.com/gemini-code-assist/docs/review-github-code",
    layer="reviewer",
    note="Gemini Code Assist PR review; review participation only.",
)

# Factory, OpenHands, Amp, Aider, Lovable, Sourcery, Codegen, CodeRabbit
ext(
    "amp",
    "custom_trailer",
    "thread-trailer",
    {"token": "Amp-Thread-ID", "value_regex": r"https://ampcode\.com/threads/\S+"},
    "authorship",
    "https://ampcode.com/manual",
    source_type="practitioner_observation",
    confidence="corroborating",
    note="Amp thread link trailer; observed in practice, not yet validated.",
)
ext(
    "aider",
    "author",
    "name-suffix",
    {"field": "name", "regex": r".*\(aider\)", "mode": "fullmatch"},
    "authorship",
    "https://aider.chat/docs/git.html",
    note="Aider appends ' (aider)' to the author name by default (census Type C).",
)
ext(
    "aider",
    "committer",
    "name-suffix",
    {"field": "name", "regex": r".*\(aider\)", "mode": "fullmatch"},
    "authorship",
    "https://aider.chat/docs/git.html",
    note="Aider appends ' (aider)' to the committer name by default.",
)
ext_login(
    "lovable",
    "github-app",
    r"(?:lovable-dev|gpt-engineer-app)(?:\[bot\])?",
    ["pr_author"],
    "activity",
    "https://docs.lovable.dev/",
    note="Lovable GitHub sync app (legacy gpt-engineer-app).",
)
ext_login(
    "sourcery",
    "review-app",
    r"sourcery-ai(?:\[bot\])?",
    ["pr_reviewer"],
    "review",
    "https://docs.sourcery.ai/",
    layer="reviewer",
    note="Sourcery review bot; review participation only.",
)
ext_login(
    "coderabbit",
    "review-app",
    r"coderabbitai(?:\[bot\])?",
    ["pr_reviewer"],
    "review",
    "https://docs.coderabbit.ai/",
    layer="reviewer",
    note="CodeRabbit review bot; review participation only.",
)


# --- helpers -----------------------------------------------------------------
def slug(text: str) -> str:
    text = text.replace("\\", "")
    text = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return text or "x"


def unescape(pattern: str) -> str:
    return pattern.replace("\\", "")


def v1_file_regex(raw: str) -> str:
    """Exact v1 file semantics (attribution.build_channel_regex, is_files=True)."""
    if "." in raw and "\\." not in raw:
        raw = raw.replace(".", "\\.")
    if not raw.startswith("(?:^|/)") and not raw.startswith("^"):
        raw = "(?:^|/)" + raw
    return raw


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [
            {k.strip(): (v or "").strip() for k, v in row.items()} for row in csv.DictReader(handle)
        ]


def file_samples(literal: str) -> list[str]:
    literal = literal.replace("*", "x")
    if literal.endswith("/"):
        return [literal, literal + "x.md", "pkg/" + literal, "pkg/" + literal + "x.md"]
    samples = [literal, "pkg/" + literal]
    if "." not in literal.lstrip("."):
        # Extensionless markers such as `.clinerules` or `.specify` are used both
        # as files and as directories; v1 substring matching accepted both.
        samples += [literal + "/x.md", "pkg/" + literal + "/x.md"]
    return samples


def path_spec_matches(spec: dict, path: str) -> bool:
    if spec.get("root") and "/" in path:
        return False
    regex = spec.get("regex")
    if regex is None:
        if spec.get("equals") is not None:
            return path == spec["equals"]
        return False
    flags = 0 if spec.get("case_sensitive", True) else re.IGNORECASE
    return re.search(regex, path, flags) is not None


def widen(regex: str) -> str:
    if regex.startswith("^") and not regex.startswith("^(?:^|/)"):
        regex = "(?:^|/)" + regex[1:]
    return re.sub(r"/\.\+(\)?)\$$", r"/.*\1$", regex)


def template(previous: dict, family_id: str, channel: str) -> dict:
    for rule in previous["rules"]:
        if rule["family_id"] == family_id and rule["channel"] == channel:
            return rule
    for rule in previous["rules"]:
        if rule["family_id"] == family_id:
            return rule
    return previous["rules"][0]


def make_rule(
    previous,
    families,
    *,
    rid,
    family_id,
    channel,
    match,
    semantics,
    cohort,
    source_url,
    source_type,
    note=None,
    variant=None,
    layer=None,
    confidence="strong",
    collision="low",
    baseline=None,
    validation=None,
    default_state="default-on",
):
    family = families[family_id]
    base = template(previous, family_id, channel)
    sem = dict(SEMANTICS[semantics])
    sem["layer"] = layer or base["semantics"].get("layer", "executor")
    sem["role"] = ROLE.get(channel)
    provenance = {
        "source_url": source_url,
        "source_type": source_type,
        "checked_at": CHECKED_AT,
        "path": None,
        "cohort": cohort,
        "validation": validation or {"status": "unvalidated", "precision": None, "n": None},
    }
    if baseline:
        provenance["baseline_patterns"] = baseline
        provenance["reference"] = PAPER_REF
    return {
        "id": rid,
        "family_id": family_id,
        "family_name": family["name"],
        "channel": channel,
        "surface": SURFACE[channel],
        "forge": "any",
        "observed_as": family["name"],
        "variant": variant,
        "match": match,
        "lineage": copy.deepcopy(base["lineage"]),
        "lifecycle": {
            "status": "legacy" if family["category"] == "legacy-only" else "current",
            "valid_from": None,
            "valid_until": None,
            "uncertainty": f"Introduced in pack {VERSION}; dates not established.",
        },
        "default_state": default_state,
        "confidence": {"class": confidence, "collision_risk": collision},
        "provenance": provenance,
        "semantics": sem,
        "roles": [],
        "enabled": True,
        "disposition": "positive",
        "note": note,
    }


# --- build -------------------------------------------------------------------
def build(baseline_dir: Path, previous_path: Path) -> tuple[dict, list[dict]]:
    previous = json.loads(previous_path.read_text(encoding="utf-8"))
    families = {f["id"]: f for f in previous["families"]}
    catalogue = copy.deepcopy(previous)
    catalogue["version"] = VERSION
    rules: list[dict] = catalogue["rules"]
    rejections: list[dict] = catalogue["rejections"]
    for rule in rules:
        rule["provenance"].setdefault("cohort", "2026-11-14")
        rule["provenance"].setdefault(
            "validation", {"status": "unvalidated", "precision": None, "n": None}
        )
    rejection_ids = {r["id"] for r in rejections}
    template_rejection = next(r for r in previous["rejections"] if r["channel"] == "author")
    for item in NEW_REJECTIONS:
        doc = copy.deepcopy(template_rejection)
        doc.update(
            {
                "id": item["id"],
                "channel": item["channel"],
                "surface": item["channel"],
                "match": item["match"],
                "note": item["note"],
            }
        )
        doc["provenance"] = {
            "source_url": PAPER_URL,
            "source_type": "audit",
            "checked_at": CHECKED_AT,
            "path": AUDIT_REF,
            "cohort": "agentic-much-baseline",
        }
        rejections.append(doc)
        rejection_ids.add(item["id"])

    mapping: list[dict] = []
    positive = lambda r: r.get("enabled", True) and r.get("disposition") == "positive"  # noqa: E731
    paper_validation = {
        "status": "published-pooled",
        "precision": 0.99,
        "n": 1198,
        "note": "Agentic Much? §4.1.3: ~400 files/commits/PRs, two raters.",
    }

    def record(kind, pattern, subtype, outcome, rule_ids):
        mapping.append(
            {
                "channel": kind,
                "pattern": pattern,
                "subtype": subtype,
                "outcome": outcome,
                "rules": " ".join(rule_ids),
            }
        )

    def note_baseline(rule, kind, pattern):
        rule["provenance"].setdefault("baseline_patterns", [])
        entry = f"{kind}:{pattern}"
        if entry not in rule["provenance"]["baseline_patterns"]:
            rule["provenance"]["baseline_patterns"].append(entry)

    def add(rule):
        existing = {r["id"] for r in rules}
        base_id, n = rule["id"], 2
        while rule["id"] in existing:
            rule["id"] = f"{base_id}-{n}"
            n += 1
        rules.append(rule)
        return rule

    def family_for(subtype, pattern):
        return FAMILY_OVERRIDE.get(pattern) or FAMILY_OF.get(subtype.strip())

    # Files
    for row in read_csv(baseline_dir / "files.csv"):
        pattern, subtype = row["pattern"], row["subtype"]
        key = ("files", pattern)
        if key in BASELINE_REJECTED:
            record("files", pattern, subtype, "rejected", [BASELINE_REJECTED[key]])
            continue
        fid = family_for(subtype, pattern)
        regex = v1_file_regex(pattern)
        samples = [s for s in file_samples(unescape(pattern)) if re.search(regex, s)]
        fam_rules = [
            r
            for r in rules
            if positive(r)
            and r["family_id"] == fid
            and r["channel"] in ("file", "workflow")
            and "path" in r["match"]
        ]
        covered = [
            r for r in fam_rules if all(path_spec_matches(r["match"]["path"], s) for s in samples)
        ]
        if covered:
            for r in covered:
                note_baseline(r, "files", pattern)
            record("files", pattern, subtype, "covered", [r["id"] for r in covered])
            continue
        widened = []
        for r in fam_rules:
            spec = r["match"]["path"]
            if not any(path_spec_matches(spec, s) for s in samples):
                continue
            trial = dict(spec, root=False, regex=widen(spec.get("regex") or ""))
            if all(path_spec_matches(trial, s) for s in samples):
                r["match"]["path"] = trial
                r["note"] = (
                    (r.get("note") or "") + " Widened in 2026-11-15 to any depth "
                    "and directory probes (baseline floor)."
                ).strip()
                note_baseline(r, "files", pattern)
                widened.append(r["id"])
                break
        if widened:
            record("files", pattern, subtype, "widened", widened)
            continue
        rule = add(
            make_rule(
                previous,
                families,
                rid=f"{fid}.baseline.file.{slug(pattern)}",
                family_id=fid,
                channel="file",
                match={
                    "path": {"regex": regex, "root": False, "kind": "file", "case_sensitive": True}
                },
                semantics="configuration",
                cohort="agentic-much-baseline",
                source_url=PAPER_URL,
                source_type="published_heuristic",
                baseline=[f"files:{pattern}"],
                validation=paper_validation,
                variant=VARIANT_OF.get(subtype),
                note="Agentic Much? file heuristic, v1 semantics (any depth, substring).",
            )
        )
        record("files", pattern, subtype, "added", [rule["id"]])

    # Branches and labels
    for kind, channel in (("branches", "branch"), ("labels", "label")):
        for row in read_csv(baseline_dir / f"{kind}.csv"):
            pattern, subtype = row["pattern"], row["subtype"]
            key = (kind, pattern)
            if key in BASELINE_REJECTED:
                record(kind, pattern, subtype, "rejected", [BASELINE_REJECTED[key]])
                continue
            fid = family_for(subtype, pattern)
            literal = unescape(pattern).strip("^$")
            sample = literal + ("x" if literal.endswith("/") else "")
            covered = [
                r
                for r in rules
                if positive(r)
                and r["family_id"] == fid
                and r["channel"] == channel
                and r["match"].get("regex")
                and re.search(r["match"]["regex"], sample)
            ]
            if covered:
                for r in covered:
                    note_baseline(r, kind, pattern)
                record(kind, pattern, subtype, "covered", [r["id"] for r in covered])
                continue
            semantics = "activity"
            rule = add(
                make_rule(
                    previous,
                    families,
                    rid=f"{fid}.baseline.{channel}.{slug(pattern)}",
                    family_id=fid,
                    channel=channel,
                    match={"regex": pattern, "case_sensitive": True}
                    if channel == "branch"
                    else {"regex": pattern},
                    semantics=semantics,
                    cohort="agentic-much-baseline",
                    source_url=PAPER_URL,
                    source_type="published_heuristic",
                    baseline=[f"{kind}:{pattern}"],
                    validation=paper_validation,
                    variant=VARIANT_OF.get(subtype),
                    note=f"Agentic Much? {channel} heuristic, v1 semantics (substring).",
                )
            )
            record(kind, pattern, subtype, "added", [rule["id"]])

    # Authors: v1 applied each author pattern to commit identities, co-author
    # trailers, PR authors and issue/PR participants.
    for row in read_csv(baseline_dir / "authors.csv"):
        pattern, subtype = row["pattern"], row["subtype"]
        key = ("authors", pattern)
        if key in BASELINE_REJECTED:
            record("authors", pattern, subtype, "rejected", [BASELINE_REJECTED[key]])
            continue
        fid = family_for(subtype, pattern)
        literal = unescape(pattern)
        ids = []
        if "@" in pattern:
            targets = [
                ("author", {"field": "email", "regex": f"^{pattern}$", "mode": "fullmatch"}),
                ("committer", {"field": "email", "regex": f"^{pattern}$", "mode": "fullmatch"}),
                ("co_author", {"token": "Co-Authored-By", "email": pattern}),
            ]
        elif " " in literal or "(" in literal:
            bounded = f"(?<![A-Za-z0-9]){pattern}(?![A-Za-z0-9])"
            targets = [
                ("author", {"field": "name", "regex": bounded}),
                ("committer", {"field": "name", "regex": bounded}),
                (
                    "co_author",
                    {"token": "Co-Authored-By", "line_regex": f"(?i)co-authored-by:.*{bounded}.*"},
                ),
            ]
        else:
            # v1 matched logins as case-insensitive substrings; keep that.
            login = f".*(?:{pattern}).*"
            targets = [
                ("author", {"field": "login", "regex": pattern}),
                ("committer", {"field": "login", "regex": pattern}),
                (
                    "co_author",
                    {
                        "token": "Co-Authored-By",
                        "line_regex": f"(?i)co-authored-by:\\s*\\S*(?:{pattern})\\S*"
                        "\\s*(?:<[^>]*>)?\\s*",
                    },
                ),
                ("pr_author", {"login_regex": login}),
                ("pr_commenter", {"login_regex": login}),
                ("issue_commenter", {"login_regex": login}),
            ]
        for channel, match in targets:
            sample_email = literal if "@" in literal else None
            covered = None
            for r in rules:
                if not (positive(r) and r["family_id"] == fid and r["channel"] == channel):
                    continue
                m = r["match"]
                if (
                    sample_email
                    and channel in ("author", "committer")
                    and m.get("field") == "email"
                    and m.get("regex")
                    and re.search(m["regex"], sample_email, re.I)
                ):
                    covered = r
                elif (
                    sample_email
                    and channel == "co_author"
                    and m.get("email")
                    and re.fullmatch(m["email"], sample_email, re.I)
                ):
                    covered = r
                if covered:
                    break
            if covered:
                note_baseline(covered, "authors", pattern)
                ids.append(covered["id"])
                continue
            semantics = (
                "authorship"
                if channel in ("author", "committer", "co_author")
                else ("activity" if channel == "pr_author" else "review")
            )
            rule = add(
                make_rule(
                    previous,
                    families,
                    rid=f"{fid}.baseline.identity.{slug(pattern)}.{channel.replace('_', '-')}",
                    family_id=fid,
                    channel=channel,
                    match=match,
                    semantics=semantics,
                    cohort="agentic-much-baseline",
                    source_url=PAPER_URL,
                    source_type="published_heuristic",
                    baseline=[f"authors:{pattern}"],
                    validation=paper_validation,
                    variant=VARIANT_OF.get(subtype),
                    collision="medium" if "@" not in pattern else "low",
                    note="Agentic Much? author heuristic applied to this surface, as in v1.",
                )
            )
            ids.append(rule["id"])
        record("authors", pattern, subtype, "covered+added", ids)

    # Bots: v1 noise filters; keep every one in the ledger.
    noise_regexes = {r["match"].get("regex") for r in rejections if r["channel"] == "bot"}
    bot_template = next(r for r in previous["rejections"] if r["channel"] == "bot")
    for index, row in enumerate(read_csv(baseline_dir / "bots.csv"), start=1):
        pattern = row["pattern"]
        if pattern in noise_regexes:
            record("bots", pattern, row["subtype"], "covered", ["noise ledger"])
            continue
        doc = copy.deepcopy(bot_template)
        doc["id"] = f"noise.baseline-bot-{index:03d}"
        doc["match"] = {"field": "login", "regex": pattern}
        doc["provenance"] = {
            "source_url": PAPER_URL,
            "source_type": "published_heuristic",
            "checked_at": CHECKED_AT,
            "path": None,
            "cohort": "agentic-much-baseline",
        }
        rejections.append(doc)
        record("bots", pattern, row["subtype"], "added-to-noise-ledger", [doc["id"]])

    # Extended surfaces (skip anything an earlier rule already encodes exactly).
    signatures = {
        (r["family_id"], r["channel"], json.dumps(r["match"], sort_keys=True)) for r in rules
    }
    for item in EXTENDED:
        signature = (item["family"], item["channel"], json.dumps(item["match"], sort_keys=True))
        if signature in signatures:
            continue
        add(
            make_rule(
                previous,
                families,
                rid=item["id"],
                family_id=item["family"],
                channel=item["channel"],
                match=item["match"],
                semantics=item["semantics"],
                cohort="extended",
                source_url=item["source_url"],
                source_type=item["source_type"],
                note=item["note"],
                variant=item["variant"],
                layer=item["layer"],
                confidence=item["confidence"],
                collision=item["collision"],
            )
        )

    # Catalogue counts.
    by_category = Counter(f["category"] for f in previous["families"])
    cohorts = Counter(r["provenance"]["cohort"] for r in rules)
    catalogue["catalogue"] = dict(previous["catalogue"])
    catalogue["catalogue"].update(
        {
            "active_total": by_category["active"],
            "rules_total": len(rules),
            "rejections_total": len(rejections),
            "rules_by_cohort": dict(sorted(cohorts.items())),
            "baseline_patterns_total": len(mapping),
            "baseline_patterns_rejected": sum(1 for m in mapping if m["outcome"] == "rejected"),
            "built_from": {
                "baseline": "packs/sources/2026-10-19 (Agentic Much? heuristics)",
                "previous": "packs/sources/2026-11-14/catalogue.json",
                "generator": "scripts/build_trace_pack_2026_11_15.py",
                "audit": AUDIT_REF,
            },
        }
    )
    return catalogue, mapping


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--previous", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    args = parser.parse_args()
    catalogue, mapping = build(args.baseline, args.previous)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(catalogue, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    with args.mapping.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["channel", "pattern", "subtype", "outcome", "rules"]
        )
        writer.writeheader()
        writer.writerows(mapping)
    outcomes = Counter(m["outcome"] for m in mapping)
    print(
        f"rules={len(catalogue['rules'])} rejections={len(catalogue['rejections'])} "
        f"baseline={len(mapping)} {dict(outcomes)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
