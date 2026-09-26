# ECHOTRACE

A local audio investigation workbench for **HackGT13 · NSA Challenge 1: HEARSAY**.

Upload a suspicious recording, inspect a real learned synthesis score, listen to passages, compare a trusted voice, transcribe speech, review factual claims against sources, and export a reproducible case report.

The app separates three questions: **Does the recording resemble synthesized speech? Does it resemble a reference voice? What independent evidence supports the words spoken?** None is a proof of identity or truth. Scores are uncalibrated and known detector failures are disclosed.

## Start here

- [Run the application](challenges/hearsay-audio-authentication/README.md)
- [Phase checklist and remaining external gates](plan.md)
- [Feature inventory](docs/product-capabilities.md)
- [Demo walkthrough](docs/demo-guide.md)
- [What you can verify, phase by phase](docs/user-verification.md)
- [Verification evidence](docs/release-verification.md)
- [Source and model attribution](THIRD_PARTY_NOTICES.md)

## Architecture

React + TypeScript + Vite provide the graphite workbench. FastAPI and SQLite manage local uploads and durable analyses. FFmpeg decodes supported media; PyTorch runs the pinned speech detector; WavLM compares consented voice references; faster-whisper transcribes locally. Optional xAI integrations explain measurements or search sources for a selected claim, with separate consent and provenance.

Weights, datasets, recordings, workspaces, credentials and build outputs are intentionally excluded from this repository. Setup commands obtain pinned models. Keep the service on loopback until deployment authentication and operational controls are designed.

## Current evidence

Real GPU training and independent public-data evaluation have run. All three candidates failed at least one predeclared promotion goal. The final adapted native model caught 87.4% of synthetic clips but falsely flagged 24.4% of genuine clips on its balanced public holdout; compressed genuine speech remains a major weakness. The application shows actual measured results and retains the baseline unless a replacement passes review. Public-corpus results do not establish performance on the unavailable sponsor data.

The project provides a strict configurable CSV export pipeline. The final official CSV cannot be produced until the sponsor supplies its held-out files and submission contract. No competition result is guaranteed.
