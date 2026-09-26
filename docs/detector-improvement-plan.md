# Detector recovery and five-hour adaptation plan

Date: 2026-09-25. This supersedes the prior decision to defer all training. The user authorized five hours of GPU work and prioritizes detector usefulness. Cluster staging and all-file auditing completed; training/evaluation job 4503646 is running and has written a checkpoint. See the [active run ledger](cluster-run-2026-09-25.md) before submitting anything else.

## What is actually implemented

AASIST-L is the only learned detector in the web pipeline. FFmpeg decodes mono 16 kHz waveforms. Each 64,600-sample window produces spoof class-0 softmax; the file score is an unweighted mean, displayed as a rounded percentage. Short inputs repeat-pad; the final long-input window may overlap its predecessor. These choices require parity/aggregation validation.

AI interpretation now has an on-demand Grok integration; live output review still requires the user's API key. The separate measurement limitations use deterministic rules. RMS, clipping, quiet frames and spectral measurements are computed observations; they do not contribute independent learned votes to the synthesis score. Very quiet input gets no score. Manipulation type is undetermined. Speaker verification, truth determination and calibration remain unimplemented.

Phase 3A software includes the bounded runner, three-way preparation, full CPU audio audit, whole-file checkpoint evaluation and acceptance reporting with attack/codec slices. Local CPU and actual A100 numerical smoke tests verify execution only. No new speech-trained detector has been promoted. All 14,000 selected recordings passed auditing; adaptation is running. Final independent evaluation remains pending. See [checkpoint evaluation](checkpoint-evaluation.md) and [cluster handoff](cluster-handoff.md).

## Evidence and hypotheses

Saved baseline: 24 selected recordings (12 genuine/12 synthetic), threshold0.5, TP6/FN6/FP3/TN9; accuracy15/24 (62.5%), synthetic recall50%, genuine false-positive rate25%, AUROC0.7431. Synthetic scores range3.906%–99.752%; 2/12 are below10%, not all. Genuine scores range0.445%–90.573%. Known Chatterbox jane_eyre_21_f000371 scores9.21%; FishTTS skyisland_15_baum_64kb scores3.91%. Separate known macOS TTS fixture also scores about3%. Full AASIST comparison caught4/12 synthetic and falsely flagged0/12 genuine; it is not an established replacement.

These are diagnostic results only. Poor transfer to newer generators/recording conditions is a plausible explanation: upstream AASIST uses ASVspoof2019 LA. Exact causes remain unproven; inspect preprocessing, window aggregation, padding, raw logits and input-specific failure slices before blaming one factor. Upstream label code confirms spoof=0, bonafide=1; no evidence of reversed polarity. Softmax is not a calibrated real-world probability. Lowering a threshold cannot repair ranking quality, and calibration cannot create missing discrimination.

## Ordered phases

### Phase 1 continuation — detector audit (implemented)

- Add upstream-reference preprocessing/scoring parity fixtures, covering short and long recordings and score polarity. Compare reference first-window evaluation with current full-file aggregation; change policy only on separate development evidence.
- Produce all-file per-generator/codec/duration error report with raw scores, not a curated success demo. Keep failures as regressions without forcing correct labels into model output.
- Acceptance: reproducible baseline, verified decoder/adapter/aggregation behavior and a documented explanation of any mismatch. An audit may confirm a weak model rather than find a code defect.
- User check: compare a known label with the predicted score and see misses as misses.

### Phase 3A — data and experiment preparation (before GPU clock)

