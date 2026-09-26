# ECHOTRACE — HEARSAY solution

Status: first working local prototype implemented; competition evaluation not complete.

[Run the application and review its limitations](README.md).

An audio-forensics workbench for NSA Challenge 1. Upload a recording, run complementary analyses, inspect the synthesis-likelihood estimate and suspicious intervals, and export predictions for the sponsor's held-out evaluation. Optional compression/noise comparisons show sensitivity; they do not prove authenticity.

- [Ordered implementation plan](../../plan.md)
- [Project instructions](../../claude.md)
- [Persistent memory and open questions](../../memory.md)
- [Independent planning reviews](../../docs/reviews.md)
- [Original challenge](CHALLENGE.md)

The critical deliverable is a reproducible real scoring pipeline with a validated official-schema CSV. Model selection, calibration, performance and manipulation classes depend on supplied data and measured validation. The app, real pretrained inference, and integration tests exist. Sponsor evaluation and calibrated likelihood estimates do not yet exist. A known synthetic TTS smoke clip received a low score from the current baseline; see the application README before interpreting outputs.
