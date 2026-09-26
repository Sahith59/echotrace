# ECHOTRACE problem validation

Date checked: 2026-09-25. Scope: NSA Challenge 1, **HEARSAY: The Audio Authentication Challenge**. This is a problem and workflow assessment, not evidence that ECHOTRACE detects synthetic speech accurately.

## Decision

**Go for a bounded forensic triage tool and the sponsor's held-out evaluation.** There is documented real-world misuse of synthetic voices, and the [sponsor brief](../challenges/hearsay-audio-authentication/CHALLENGE.md) directly requests file-based analysis, multiple forensic techniques, a 0–100 synthesis-likelihood score, and a test-set CSV. The strongest product claim is that ECHOTRACE helps an analyst prioritize and inspect a recording. A score alone cannot authenticate a caller, establish who spoke, or authorize a transfer.

## Evidence of urgency

| Finding | What it establishes | What it does **not** establish |
| --- | --- | --- |
| In its [May 15, 2025 public alert](https://www.fbi.gov/investigate/cyber/alerts/2025/senior-us-officials-impersonated-in-malicious-messaging-campaign), the FBI reported a campaign active since April 2025 using AI-generated voice messages that purported to come from senior U.S. officials. Targets included current or former federal and state officials and their contacts. | A concrete, operational voice-impersonation case relevant to security teams. | Prevalence of such calls or detector effectiveness. |
| The [FTC's November 2023 voice-cloning challenge announcement](https://www.ftc.gov/policy/advocacy-research/tech-at-ftc/2023/11/preventing-harms-ai-enabled-voice-cloning) identified risks to families, small businesses, and creative professionals. The [FTC's July 2024 filing announcement](https://www.ftc.gov/news-events/news/press-releases/2024/07/ftc-submits-comment-fcc-work-protect-consumers-potential-harmful-effects-ai) says scammers use cloned voices to impersonate family, friends, and executives to obtain money. | A federal consumer-protection agency treats misuse as a present problem across several contexts. | A measured count or dollar loss caused specifically by voice clones. |
| The [2025 FBI IC3 annual report](https://www.ic3.gov/AnnualReport/Reports/2025_IC3Report.pdf) records **22,364 complaints** reporting AI-related information and **$893,346,472 in adjusted losses**. It describes voice cloning as *one possible tactic* in business email compromise and family distress scams. | AI-related fraud is large enough to warrant investigation, with voice cloning among the described tactics. | The complaint and loss totals **are not voice-cloning totals**; AI involvement is based on information reported in complaints. The report's distress-scam and business-email-compromise amounts also mix tactics and cannot be assigned to cloned voices. |
| The [FTC's June 2026 data release](https://www.ftc.gov/news-events/news/press-releases/2026/06/ftc-data-show-people-reported-losing-3-point-5-billion-imposter-scams-2025) reports **$3.5 billion in reported 2025 imposter-scam losses**, with contact through text, phone, email, social media, search, and other channels. | Impersonation is a serious, adjacent fraud category. | This is **not** an AI, audio, or voice-cloning loss estimate. |

The FTC stated in [released congressional correspondence](https://www.ftc.gov/system/files/ftc_gov/pdf/2024-00414_final_records_for_release_part_3.pdf) that the number of Americans targeted by scammers using generative AI remained unknown. The public evidence above establishes credible misuse and high stakes; it does not support a numerical claim about voice-cloning prevalence.

## User and workflow

**Primary user (product hypothesis):** a security or multimedia-forensics analyst who has a saved call, voicemail, or voice message and must decide which recordings merit closer examination. This is an inferred workflow based on the FBI alert and the sponsor's file-input requirement, not a user-research finding. The analyst uploads the original recording, receives a clearly labeled synthesis-likelihood estimate and complementary forensic observations, inspects suspicious intervals and model limitations, then records the result for human review. The sponsor's labeled training and held-out test sets provide the near-term evaluation path; their contents and scoring rules are still unavailable in this repository.

**Immediate decision:** queue a recording for further review and independently verify the claimed speaker through a known channel before acting. The [FBI's 2025 alert](https://www.fbi.gov/investigate/cyber/alerts/2025/senior-us-officials-impersonated-in-malicious-messaging-campaign) and [FTC consumer guidance](https://consumer.ftc.gov/articles/scammers-use-fake-emergencies-steal-your-money) both recommend independent contact or verification. This safety step remains necessary regardless of ECHOTRACE's output.

## Why this challenge and approach

The [HEARSAY brief](../challenges/hearsay-audio-authentication/CHALLENGE.md) makes file-level synthetic-speech scoring and a CSV the acceptance target. ECHOTRACE's workbench can make the score reviewable with playback, suspicious intervals, and technique-level evidence, while a reproducible batch path satisfies the evaluation requirement. Manipulation type is optional in the brief, so the project must not imply reliable subtype identification without a validated classifier.

There are adjacent interventions. The [FTC's April 2024 review](https://www.ftc.gov/policy/advocacy-research/tech-at-ftc/2024/04/approaches-address-ai-enabled-voice-cloning) groups ideas into upstream prevention/authentication, real-time detection, and post-use evaluation. ECHOTRACE sits in **post-use evaluation** because the challenge provides audio files. Source capture or cryptographic provenance could offer stronger origin evidence when deployed at recording time, and independent callback verification protects a live decision. Neither is replaced by retrospective acoustic analysis.

## Conditions for a defensible demo

1. Show actual model inference and distinct automatic forensic techniques on real files; do not present handcrafted demo scores as detections.
2. Evaluate on held-out data using the sponsor's metric and report errors, especially false reassurance and performance on compression, noise, short speech, and unseen generators if the data permits. A 0–100 score must be called a *synthesis-likelihood estimate* until calibration on relevant data justifies probability language.
3. Preserve original audio and record preprocessing and model versions so an analyst can reproduce a result. Explicitly return `undetermined` or an error for silence, unsupported content, or model failure.
4. Export predictions for every provided test file in the sponsor's required CSV schema once the template is available.

**No-go for any claim of operational authentication** until an independent, relevant evaluation establishes acceptable error rates and calibration. Even then, a low synthesis score cannot verify identity or intent. The current repository contains no sponsor dataset, measured model results, user interviews, or evidence of field performance.
