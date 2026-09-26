# What you can verify in the application

Open the local workbench at `http://127.0.0.1:4173` while its API and preview processes are running. Startup commands are in the [application README](../challenges/hearsay-audio-authentication/README.md).

## Phase 2 — Your investigation

1. Add a permitted recording from your computer, or use **Try a known recording**. It does not need to come from a dataset. An upload runs inference with saved weights; it does not train the model.
2. Wait for the saved result. Play the recording and choose a scored interval. You should hear the same original audio, with the playback position moving to that interval.
3. Read the synthesis assessment together with its uncalibrated label. A known synthetic example can be missed; a low score does not prove that it is genuine.
4. Make an MP3 or noisy comparison. You should get a separate result and playable derivative, while the original remains unchanged.
5. Open **Batch & export**, select completed scored recordings, and export CSV. Failed or scoreless records should be unavailable for numeric export.

An unfamiliar-file chooser could not be completed by our Chrome automation because the extension lacks file-URL permission. You can check that ordinary browser upload manually. The API's real decoding/inference and format/error limits are tested separately. Do not use private recordings merely to test the interface; a permitted public or self-created sample is sufficient.

## Evidence extensions

- **Speaker reference:** supply a permitted trusted voice reference and check the consent box. The result is cosine similarity, not an identity probability. The reference recording is deleted after processing; comparison metadata remains until you remove it.
- **Transcript:** create a transcript, listen to a timestamped passage, and correct any words. A correction creates a new version. **Review this passage** copies the words and their time span into claim review.
- **Claims:** enter one specific factual statement. An analyst review is explicitly labeled as yours. A supported or contradicted review needs a source URL. Subjective or private statements can remain uncheckable. Corrections mark reviews of older transcript wording stale.
- **AI:** save your xAI key in the local root `.env` as `XAI_API_KEY`, then use **Check configuration** for interpretation or reload the case for claim search. Never put the key in a recording, a prompt, a screenshot, source control or the browser code. Interpretation receives measurements only; claim search sends the selected claim after consent. Open the cited sources and check that they actually support the assessment.
- **Report:** open the printable case report or download case JSON. The synthesis score, voice comparison, transcript and claim evidence stay separate. No combined “authenticity” number is invented.

## Phase 3 — Model quality

Expand **Detector validation · measured performance**. Compare the fraction of synthetic recordings caught with the fraction of genuine recordings falsely flagged. A finished training job is not enough to install a candidate; its independent results and serving behavior must pass review. Public-data evaluation does not replace sponsor-data evaluation.

## Phase 4 — Demo

Follow the [demo guide](demo-guide.md). Include a genuine recording, a synthetic recording, a known miss, and a comparison. Local saved real reports are under ignored `artifacts/release-demo/`; identify them as prior results if used offline. A missing AI key must produce an unavailable state, not a simulated Grok answer.

## Phase 5 — Source handoff and competition

The source release includes reproducible commands, locked dependencies, tests and measured reports. The sponsor must still supply the official held-out files, schema, scoring rules and submission destination before the final competition CSV can be checked and submitted. Deployment and multi-user access are a later task.
