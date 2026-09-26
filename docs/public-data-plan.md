# Public-data pilot while HEARSAY sponsor data are absent

Checked 2026-09-25 against dataset creators' and challenge organizers' pages. Public data can expose pipeline failures and give a **public-corpus** baseline; it cannot establish performance on the unreleased HEARSAY distribution, satisfy its held-out CSV, or determine the official metric.

## Practical choice

Start with a small, fixed, balanced sample of genuine and synthetic clips from the authors' [MLAAD-tiny repository](https://huggingface.co/datasets/mueller91/MLAAD-tiny). Its `original/` and `fake/` folders put both labels in one source. Record the repository revision, file paths, labels, hashes, language, source speaker/book and TTS system if available. Download only the selected files first; keep audio in the ignored local data area and keep a manifest in the run record. Run the **unchanged AASIST-L baseline** and report counts, score distributions, AUC/EER or other suitable public-pilot metrics, false positives/negatives, and runtime before any tuning. Its low score on our known synthetic macOS TTS clip makes this measurement urgent. If metadata cannot identify related source recordings, speakers, or TTS systems, say so and avoid claiming an independent grouped test. Do not fit calibration or choose a threshold on the same clips used to report evaluation.

The [authors describe MLAAD-tiny](https://deepfake-demo.aisec.fraunhofer.de/mlaad_tiny) as a prototype/debug subset, with roughly 6,000 M-AILABS genuine clips and 6,400 generated clips from 64 TTS systems, around 4.2 GB by their component estimates. The [current Hugging Face card](https://huggingface.co/datasets/mueller91/MLAAD-tiny) instead displays 15,290 rows and 3.54 GB. Verify the actual revision, file count, metadata and download size before budgeting or quoting a result. Genuine audio retains its [M-AILABS source terms](https://huggingface.co/datasets/mueller91/MLAAD-tiny); synthetic audio is CC BY-NC 4.0. Check the files' licenses and demo/redistribution use before publishing any clips or derivatives. The small pilot is for development, not a sponsor-equivalent benchmark.

| Dataset | What the primary source provides | Practical tradeoff |
| --- | --- | --- |
| [MLAAD-tiny](https://huggingface.co/datasets/mueller91/MLAAD-tiny) | Genuine and TTS audio in separate folders; authors describe English genuine audio and English/German synthetic audio; CC BY-NC 4.0 applies to the synthetic side, with M-AILABS terms for genuine. | Best first local pilot by size and paired labels. Language/source artifacts and incomplete grouping metadata may dominate results; check licenses and revision. |
| [ASVspoof 2019 LA](https://datashare.ed.ac.uk/items/31074a11-b6f6-4e92-a4ad-07093f8c0c45) | Official 7.12 GB LA archive, protocols and train/development/evaluation partitions; speakers are disjoint across partitions. The publisher supplies [ODC Attribution license text](https://datashare.ed.ac.uk/bitstreams/60c7de6d-37d3-45c1-b52e-9f18b0338e47/download). | Strong reproducible follow-up. AASIST-L comes from the ASVspoof line, so inspect checkpoint training provenance and do **not** present training/development scores as independent generalization. Audio-content rights may need separate checks. |
| [ASVspoof 2021 DF](https://zenodo.org/records/4835108) | Official deepfake evaluation audio with genuine/spoof labels in separately released [keys and metadata](https://www.asvspoof.org/index2021.html); four archives total 34.5 GB. Organizers describe ODC Attribution terms. | Useful later external evaluation with compression effects, but too large for the first local pilot and no new training/development set accompanies the 2021 release. |
| [WaveFake](https://zenodo.org/records/5642694) | 104,885 generated WAV clips in one 28.9 GB archive, CC BY-SA 4.0; the authors explicitly **do not redistribute the genuine reference corpora**. | More setup and storage: obtain genuine LJSpeech/JSUT separately, honor their terms, and control source/recording overlap. Defer until a specific cross-generator question warrants it. |
| [Full MLAAD](https://deepfake-demo.aisec.fraunhofer.de/mlaad) | Large multi-language synthetic corpus intended for use with genuine M-AILABS audio; CC BY-NC 4.0. | Defer. It adds a separate genuine corpus and much more storage; version and composition should be pinned before comparison. |

## Evaluation sequence

1. Check terms and pin a public dataset revision. Pick a small balanced manifest before looking at model scores, with file IDs, paths, binary labels (`0` genuine, `1` synthetic), source and group fields where known. Hash files and keep original labels; the app's filename is never an input feature.
2. Audit decodability, duration, classes, duplicate hashes, and related speakers/source recordings. Exclude or group derivatives and near duplicates across splits. Report missing metadata instead of assuming independence.
3. Score with the current pipeline unchanged. Keep raw AASIST logits and verify synthetic-high polarity; the UI's 0–100 display is an **uncalibrated model score**. Record the exact model/configuration and manifest, processed/failure counts, hardware and runtime.
4. Inspect failure categories before deciding whether a second model, adaptation, or cluster time is justified. Reserve a disjoint public test set for any public-data tuning; freeze choices before evaluating it. Avoid treating repeated subsets or compressed copies as independent examples.
5. When sponsor data arrives, repeat the audit with the sponsor's labels and grouping, compare the untouched baseline and candidates under its metric, then confirm its CSV schema and held-out test policy. Public-pilot metrics remain labeled by corpus.

## Still unknown

The sponsor dataset location, size, labels, source/generator metadata, license, official metric, CSV columns/scale/order, test policy, deadline, and permission to combine external data remain unknown. For MLAAD-tiny, reconcile the current row/size discrepancy and inspect per-file rights and grouping metadata. For ASVspoof 2019 LA, verify the AASIST-L checkpoint's training split before calling any partition an independent evaluation. No public dataset has been downloaded or scored for this plan.

## Pilot executed after this research

A24-file English diagnostic sample was downloaded and scored without tuning. Exact selection, revision, hashes, scores and limitations are in `challenges/hearsay-audio-authentication/reports/public-pilot/`. This supersedes the earlier no-download status above. No full corpus or cluster allocation was used.
