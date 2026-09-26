# Independent-corpus stress check, 2026-09-26

The 24 MLAAD demonstration clips cannot validate the NII primary detector: [the checkpoint's training inventory](https://huggingface.co/nii-yamagishilab/wav2vec-small-anti-deepfake) explicitly includes MLAAD and ASVspoof5. The previously reported 2,000-file In-the-Wild result replicates a corpus the checkpoint authors already evaluated. To test a different source, we ran a bounded check on the [ArA-DF-2026 Arabic deepfake benchmark](https://huggingface.co/datasets/ArabicSpeech/ArA-DF-2026), published after the NII checkpoint. That corpus is not in the checkpoint's disclosed training inventory. Exact utterance/source overlap beyond the inventory has not been independently audited.

## Frozen protocol

- Source: `track-2_development_test`, shard `000000`. The benchmark describes Track 2 as a held-out acoustic/channel robustness condition. All distributed audio is 16 kHz mono FLAC; the metadata does not expose per-clip codec or channel labels. This is a *development-test* split of another challenge, not NSA's held-out data.
- Gold map: **0 synthetic**, **1 genuine**. ECHOTRACE scores higher for synthetic, so the polarity was inverted correctly for metrics. The decision threshold stayed at **0.5**; no threshold fitting or weight update used these files.
- Sample: SHA-256 order of `echotrace-ara-df-2026-09-26-v1|<id>`, first 100 in each class across one complete shard. The manifest SHA-256 is `41b9b04428ab59cdc7a773b0edaf72ec410181ed4f6261c824b9c94f5f663ebc` for both detectors. This is a deterministic, balanced convenience sample, not a random or representative estimate of the 647,844-row corpus.
- Audio archive SHA-256: `c266140c6ade2e7064233f11ef21c727f5f57317fe8e915ee3c096aa9d683840` (matched the upstream file OID). Gold metadata SHA-256: `1cd36378c09301e2ea7c4056e96cff1cf35da28203bb14572feb098e7121f90e`. Each selected FLAC was also checked against its gold metadata hash before scoring.
- NII used the same pinned whole-file inference routine as the app. AASIST-L used its official pinned checkpoint with full-coverage 64,600-sample windows and mean spoof softmax. Both were evaluated on **exactly the same selected IDs**; two synthetic clips (33.76s and 95.02s) exceeded NII's 30-second product scope and were retained as failures for both.

| Model | Scored | Synthetic recall | Genuine false-positive rate | AUROC | TP / FN / FP / TN |
| --- | ---: | ---: | ---: | ---: | --- |
| NII primary | 198/200 | **60/98 = 61.2%** | **7/100 = 7.0%** | 0.9018 | 60 / 38 / 7 / 93 |
| Historical AASIST-L | 198/200 | 77/98 = 78.6% | 93/100 = 93.0% | 0.3485 | 77 / 21 / 93 / 7 |

Approximate 95% Wilson intervals for NII: synthetic recall **51.3–70.3%** and genuine false-positive rate **3.4–13.7%**. This small selected cohort does not meet our predeclared 80% recall / ≤5% false-positive goals at 0.5. It is evidence of a real domain-shift weakness, even though NII has a much better tradeoff than historical AASIST on these same files. It does **not** justify a claim of reliable Arabic/channel robustness, overall detector accuracy, or sponsor performance. In particular, the higher AASIST recall comes with an unusable false-positive rate. No model or threshold changed in serving.

The NII scores were inspected before the paired AASIST run, so the comparison is exploratory. The single-shard, balanced selection and 30-second exclusions further limit generalization. To strengthen the detector, prepare a fresh selection set from permitted data, keep a separate untouched test with speaker/source/condition diversity, choose a threshold only on selection, and verify recall and false-positive costs on that untouched test. Official sponsor data and metric are still required before a competition claim.

## Reproduce

With the two upstream files downloaded to a local ignored `artifacts/` directory and pinned model weights installed, from `challenges/hearsay-audio-authentication/backend` run:

```bash
uv run python -m echotrace.ara_benchmark artifacts/external/ara-df-2026/track2-dev-shard0.tar artifacts/external/ara-df-2026/track2-dev-labels.csv.gz artifacts/external/ara-df-2026/run-100-each --per-class 100
uv run python -m echotrace.ara_benchmark artifacts/external/ara-df-2026/track2-dev-shard0.tar artifacts/external/ara-df-2026/track2-dev-labels.csv.gz artifacts/external/ara-df-2026/aasist-100-each --per-class 100 --detector aasist
```

The CLI deliberately returns nonzero when selected files fail product scope, while writing every row, `manifest.csv`, `scores.csv`, and `metrics.json` for audit. Those ignored local outputs are retained. The large downloaded TAR was removed after hash verification and evaluation to preserve disk space; it can be retrieved again from the cited dataset. Its license is marked `other` on the repository page, so audio is not redistributed here.
