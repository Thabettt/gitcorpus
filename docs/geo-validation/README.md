# Owner Geolocation Validation

This workflow validates the resolver against blinded, independently annotated real profile evidence. It deliberately separates resolver development from human ground truth.

## 1. Create a deterministic sample

```powershell
$env:PYTHONPATH = "src"
python scripts/geo_benchmark.py sample `
  --output geo-benchmarks/geo-v1 `
  --size 3000 `
  --seed 20261108
```

The workspace contains a content-hashed sample, frozen annotation policy, frozen artifact schema, frozen adversarial challenge corpus, frozen release gates, sampling probabilities, resolver/data provenance, and no login, GitHub id, or full website hostname. Related normalized location families are assigned together to an 80% untouched holdout and a 20% development split. Sparse strata of at most 50 cases are sampled as a census so rare scripts and evidence shapes are not erased by proportional sampling.

## 2. Create two blinded packs

Use unrelated seeds and independent annotators:

```powershell
python scripts/geo_benchmark.py pack --workspace geo-benchmarks/geo-v1 --annotator annotator-a --seed 101
python scripts/geo_benchmark.py pack --workspace geo-benchmarks/geo-v1 --annotator annotator-b --seed 202
```

Prediction, confidence, frequency, stratum, and sampling weight are absent from each pack.

## 3. Annotate independently

```powershell
python scripts/geo_benchmark.py annotate `
  --pack geo-benchmarks/geo-v1/packs/annotator-a.jsonl `
  --output geo-benchmarks/geo-v1/annotations/annotator-a.jsonl
```

Repeat for annotator B. The terminal workflow autosaves after every case and resumes safely. Annotators must follow `annotation-policy.md` and must not search for owners or inspect predictions.

## 4. Compare and adjudicate

```powershell
python scripts/geo_benchmark.py adjudicate `
  --workspace geo-benchmarks/geo-v1 `
  --annotations-a geo-benchmarks/geo-v1/annotations/annotator-a.jsonl `
  --annotations-b geo-benchmarks/geo-v1/annotations/annotator-b.jsonl
```

Exact agreements are retained. Only disagreements are shown to the third adjudicator. Use `--prepare-only` to create the disagreement sheet without entering the interactive adjudication session.

Finalize after every disagreement is completed:

```powershell
python scripts/geo_benchmark.py finalize --workspace geo-benchmarks/geo-v1
```

Development diagnostics may be inspected without making a release claim:

```powershell
python scripts/geo_benchmark.py evaluate --workspace geo-benchmarks/geo-v1 --split development --informational
```

Do not inspect holdout labels or holdout error cases while tuning resolver rules.

## 5. Evaluate and gate the resolver

```powershell
python scripts/geo_benchmark.py evaluate `
  --workspace geo-benchmarks/geo-v1 `
  --split holdout `
  --bootstrap 1000 `
  --seed 20261108
```

The command exits non-zero when a predeclared release gate fails. Outputs include:

- unique profile-evidence and owner-weighted estimates;
- production-threshold and all-assignment views;
- precision, wrong-assignment rate, resolvable recall, coverage, and abstention quality;
- conservative 95% intervals combining stratified bootstrap and effective-sample Wilson bounds;
- per-confidence, script, and evidence-shape results;
- error-case JSONL/CSV;
- publication-ready Markdown;
- a SHA-256 audit index over every input and output artifact.

The non-Latin gate uses a lower confidence-bound threshold calibrated to the finite non-Latin evidence present in the current population, not a weaker point-accuracy target. Sparse strata are censused, and even one observed error can fail that gate.

Verify hashes at any time:

```powershell
python scripts/geo_benchmark.py verify --workspace geo-benchmarks/geo-v1
```

## Privacy and publication

Benchmark workspaces are git-ignored operator data. They contain public self-reported location strings, which can still include addresses or other personal information. The sampler removes login, GitHub id, repository identity, full website hostname, and URL path; only the final website TLD is retained. Keep raw annotation artifacts access-controlled. Publish aggregate metrics and hashes by default; publish row-level evidence only after the study's ethics/privacy review and retention policy permit it.

## Research reporting language

Report this field as **inferred country from self-reported GitHub owner profile evidence**. Never describe it as nationality, citizenship, legal residence, contributor location, or repository country. Publish the resolver version, GeoNames version, annotation-policy hash, sample-frame hash, weighting method, confidence intervals, missingness, and every failed gate.