- Keep current24 as demonstration/regression material, excluded from fitting, calibration and independent acceptance claims.
- Development source: official ASVspoof5 train/dev. The first run stages only `flac_T_aa.tar` and `flac_D_aa.tar`, totaling 14,169,763,840 archive bytes, in verified personal cluster storage. This is a subset of the 57,561,937,920-byte train/dev release; do not claim full-corpus coverage. Audio staging completed; actual split counts and coverage are in the current plan and run ledger.
- Target a bounded10k–30k training subset, chosen by fixed rules across genuine/spoof, speakers and attack types; actual size is selected from audited availability and measured throughput, not promised in advance.
- Preserve official train/dev/eval boundaries. Group linked sources/speakers and duplicates. Partition development groups into checkpoint/threshold selection, optional calibration and a locked acceptance subset before fitting; ensure sufficient genuine/synthetic counts. Never tune on the locked subset or official evaluation labels.
- Implemented: reproducible PyTorch runner with shared decoding, explicit class-map conversion (manifest1=synthetic vs AASIST target0=spoof), seeded sampling, weighted loss, best checkpoint, wall-clock limit, memory controls and config/hash/split provenance. Resume and patience early stopping are not implemented. Checkpoint selection uses first-crop loss; a separate evaluator checks the intended whole-file serving policy. Leakage, class mapping, gradients and checkpoint reload have software tests. CUDA compatibility and generated-signal throughput passed on an A100; the real-data CPU audit subsequently decoded all 14,000 selected files in about 29 minutes.
- Primary bounded experiment: fine-tune existing AASIST-L checkpoint on new training data, with conservative learning rate and validation-selected checkpoint. This minimizes adapter uncertainty; improvement is a hypothesis, not a promised result.
- A pretrained wav2vec2 anti-spoofing model is the next architecture candidate if adaptation fails. Do not spend the same five-hour budget on an uncontrolled architecture sweep. Check checkpoint license, runtime and reproducibility first.
- Acceptance: data installed and audited, partitions frozen, baseline on exact evaluation files, training smoke test and throughput estimate. No GPU hours spent on downloading.

### Phase 3B — bounded five-hour cluster experiment

Active resource plan: one node, one A100, four CPUs, 32 GB host RAM, under account `trends517s113` on `qTRDGPUM`. VPN access, allocation and owned `/data/users3/sthummala2/echotrace` storage are verified. The completed smoke used an A100-SXM4-40GB. No multi-node jobs or automatic extra allocation. Do not use the old course account `fall24csc4760` or stage large data in the 100 GB home directory.

| Maximum budget | Work in the implemented job |
| --- | --- |
| CPU preparation, outside GPU budget | Install/audit audio and dependencies, freeze subset sizes |
| 5 minutes reserved | GPU compatibility/numerical smoke; completed in 13 seconds |
| 3 hours | One adaptation run with periodic validation and best-checkpoint selection |
| 4 × 20 minutes | Whole-file baseline/candidate scoring on selection and locked acceptance |
| Remaining 35 minutes | Preflight hashing, setup, reporting and shutdown overhead in the 4h55 main job |

Times are caps, not completion guarantees. The main job's Slurm limit is 4h55, automatic requeue is disabled, and the earlier smoke's five-minute reservation keeps combined GPU limits within five hours. Slow hashing or decoding can exhaust the allocation. Do not drop difficult acceptance examples after seeing results. Calibration and architecture sweeps are outside this first bounded job. Queue time and CPU preparation time are additional elapsed time.

### Phase 3C — promotion gate

Provisional internal gate (not sponsor criteria): choose threshold on selection data to target at most5% genuine false-positive rate; lock it before acceptance scoring. On locked acceptance data, require synthetic recall at least80%, genuine false-positive rate at most5%, and at least10 percentage-point recall improvement over baseline at its independently selected operating point. Report confidence intervals, per-attack/codec counts and failures; insufficient counts or material slice regressions block promotion. These are goals and may fail, not predicted outcomes.

Implemented report: at least100 examples per class in both selection and acceptance, complete scores, no cross-split content/ID/group/speaker/source links, consistent checkpoint/configuration, the above recall/FPR goals and no AUROC regression. Wilson95% intervals accompany recall/FPR, but the gates use point estimates; passing is only `eligible_for_review`, never automatic promotion. Per-attack/codec descriptive breakdowns are now implemented at those locked thresholds; single-class ranking metrics are null. Reviewing slice regressions, EER, serving latency/memory and human review remain additional work. A tiny successful smoke test cannot pass the sample-count gate.

Also compare AUROC, average precision and EER; do not confuse a threshold adjustment with better ranking. Measure latency/memory on intended serving hardware. Independent public acceptance cannot establish sponsor accuracy. Once sponsor data arrive, repeat sponsor-specific evaluation and apply the official metric/schema. If no candidate passes, report the experiment as unsuccessful and retain explicit experimental status; do not inflate scores.

