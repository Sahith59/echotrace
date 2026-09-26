# ECHOTRACE application walkthrough

ECHOTRACE is a **local workbench for reviewing a suspicious voice recording**. An analyst can obtain a first synthesis assessment, inspect its limits, add separate evidence, and hand a reproducible case to the next reviewer. The system does not prove who spoke or whether the words are true.

## Start and orient yourself

From the challenges/hearsay-audio-authentication directory, run **./scripts/dev.sh status**. If stopped, run **./scripts/dev.sh start**, then open **http://127.0.0.1:5173/**. The local API uses port 8000. The repository-root .env holds the optional GROQ_API_KEY; keep it private. Detection, playback, reviews and exports do not require Groq.

The left rail has **Investigation** for individual recordings, **Batch & export** for the queue, and **Recent recordings** for saved cases. A saved case can be reopened without running the detector again. Older AASIST cases are labeled separately from newer NII cases.

Start at the **human versus generated** panel on Investigation. The two Jane Eyre recordings speak the same passage: one is a human reading and one was produced by Chatterbox. Play both, then choose **Analyze both recordings**. The resulting two case scores appear in the same panel, with links to each full analysis. This is a listening and workflow demo. The speakers need not match, and the NII training data includes MLAAD, so this pair is not an independent accuracy test. The human reference is a separately pinned extra file; on a fresh install prepare it with `uv run python -m echotrace.setup_examples --confirm-source-review --include-paired-reference` from `backend/` after reviewing the source notices.

## 1. Add one recording

Choose **Add recording** or **Choose audio files**. Select a permitted WAV, MP3, M4A or another FFmpeg-decodable file. Multiple selections become separate jobs. Current NII-primary limits are **50 MiB and 30 seconds per file**. Corrupt, too-quiet or overlong input fails explicitly rather than receiving a fabricated score or being silently truncated.

For a quick tour, expand **Try a known recording** on the intake screen, preview one of the 24 labeled MLAAD examples, and choose **Analyze this sample**. They use the same upload and scoring path as a custom file. Their labels are reference information and are never model input. They are *interface demonstrations*, not independent NII accuracy evidence: the [NII model card](https://huggingface.co/nii-yamagishilab/wav2vec-small-anti-deepfake) lists MLAAD among its training sources.

Uploading performs **inference**, not training. The detector does not learn from web uploads. The original audio and result stay in the local workspace.

## 2. Review the recording

Open a finished case from Recent recordings or the queue. **Review recording** is the first of three steps.

- **Synthesis assessment:** the large 0–100 display is a synthetic-high model score. It is uncalibrated: 80% on this display is not a verified 80% probability. A low score is not proof of a real voice. New recordings use pinned NII whole-file scoring, which cannot locate an edit or name a generator.
- **Review context:** shows job status, exact model, processing time, decoded sample rate and channels. The short case ID and **JSON report** are at the top.
- **Audio timeline:** play the original, seek on the waveform, or select an interval row. With NII, the scored interval is the **entire file**, not a detected splice.
- **Forensic observations:** measured level, clipping, quiet frames and spectral properties describe recording quality. They do not cause or explain the neural score. The nearby information buttons explain each area.
- **AI interpretation:** when Groq is configured, choose **Generate interpretation**. It receives measured findings, not audio, filename or transcript. Its evidence references open the corresponding measurements. Check the prose: it cannot change the detector score.

## 3. Check reliability

Choose **Check reliability**. Read **Measurement limitations** and expand **Technical provenance** for the source hash and model version.

In **Compression and noise test**, choose **MP3 compression** or **Add noise**. This is a different question from the home-page human/generated listening comparison: it changes one recording to see whether the same model's assessment is fragile. The app preserves the original, creates a named derivative, runs the *same* model again, and shows both scores and their difference. You can play the derivative and open its own case. A stable score under one transformation does not establish authenticity.

Expand **How well has the detector worked on other recordings?** This is about the model on labeled public audio, *not a judgment on the current case*. The first card is the newer ArA-DF-2026 Arabic/channel stress check: it missed **38 of 98** eligible synthetic clips and falsely flagged **7 of 100** genuine clips at the unchanged threshold. Two selected clips exceeded the 30-second app limit. That **misses** the project's 80% recall / 5% false-positive goal. Open **See test numbers and method** for percentages and provenance. The favorable In-the-Wild replication below was previously evaluated by the model authors. Neither is the NSA sponsor's withheld evaluation. Historical adaptation experiments and their failed promotion decisions remain under **Earlier model experiments**.

## 4. Leave an analyst handoff

Choose **Case evidence**. In **Record the next step**, select **Needs review**, **Corroboration requested**, or **Review complete**, add your own notes, and choose **Save review**. Review complete means a person completed a review; it does **not** certify the recording as authentic. Notes and status are versioned separately from the detector output.

Optional independent evidence appears below:

- **Speaker reference:** with permission, choose a trusted reference recording, add a label, check consent and choose **Compare reference** if the local WavLM model is ready. Cosine similarity is uncalibrated and cannot prove identity; clones or replays may match. Reference audio is deleted after comparison.
- **Transcript:** choose **Create transcript** if the local speech model is ready. Listen to timestamped passages, correct errors and **Save correction**. Corrections create new versions and mark linked older claim reviews stale.
- **Check a factual claim:** enter a checkable statement, expand **Record an analyst review**, and save your assessment, reasoning and source URL. Automated Groq source search is currently disabled because URL-level source provenance is not validated. This is source review, not lie detection.

Use **Download case JSON** or **Printable report** under “Beyond the waveform” for a handoff that keeps synthesis, speaker similarity, words and factual claims separate. The top **JSON report** exports the synthesis-analysis result alone.

## 5. Review a collection and export

Open **Batch & export**. Search and filter the queue by analysis/review state or date. Failed and scoreless records remain visible but cannot be selected as scored predictions. Select completed rows from the **same model version**, then choose **Export selected CSV**. This analyst CSV includes file ID, filename, a **0–1 synthetic-high score**, review status, notes and version. The UI shows the score on a 0–100 scale. This six-column export is **not** the official NSA submission schema; the sponsor's test files, metric and exact CSV rules must be confirmed.

## Suggested seven-minute live demonstration

1. **Problem, 30 seconds:** “A convincing recorded voice can be synthesized. We need a reproducible way to triage it, inspect model limits, and leave evidence for the next reviewer.”
2. **Upload and assessment, 90 seconds:** show a saved known synthetic NII case (the Jane Eyre example currently displays an elevated score), then a saved known genuine NII case (the Wives and Daughters example currently displays a low score). Say these are *illustrations*, not an accuracy test.
3. **Hear and inspect, 60 seconds:** play and seek the original, show the whole-file interval and two measured acoustic observations. Point out that measurements and neural scoring are distinct.
4. **Stress the result, 60 seconds:** run or open a saved MP3 comparison, play the derivative and explain the score delta and its limits.
5. **Show honest validation, 60 seconds:** expand the ArA failed-goal card. Explain the missed synthetic clips and false alarms and why the team did not hide them or silently retune.
6. **Handoff, 90 seconds:** open a saved Groq brief and evidence reference if available, show an analyst note, then open the unified report and batch analyst CSV.

Keep a saved real case and its report for an offline fallback. Clearly identify a saved case as a prior run. The [phase checklist](../plan.md) tracks the remaining detector-quality and official sponsor-data gates.
