# ECHOTRACE product validation

Date: 2026-09-25. This is an independent product review of `plan.md`, `claude.md`, and the local NSA Challenge 1 brief. It is a design recommendation, not user research or evidence of detector performance.

## Verdict

ECHOTRACE is a compelling presentation of the HEARSAY submission **if it is framed as recorded-audio triage for a forensic analyst**. The challenge asks for an audio-file input, automatic orchestration of multiple forensic techniques, a 0–100 synthesis-likelihood output, and a CSV of held-out test predictions. An analyst workbench makes all four visible in one coherent workflow. A waveform, interval list, quality observations, and method-level results can help an analyst decide what to review next, while the batch screen demonstrates the evaluated deliverable.

The concept becomes less credible if it claims to authenticate a recording, detect a scammer in a live call, or explain the exact source of a synthetic voice. The brief does not require any of those tasks, and a binary synthetic-audio detector cannot establish them. The product should never turn a high model score into a verdict about a person's identity, intent, or the recording's provenance.

The main product risk is an attractive analysis page built around weak or misleading model output. The scoring baseline, score polarity, format handling, and CSV coverage therefore matter more than additional visual effects. The current phase order mostly reflects that priority. I would make the public-facing story narrower than “audio authentication”: **“Review a recorded clip for evidence of synthetic speech, then export reproducible predictions for a batch.”**

## Which product to build

| Product frame | Real target user and moment | Challenge fit | MVP judgment |
| --- | --- | --- | --- |
| General consumer scam app | A person deciding whether a caller is fraudulent | Weak. A scam may use genuine speech; a synthetic recording may be benign. The challenge provides audio authenticity labels, not scam outcomes or advice labels. | Do not build. It invites false reassurance and unsupported safety claims. |
| Live call detector | A person or operator monitoring an active phone call | Partial at best. Streaming capture, latency, phone integration, consent, and noisy call conditions are distinct requirements. The brief explicitly evaluates files and a CSV. | Defer. A prerecorded call can be analyzed as a file, but the UI should not imply live protection. |
| Analyst uploaded-audio triage | A digital-media forensic analyst, fraud-investigation analyst, or incident responder with a suspicious recording already in hand | Strong. Upload and batch workflows map directly to the file task, multiple techniques, likelihood score, and CSV submission. | Build this. Choose one primary persona: a forensic analyst reviewing a queue of received recordings. |

The analyst's concrete job is to process a clip, identify whether its synthetic-speech score merits closer review, note limitations such as silence or severe compression, and preserve a repeatable result. This is a defensible job even when the detector cannot decide the case alone. A manager, consumer, or hotline operator may view a report later, but they should not drive the MVP interface.

## Tight MVP experience

1. **Intake.** A file picker/drop zone states supported formats and size/duration limits. A separate “use example” action identifies sample provenance and any precomputed result. Show filename, duration, codec, and analysis status only after actually reading them. Reject corrupt, unsupported, oversized, or non-analyzable input with a clear reason.
2. **Analysis result.** The first screen after completion shows the 0–100 score with its honest label (`calibrated estimate` only if calibration was fitted and evaluated; otherwise `uncalibrated model score`), a short limitations line, and an audio player. Below it, provide a waveform and a text list of scored time windows when genuine window inference exists. The list seeks playback; it does not call windows verified edit boundaries. A compact evidence panel shows each technique's actual output and quality findings, with model/configuration details expandable. If window inference is not implemented or validated, omit the suspicious-interval layer and show only file-level analysis.
3. **Batch and export.** A manifest or multi-file selection starts the same pipeline used for single files. The screen shows total, completed, failed, and pending files; a table exposes each file's score/status and failure reason. Export preflight checks official columns, IDs, score scale, duplicates, missing rows, and finite values against the sponsor template. A CSV download is enabled only when the batch satisfies the actual submission contract or a documented sponsor-approved exception.

The comparison screen proposed in the plan is a good demo extension **after** these screens work. It should show an explicitly named transformation (for example, a specified codec or noise level), playback of both files, two real scores, and their difference. It must not describe score stability as proof of robustness or authenticity. A static “demo result” can help presentation only if clearly labeled and never routed into submission output.

The visual polish should come from a fast, legible path through those three screens: clear hierarchy, responsive player, aligned timeline and evidence, readable empty/error/loading states, keyboard operation, and restrained motion. Elaborate investigative graphics add little if they cannot be traced to measured data.

## Claims the product can support

| Safe product language | Condition or limit |
| --- | --- |
| “Synthetic-speech score: 78/100” | The scale and label polarity are verified. Present this as a model score unless calibration is actually evaluated. |
| “These 2-second windows received higher model scores” | Window inference ran, timestamps map correctly to the original audio, and the resolution is stated. |
| “Clipping was observed” / “The file contains a long silent span” | The measurement ran and its threshold or definition is available in details. These are observations, not proof of synthesis. |
| “Two analysis methods returned these results” | Both techniques actually execute on the file. A second chart of the same detector's output is not a second technique. |
| “This run used model version X and configuration Y” | Versions and artifacts are recorded with the result. |

Avoid “verified real,” “deepfake confirmed,” “voice cloned,” “speaker identified,” “scam detected,” “95% confidence,” “tampering at 01:23,” and manipulation-type labels unless separate data and evaluation support each claim. A low synthesis score is inconclusive evidence about authenticity. Method agreement is not a statistical confidence interval. If calibration cannot be supported by the supplied data, the challenge's required 0–100 output can still be provided as a clearly labeled model-derived score; the interface should not imply that 78 means a validated 78% probability.

## First acceptance bar

The first reviewable vertical slice should be judged against concrete evidence, not the appearance of the UI:

- A real WAV, MP3, and M4A fixture each decodes and produces a score from a working learned detector; the same job automatically records at least one distinct signal or quality analysis technique. A known-label check verifies score polarity.
- An unfamiliar supported clip completes intake → actual analysis → result → playback, with status reflecting real work and no fabricated progress. Silent, corrupt, and unsupported clips produce explicit failures or limited-result states with no invented default score.
- The result identifies its score semantics, model/configuration, input metadata, technique outputs, and limitations. Any interval UI is driven by real window results with verified timestamps.
- The batch command and web path use one scoring implementation. Once the sponsor template and test files exist, the batch produces a CSV with every expected ID exactly once, correct columns and score scale, and no missing or non-finite predictions; failures must be resolved before export.
- A held-out validation report documents the split, sample counts, metric, runtime, score polarity, and known data limitations. The report supports only the measured claims shown in the demo. No numerical accuracy target should be invented before the dataset and official metric arrive.

This bar fits the challenge more tightly than a live-call demo or a broad consumer promise. The official dataset, CSV schema, metric, and deadline are still unknown, so the final two acceptance items cannot be completed until those artifacts arrive. Work on decoding, baseline feasibility, and the single-file path can begin once the root plan authorizes implementation.
