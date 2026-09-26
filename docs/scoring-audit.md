# Detector scoring audit

The retained 24-file MLAAD-tiny pilot is a diagnostic set, not an independent benchmark or evidence of sponsor performance. This audit reuses its existing manifest and scores. It does not run inference, change weights, tune the threshold, or create data.

From `challenges/hearsay-audio-authentication/backend`:

```sh
uv run python -m echotrace.diagnostics ../reports/public-pilot/manifest.csv ../reports/public-pilot/scores.csv
uv run pytest -q tests/test_reference_parity.py
```

The command prints JSON. Pass `--output` with a new path to save it; the command refuses to replace an existing file, including either input CSV. The retained report is `challenges/hearsay-audio-authentication/reports/detector-audit/public-pilot-errors.json`. It includes all 24 manifest rows, scores, truth and predicted labels, file-level errors, generator counts, and overall metrics. At the fixed 0.5 threshold, the baseline has 9 true negatives, 3 false positives, 6 false negatives, and 6 true positives. ROC AUC is 0.7431 and synthetic recall is 0.5. Of three files per synthetic generator, the model misses two Chatterbox, one Edge-TTS, two FishTTS, and one MeloTTS. These counts are too small to rank generators reliably.

The parity tests pin the relevant input and output interpretation to [AASIST upstream revision `a04c9863`](https://github.com/clovaai/aasist/tree/a04c9863f63d44471dde8a6abcb3b082b07cd1d1). Its [evaluation data utility](https://github.com/clovaai/aasist/blob/a04c9863f63d44471dde8a6abcb3b082b07cd1d1/data_utils.py#L35-L42) repeats short waveforms and truncates them to 64,600 samples; the local pipeline uses the same repeat policy. For long waveforms, upstream evaluation takes the first 64,600 samples. The web pipeline scores full-length windows and an end-anchored overlapping tail, then averages interval spoof scores. These long-file results are intentionally different from the pinned upstream evaluation policy and should not be described as reference parity.

For 16 kHz PCM WAV, a test checks local FFmpeg float decoding against `soundfile` samples within one 16-bit quantization step. That check does not establish parity for compressed formats or resampled files. Local model scoring reads the softmax probability for output index 0, spoof; [upstream labels](https://github.com/clovaai/aasist/blob/a04c9863f63d44471dde8a6abcb3b082b07cd1d1/data_utils.py#L10-L32) use index 0 for spoof and 1 for bonafide. Upstream [evaluation output](https://github.com/clovaai/aasist/blob/a04c9863f63d44471dde8a6abcb3b082b07cd1d1/main.py#L264-L284) writes the raw index-1 bonafide logit, so its score scale and direction differ from this product's synthetic-high softmax.

No detector improvement is claimed: this work adds tests and an error report only. The same pilot should not be used to both select changes and claim an independent final result.
