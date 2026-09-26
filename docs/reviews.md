# Independent planning reviews

Date: 2026-09-25. Three agents were requested with model `gpt-5.6-sol` for read-only planning review: detection/evaluation, product/demo, and architecture/delivery. These are design reviews, not implementation tests or evidence of model performance.

## Detection and evaluation

Recommendations: obtain metric/schema/label taxonomy; prioritize a reproducible CSV baseline; compare pretrained anti-spoofing against frozen speech embeddings plus a small head and a lightweight acoustic-feature classifier; prevent recording-family leakage; calibrate and fuse without evaluation contamination; inspect codec/generator shortcuts; preserve raw scores and expose failures.

Integrated: model choice stays provisional; alternative supervised routes and naive baseline added; grouped splits and optional generator diagnostics documented; final score semantics and CSV preflight explicit; no LLM scoring; best single model remains a valid outcome.

Adjusted: the reviewer suggested universal mono 16 kHz and a short-file cutoff. The plan instead requires each model's actual preprocessing contract and a validated minimum duration. Different models may require different inputs; no unsupported global cutoff is assumed. A heuristic fallback may support diagnostics but is not represented as a completed learned detector.

## Product and demonstration

Recommendations: intake -> truthful processing stages -> investigation -> stress comparison -> batch export; synchronized player and evidence timeline; keyboard and non-color alternatives; clear uncertainty; labeled cached examples; keep mandatory CSV prominent and defer live calls, chat, accounts and elaborate reports.

Integrated: four focused views, polished restrained visual direction, actual analysis stage reporting, evidence-versus-interpretation separation, accessibility checks and a short proposed demo storyboard.

Adjusted: a proposed mandatory trio of detectors would increase scope without proving improvement. The plan requires multiple actual analysis techniques and gates additional learned detectors on validation. Suggested uncertainty bands and disagreement-based widening are not adopted without statistical validation. Hypothesis classes and sample CSV headers remain uncommitted until the sponsor supplies them. File hashes and technical provenance stay in expandable details instead of dominating the initial experience.

## Architecture and delivery

Recommendations: one Python scoring pipeline for API/CLI; bounded FFmpeg decoding; SQLite-backed jobs and restart recovery; immutable manifests and versioned artifacts; strict schema adapter; focused API/CLI parity and malformed-input tests; offline CPU/batch fallback; no unnecessary distributed infrastructure.

Integrated: shared package, durable single worker, explicit contracts, typed failures, full test-set coverage, restart tests, local-first operation and offline CLI fallback. Final schema and infrastructure spend remain unresolved rather than guessed.

Adjusted: the review's proposed block on nearly all implementation until sponsor artifacts arrive is too broad. Missing artifacts block sponsor-specific evaluation/submission but do not block authorized decoding, checkpoint smoke tests, contract design or clearly labeled UI fixtures. Per-analyzer reliability numbers are omitted unless measured and defined. No default rounding to integers.

## Resolved plan priorities

1. Verify rules, data, compute and preprocessing feasibility.
2. Establish real detection plus complementary analysis and a reproducible batch path.
3. Connect a complete usable product flow to the same pipeline.
4. Promote model/fusion/calibration changes through measured comparisons.
5. Add a genuine stress-test demo if time permits.
6. Freeze, verify final CSV and rehearse with documented limitations.

All three reviews leave metric, dataset, schema, compute, deadline and sponsor-wide rules unresolved. No review guarantees winning or benchmark performance.
