# Full AASIST vs AASIST-L: unchanged 24-file diagnostic sample

Both official checkpoints are from the pinned upstream revision recorded in provenance.json. Same downloaded MLAAD-tiny files, 16kHz mono decoding, roughly four-second full-coverage windows, repeat padding for short files and mean window spoof-softmax aggregation. Fixed0.5 threshold, no training or calibration. No checkpoint promotion.

| Metric | AASIST-L baseline | Full AASIST candidate |
|---|---:|---:|
| Genuine correctly retained | 9/12 | 12/12 |
| Genuine falsely flagged | 3/12 | 0/12 |
| Synthetic detected | 6/12 | 4/12 |
| Synthetic missed | 6/12 | 8/12 |
| ROC AUC | 0.7431 | 0.7569 |
| Average precision | 0.7776 | 0.8039 |

Interpretation: the larger checkpoint is not an unambiguous improvement. Its slightly higher ranking metric on this tiny selection is not evidence of better generalization; its synthetic recall at the unchanged threshold is lower. The web model remains AASIST-L. Both are development candidates, not validated field detectors. Comparing on this already inspected pilot is exploratory and not an independent final test.

Sample limits and acquisition: see ../public-pilot/README.md. No speaker/source-independent sample split was created, and potential upstream training overlap was not independently excluded. The diagnostic runner is CPU-only and bounded to256files. These results must not be called sponsor performance, calibrated probabilities, or evidence that genuine speech was authenticated.

Scope distinction: the isolated candidate scores every decoded clip and does not apply the web pipeline's too-quiet rejection gate. This pilot contains labeled speech with usable baseline scores; future comparisons must explicitly align eligibility policies. Current candidate run metadata documents this distinction; the original24clip artifact predates that explanatory field.
