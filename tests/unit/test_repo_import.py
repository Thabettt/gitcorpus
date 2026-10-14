from __future__ import annotations

import pytest
from sqlalchemy import text

from serve.repo_import import (
    MAX_IMPORT_ROWS,
    RepoImportError,
    import_repos_as_run,
    parse_repo_csv,
)


def test_parse_app_export_format():
    csv_text = (
        "id,full_name,stargazers,pushed_at,archived,language,license_spdx,"
        "country_iso,geo_confidence\n"
        "101,octo/one,42,2026-01-01T00:00:00Z,false,Rust,MIT,DE,name\n"
        "102,octo/two,7,,,,,,\n"
    )
    parsed = parse_repo_csv(csv_text)
    assert [(row.full_name, row.repo_id, row.stargazers) for row in parsed.rows] == [
        ("octo/one", 101, 42),
        ("octo/two", 102, 7),
    ]
    assert parsed.skipped == 0


def test_parse_repos_rust_format():
    csv_text = (
        "repo,stars,forks,commits,lang_bytes,url\n"
        "AtalayaLabs/OxiCloud,3608,176,2451,9214805,https://github.com/x\n"
    )
    parsed = parse_repo_csv(csv_text)
    assert [(row.full_name, row.repo_id, row.stargazers) for row in parsed.rows] == [
        ("AtalayaLabs/OxiCloud", None, 3608),
    ]


def test_parse_skips_malformed_and_duplicate_rows():
    csv_text = "full_name,stars\nocto/one,10\nocto/one,11\nnot-a-repo,5\n,3\nocto/two,\n"
    parsed = parse_repo_csv(csv_text)
    assert [row.full_name for row in parsed.rows] == ["octo/one", "octo/two"]
    assert parsed.rows[1].stargazers is None
    assert parsed.skipped == 3


def test_parse_rejects_missing_name_column():
    with pytest.raises(RepoImportError, match="full_name or repo"):
        parse_repo_csv("stars,url\n5,https://github.com/x\n")


def test_parse_rejects_oversized_files():
    rows = "\n".join(f"octo/repo{index},1" for index in range(MAX_IMPORT_ROWS + 1))
    with pytest.raises(RepoImportError, match="more than"):
        parse_repo_csv(f"full_name,stars\n{rows}\n")


def test_import_creates_run_items_repos_and_reuses_on_reimport(clean_db):
    engine = clean_db()
    parsed = parse_repo_csv("full_name,stars\nocto/one,42\nocto/two,7\n")
    run_id = import_repos_as_run(engine, parsed, name="repos.csv")
    with engine.connect() as connection:
        run = (
            connection.execute(
                text("SELECT kind, status, fetched, inserted FROM runs WHERE id = :id"),
                {"id": run_id},
            )
            .mappings()
            .one()
        )
        items = (
            connection.execute(
                text(
                    "SELECT repo_id, full_name, stargazers FROM run_items"
                    " WHERE run_id = :id ORDER BY full_name"
                ),
                {"id": run_id},
            )
            .mappings()
            .all()
        )
        repos = (
            connection.execute(text("SELECT id, full_name, owner_id, node_id FROM repos"))
            .mappings()
            .all()
        )
        owners = connection.execute(text("SELECT id, login FROM owners")).mappings().all()
    assert run["kind"] == "find"
    assert run["status"] == "done"
    assert run["fetched"] == run["inserted"] == 2
    assert [item["full_name"] for item in items] == ["octo/one", "octo/two"]
    assert [int(item["repo_id"]) for item in items] == [-1, -2]
    assert [repo["full_name"] for repo in repos] == ["octo/one", "octo/two"]
    assert repos[0]["node_id"] == "import:octo/one"
    assert [owner["login"] for owner in owners] == ["octo"]

    second_id = import_repos_as_run(engine, parsed, name="repos.csv")
    with engine.connect() as connection:
        repo_count = connection.scalar(text("SELECT count(*) FROM repos"))
        owner_count = connection.scalar(text("SELECT count(*) FROM owners"))
        second_items = connection.scalar(
            text("SELECT count(*) FROM run_items WHERE run_id = :id"), {"id": second_id}
        )
    assert second_id != run_id
    assert repo_count == 2
    assert owner_count == 1
    assert second_items == 2
