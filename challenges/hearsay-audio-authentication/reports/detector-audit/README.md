# Retained baseline error audit

`public-pilot-errors.json` joins the existing 24-row public pilot manifest and score CSV by file ID. It reports each error and counts by synthetic generator at the original fixed threshold of 0.5. The command and interpretation are documented in [scoring-audit.md](../../../../docs/scoring-audit.md).

This is a read-only analysis of the unchanged AASIST-L baseline. No new audio was generated, no inference was rerun, and no performance gain is claimed.
