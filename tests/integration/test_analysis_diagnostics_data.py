from __future__ import annotations

import json

import pytest
from alembic import command
from sqlalchemy import insert, text

from serve.adoption_metrics import all_stratified_metrics
from serve.analysis_dataset import load_analysis_dataset
from serve.analysis_diagnostics import build_diagnostics
from store.models import DetectionEvidence, DetectionRepoFilter, RunItem


@pytest.fixture(scope="module", autouse=True)
def schema(alembic_config):
    command.upgrade(alembic_config, "head")


def test_frozen_run_diagnostics_reconcile_evidence_owners_and_missingness(clean_db):
    owners = [
        {"id": owner_id, "login": f"owner{owner_id}", "type": account_type}
        for owner_id, account_type in (
            (1, "User"),
            (2, "User"),
            (3, "User"),
            (4, "Organization"),
            (5, "Organization"),
        )
    ]
    repos = [
        {
            "id": repo_id,
            "node_id": f"node{repo_id}",
            "full_name": f"owner{owner_id}/repo{repo_id}",
            "owner_id": owner_id,
            "name": f"repo{repo_id}",
            "visibility": "public",
        }
        for repo_id, owner_id in ((1, 1), (2, 1), (3, 2), (4, 3), (5, 4), (6, 5))
    ]
    engine = clean_db(owners=owners, repos=repos)
    spec = {
        "kind": "detect",
        "channels": ["file", "author", "pr_metadata"],
        "source_run_id": None,
    }
    documents = {
        1: {
            "agents": ["A"],
            "channels": {"file": "ok", "author": "ok", "pr_metadata": "ok"},
            "unavailable": False,
            "commit_ratio": 0.0,
            "history_coverage": 1.0,
            "history_complete": True,
            "first_signal_at": "2020-01-01T00:00:00Z",
        },
        2: {
            "agents": ["B"],
            "channels": {"file": "ok", "author": "ok", "pr_metadata": "ok"},
            "unavailable": False,
            "commit_ratio": 0.1,
            "history_coverage": 1.0,
            "history_complete": True,
            "first_signal_at": "2022-01-01T00:00:00Z",
        },
        3: {
            "agents": ["A", "B"],
            "channels": {"file": "ok", "author": "ok", "pr_metadata": "ok"},
            "unavailable": False,
            "commit_ratio": 0.2,
            "history_coverage": 0.5,
            "history_complete": False,
            "first_signal_at": "2021-01-01T00:00:00Z",
        },
        4: {
            "agents": ["C", "D"],
            "channels": {"file": "ok", "author": "ok", "pr_metadata": "ok"},
            "unavailable": False,
            "commit_ratio": None,
            "history_coverage": None,
            "history_complete": None,
            "first_signal_at": None,
        },
        5: {
            "agents": ["A"],
            "channels": {"file": "ok", "author": "ok", "pr_metadata": "ok"},
            "unavailable": False,
            "commit_ratio": 0.4,
            "history_coverage": 1.0,
            "history_complete": True,
            "first_signal_at": "2023-01-01T00:00:00Z",
        },
        6: {
            "agents": [],
            "channels": {"file": "partial", "author": "ok", "pr_metadata": "ok"},
            "unavailable": False,
            "commit_ratio": 0.0,
            "history_coverage": 1.0,
            "history_complete": True,
            "first_signal_at": None,
        },
    }
    facets = [
        (1, "A", "file"),
        (2, "B", "author"),
        (3, "A", "file"),
        (3, "B", "author"),
        (4, "C", "file"),
        (4, "D", "file"),
        (5, "A", "pr_metadata"),
    ]
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO trace_packs (version, authors, files, branches, labels)"
                " VALUES ('diagnostic-pack', '[]', '[]', '[]', '[]')"
            )
        )
        run_id = connection.execute(
            text(
                "INSERT INTO runs (filter_hash, filter_spec, api_version, status, kind,"
                " finished_at) VALUES ('diagnostic-run', CAST(:spec AS jsonb),"
                " '2022-11-28', 'done', 'detect', now()) RETURNING id"
            ),
            {"spec": json.dumps(spec)},
        ).scalar_one()
        connection.execute(
            insert(RunItem),
            [
                {
                    "run_id": run_id,
                    "repo_id": repo_id,
                    "full_name": repos[repo_id - 1]["full_name"],
                    "stargazers": 10,
                    "commit_count": 100,
                    "language": "Python" if repo_id < 5 else "Rust",
                    "country_iso": "US" if repo_id < 5 else "DE",
                    "detection": documents[repo_id],
                }
                for repo_id in documents
            ],
        )
        connection.execute(
            insert(DetectionEvidence),
            [
                {
                    "run_id": run_id,
                    "repo_id": repo_id,
                    "agent": agent,
                    "channel": channel,
                    "evidence": (
                        {"path": f"{agent}.md", "source": "tree"}
                        if channel == "file"
                        else {"login": agent}
                    ),
                    "pack_version": "diagnostic-pack",
                }
                for repo_id, agent, channel in facets
            ],
        )
        connection.execute(
            insert(DetectionRepoFilter),
            [
                {"run_id": run_id, "repo_id": repo_id, "agent": agent, "channel": channel}
                for repo_id, agent, channel in facets
            ],
        )

    dataset = load_analysis_dataset(engine, int(run_id))
    diagnostics = build_diagnostics(dataset)
    _dataset, stratified = all_stratified_metrics(engine, int(run_id), dataset=dataset)

    evidence = diagnostics["evidence_robustness"]
    assert evidence["eligible"] == 5
    assert evidence["definitions"]["broad"]["count"] == 5
    assert evidence["definitions"]["behavioral"]["count"] == 3
    assert evidence["definitions"]["corroborated"]["count"] == 1
    assert evidence["definitions"]["strict"]["count"] == 3
    assert evidence["definitions"]["structural_only"]["count"] == 2

    coverage = diagnostics["observation_coverage"]
    star_row = next(group for group in coverage["dimensions"] if group["key"] == "stars")["rows"][0]
    assert star_row["repos"] == 6
    assert star_row["coverage"]["complete_channels"]["count"] == 5
    assert star_row["coverage"]["commit_denominator"]["count"] == 5
    assert star_row["coverage"]["history_observed"]["count"] == 5
    assert star_row["coverage"]["full_history"]["count"] == 4

    commit_rows = stratified["commit_depth"]
    assert [row["bucket"] for row in commit_rows] == ["100–499"]
    assert commit_rows[0]["coverage_observed"] == 5
    assert commit_rows[0]["full_history"] == 4
    languages = {row["language"]: row for row in stratified["language_adoption"]}
    assert set(languages) == {"Python", "Rust"}
    assert languages["Python"]["repos"] == 4
    assert languages["Rust"]["repos"] == 2

    users = diagnostics["multi_agent_co_use"]["owners"][0]
    organizations = diagnostics["multi_agent_co_use"]["owners"][1]
    user_pairs = next(row for row in users["bands"] if row["band"] == "2")
    assert users["represented_owners"] == 3
    assert users["owners_with_agents"] == 3
    assert [row["set_key"] for row in user_pairs["rankings"]] == ["A + B", "C + D"]
    assert organizations["represented_owners"] == 2
    assert organizations["owners_with_agents"] == 1
    assert organizations["owners_without_agents"] == 1

    intensity = diagnostics["adoption_intensity"]["overall"]
    assert intensity["history_observed"] == 5
    assert intensity["zero_recent"]["count"] == 2
    assert intensity["recent_adopters"] == 3