### Phase 2 follow-through — make results understandable

After the experiment, expose the accepted model version, validation summary and reference-vs-predicted disagreement in the demo. Label measured audio properties and rule-based limitations by their source. A low uncalibrated score must not read as verified genuine. Grok wording must summarize recorded evidence without deciding authenticity, inventing causes or asserting speaker identity. Preserve null/failure states and a rollback checkpoint.

### Phases 4 and 5 — demonstration and delivery

Rehearse genuine, synthetic, failed-detection, noisy and compressed examples; publish honest validation evidence with the prototype. Complete mobile/restart/export QA and official CSV adaptation when schema arrives. Speaker comparison needs reference recordings and separate validation; factual claim review needs external evidence. Neither is a lie detector or a substitute for synthesis detection, and neither distracts from this experiment.

## Sources

- Local: reports/public-pilot/{scores.csv,metrics.json}, reports/candidate-pilot/metrics.json, backend/echotrace/{model.py,pipeline.py,audio.py}.
- Official AASIST repository: https://github.com/clovaai/aasist (ASVspoof2019 LA; reported training environment single V100, about16GB at batch24).
- Pinned class labels and reference padding: https://raw.githubusercontent.com/clovaai/aasist/a04c9863f63d44471dde8a6abcb3b082b07cd1d1/data_utils.py
- ASVspoof5 organizers: https://www.asvspoof.org/
- Alternative architecture authors: https://github.com/TakHemlata/SSL_Anti-spoofing

Independent GPT-6 Sol medium reviews agreed on scoring mechanics and the need to prepare data/training code before the five-hour run. No model code, score thresholds, or weights changed during this planning audit.

## TReNDs cluster addendum — supplied guide reviewed

Source: `/Users/sahithreddythummala/Downloads/Introduction to the TReNDs Cluster - Summer 2026.pdf`, 65 pages, text extracted with pypdf. This is documentation, not a live resource inventory.

- Pages4,28–29: Slurm; hybrid qTRDGPU and GPU-only qTRDGPUL/qTRDGPUM/qTRDGPUH. H/M have published per-user GPU limits8/16, but our plan requests only1.
- Pages32,37,39 show A100 and typed GRES syntax `gpu:A100:1`. Prefer one permitted A100 with4 CPUs and32GB host RAM initially; GPU memory is separate and must be measured. Use an authorized matching partition after checking current inventory; do not assume qTRDGPUM or the example account is granted.
- Pages12,22–26: keep environments, audio/checkpoints and results under the user's actual `/data/users#/<campusid>` location, not home. Check for an existing shared corpus before downloading duplicate data. New data location/project allocation must follow PI/site rules; public audio does not grant rights over existing lab data.
- Pages7,12,42: no computation on login; no large directory operations there. Prepare/smoke-test on permitted dev or scheduled resources. Do not leave idle GPU sessions.
- Pages38–39: minimum necessary resources, usually4–8 CPUs for GPU work. One node/one task/one GPU,4 CPUs,32GB RAM, five-hour limit is a proposed modest starting request; adjust only from measured needs and site policy.
- Pages46–49: submit batch job through sbatch, pre-create log directories; capture job ID and use squeue/sacct for tracking. Cancel only this project's job if needed, never all user jobs.
- Pages57–58 contain `#SGATCH --gres=gpu:1` typographical errors: do not copy them; the actual directive is `#SBATCH`. Page37 short node/task flags are inconsistent; use explicit long options `--nodes=1 --ntasks=1` in our eventual job script.
- Guide example account `trends53c17` is not proof of the user's allocation. Need the user's actual permitted Slurm account, personal data path, and access route. No credentials needed in project documentation.

Implemented local job template: `--nodes=1 --ntasks=1 --cpus-per-task=4 --gres=gpu:A100:1 --mem=32G --time=05:00:00`. Supply the verified partition and `--account=trends517s113` as documented in [cluster handoff](cluster-handoff.md). No arrays, exclusive-node reservation or multi-node sweep. The template has not been submitted.
