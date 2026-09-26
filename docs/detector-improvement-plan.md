# Detector recovery and five-hour adaptation plan

Date: 2026-09-25. This supersedes the prior decision to defer all training. The user is willing to spend five hours of cluster training and prioritizes detector usefulness over further UI polish. No cluster job or large download has been launched.

## What is actually implemented

AASIST-L is the only learned detector in the web pipeline. FFmpeg decodes mono 16 kHz waveforms. Each 64,600-sample window produces spoof class-0 softmax; the file score is an unweighted mean, displayed as a rounded percentage. Short inputs repeat-pad; the final long-input window may overlap its predecessor. These choices require parity/aggregation validation.

Interpretation notes are deterministic templates plus conditional audio-quality warnings, not LLM output. RMS, clipping, quiet frames and spectral measurements are computed observations; they do not contribute independent learned votes to the synthesis score. Very quiet input gets no score. Manipulation type is undetermined. No speaker verification, truth determination, calibration, training runner, or trained project-specific checkpoint is implemented.

## Evidence and hypotheses

Saved baseline: 24 selected recordings (12 genuine/12 synthetic), threshold0.5, TP6/FN6/FP3/TN9; accuracy15/24 (62.5%), synthetic recall50%, genuine false-positive rate25%, AUROC0.7431. Synthetic scores range3.906%–99.752%; 2/12 are below10%, not all. Genuine scores range0.445%–90.573%. Known Chatterbox jane_eyre_21_f000371 scores9.21%; FishTTS skyisland_15_baum_64kb scores3.91%. Separate known macOS TTS fixture also scores about3%. Full AASIST comparison caught4/12 synthetic and falsely flagged0/12 genuine; it is not an established replacement.

These are diagnostic results only. Poor transfer to newer generators/recording conditions is a plausible explanation: upstream AASIST uses ASVspoof2019 LA. Exact causes remain unproven; inspect preprocessing, window aggregation, padding, raw logits and input-specific failure slices before blaming one factor. Upstream label code confirms spoof=0, bonafide=1; no evidence of reversed polarity. Softmax is not a calibrated real-world probability. Lowering a threshold cannot repair ranking quality, and calibration cannot create missing discrimination.

## Ordered phases

### Phase 1 continuation — detector audit (next implementation)

- Add upstream-reference preprocessing/scoring parity fixtures, covering short and long recordings and score polarity. Compare reference first-window evaluation with current full-file aggregation; change policy only on separate development evidence.
- Produce all-file per-generator/codec/duration error report with raw scores, not a curated success demo. Keep failures as regressions without forcing correct labels into model output.
- Acceptance: reproducible baseline, verified decoder/adapter/aggregation behavior and a documented explanation of any mismatch. An audit may confirm a weak model rather than find a code defect.
- User check: compare a known label with the predicted score and see misses as misses.

### Phase 3A — data and experiment preparation (before GPU clock)

- Keep current24 as demonstration/regression material, excluded from fitting, calibration and independent acceptance claims.
- Proposed development source: ASVspoof5 official train/dev, whose protocol importer is already built. Audio is not installed. Train/dev archives total57,561,937,920 bytes before extraction. Confirm cluster storage and download route before acquisition; a smaller verified source/subset is acceptable if corpus logistics do not fit.
- Target a bounded10k–30k training subset, chosen by fixed rules across genuine/spoof, speakers and attack types; actual size is selected from audited availability and measured throughput, not promised in advance.
- Preserve official train/dev/eval boundaries. Group linked sources/speakers and duplicates. Partition development groups into checkpoint/threshold selection, optional calibration and a locked acceptance subset before fitting; ensure sufficient genuine/synthetic counts. Never tune on the locked subset or official evaluation labels.
- Build a reproducible PyTorch training runner with shared preprocessing, explicit class-map conversion (manifest1=synthetic vs AASIST target0=spoof), seeded sampling, weighted loss or balanced batches, checkpoint/resume, wall-clock limit, memory controls and config/hash provenance. Test leakage rejection, class mapping, gradients, checkpoint reload and train/serve parity before a real run.
- Primary bounded experiment: fine-tune existing AASIST-L checkpoint on new training data, with conservative learning rate and validation-selected checkpoint. This minimizes adapter uncertainty; improvement is a hypothesis, not a promised result.
- A pretrained wav2vec2 anti-spoofing model is the next architecture candidate if adaptation fails. Do not spend the same five-hour budget on an uncontrolled architecture sweep. Check checkpoint license, runtime and reproducibility first.
- Acceptance: data installed and audited, partitions frozen, baseline on exact evaluation files, training smoke test and throughput estimate. No GPU hours spent on downloading.

### Phase 3B — bounded five-hour cluster experiment

Requested resource plan: one node, one GPU, five-hour wall-clock maximum (five GPU-hours), subject to university policy. Prefer one A10040GB if offered; otherwise use an available permitted GPU with at least16GB and tune batch size to measured memory. No multi-node jobs or automatic extra allocation. The supplied TReNDs Summer2026 guide confirms Slurm and A100/V100/H100/L40/RTX/A40 resources across its GPU partitions. Actual user allocation, authorized partition, current availability/VRAM and personal storage path remain to be checked. See the cluster addendum below.

| Elapsed budget | Work |
| --- | --- |
| 0:00–0:15 | GPU/environment verification, finite loss/gradient check, throughput and memory measurement |
| 0:15–0:45 | Fixed baseline/selection evaluation; cap subset beforehand if measured throughput requires it |
| 0:45–3:45 | One adaptation run with periodic validation, checkpointing and early stopping |
| 3:45–4:30 | Score frozen candidate and baseline on locked acceptance subset; slice/error analysis |
| 4:30–5:00 | Optional separate-set calibration only if supported; save artifacts, parity check and shutdown |

Times are caps, not completion guarantees. Reserve evaluation time; shorten training if needed. Do not extend the job or discard difficult examples to meet a target. Pre-stage dependencies/audio/checkpoints outside the GPU allocation. Queue time and preparation time are additional elapsed time, not promised within five hours.

### Phase 3C — promotion gate

Provisional internal gate (not sponsor criteria): choose threshold on selection data to target at most5% genuine false-positive rate; lock it before acceptance scoring. On locked acceptance data, require synthetic recall at least80%, genuine false-positive rate at most5%, and at least10 percentage-point recall improvement over baseline at its independently selected operating point. Report confidence intervals, per-attack/codec counts and failures; insufficient counts or material slice regressions block promotion. These are goals and may fail, not predicted outcomes.

Also compare AUROC, average precision and EER; do not confuse a threshold adjustment with better ranking. Measure latency/memory on intended serving hardware. Independent public acceptance cannot establish sponsor accuracy. Once sponsor data arrive, repeat sponsor-specific evaluation and apply the official metric/schema. If no candidate passes, report the experiment as unsuccessful and retain explicit experimental status; do not inflate scores.

### Phase 2 follow-through — make results understandable

After audit, expose model version, validation summary and reference-vs-predicted disagreement in the demo. Label measured audio properties and rule-based limitations by their source. A low uncalibrated score must not read as verified genuine. Optional LLM report wording, if ever added, must summarize recorded evidence without deciding authenticity, inventing causes or asserting speaker identity. Preserve null/failure states and a rollback checkpoint.

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

Proposed resource specification (not a runnable/submitted training script): `--nodes=1 --ntasks=1 --cpus-per-task=4 --gres=gpu:A100:1 --mem=32G --time=05:00:00`, with verified account/partition supplied later. No arrays, exclusive-node reservation or multi-node sweep. Build/test the runner first.
