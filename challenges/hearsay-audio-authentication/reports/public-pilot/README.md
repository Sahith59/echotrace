# MLAAD-tiny diagnostic pilot

24 files, 12 genuine and 12 synthetic, sampled before inference using seed42. Synthetic selection: three English clips each from Chatterbox, Edge-TTS, FishTTS and MeloTTS. Genuine selection: 12 English clips sampled from the pinned original/en listing. See provenance.json for exact revision, URLs, byte counts, hashes and selection. Total downloaded audio: 5,274,736 bytes. Audio and source licenses are in ignored backend/artifacts/public-pilot; this report redistributes no audio. Dataset: https://huggingface.co/datasets/mueller91/MLAAD-tiny (synthetic CC BY-NC4.0, genuine M-AILABS terms).

Unchanged local AASIST-L CPU baseline. No model training, threshold tuning, calibration or fusion. Fixed threshold0.5 chosen before this pilot. All24 files scored successfully.

| Outcome | Result |
|---|---:|
| Correct genuine | 9 /12 |
| Genuine incorrectly flagged | 3 /12 |
| Synthetic detected | 6 /12 |
| Synthetic missed | 6 /12 |
| ROC AUC | 0.7431 |
| Synthetic recall at0.5 | 0.50 |

Small selected diagnostic sample, not a representative benchmark, not a speaker/source-independent test, and not sponsor performance. Group metadata was not supplied to this pilot manifest; no split or fitting was performed. Potential model-training overlap is not independently excluded. Do not use this set both for future tuning and for reporting an independent final evaluation. No performance improvement is claimed.

Next: examine errors by generator and recording quality, choose a separately sourced/partitioned development evaluation, compare a second model, and only then schedule justified training. Record future evaluations separately; preserve this untouched baseline.

Commands used from backend:

```sh
uv run echotrace batch artifacts/public-pilot/manifest.csv --root artifacts/public-pilot --output artifacts/public-pilot/scores.csv
uv run echotrace evaluate artifacts/public-pilot/manifest.csv artifacts/public-pilot/scores.csv --root artifacts/public-pilot --output artifacts/public-pilot/metrics.json
```

File-level results and public download manifest are retained alongside this report. File identifiers and corpus-derived labels are not predictive features. UI scores remain uncalibrated.
