# Third-party code, models and data

This repository does not confer rights beyond each upstream license. Model weights and audio datasets are downloaded separately and are not included in Git.

- **AASIST / AASIST-L**: NAVER Corp., MIT license. Vendored implementation, configurations, original license and revision attribution are retained in `challenges/hearsay-audio-authentication/backend/echotrace/vendor/`. Upstream: https://github.com/clovaai/aasist.
- **WavLM speaker model**: Microsoft, `microsoft/wavlm-base-plus-sv` on Hugging Face; model revision and hashes are recorded in `speaker.py`. Upstream: https://huggingface.co/microsoft/wavlm-base-plus-sv. Subject to its upstream model terms.
- **Whisper / faster-whisper**: OpenAI Whisper and SYSTRAN faster-whisper; local speech recognition through the installed CTranslate2 runtime. Upstream: https://github.com/SYSTRAN/faster-whisper and https://github.com/openai/whisper.
- **Native frozen detector experiment**: https://huggingface.co/garystafford/wav2vec2-deepfake-voice-detector, Apache-2.0 model card. It is a separately evaluated experiment; published upstream accuracy is not ECHOTRACE accuracy.
- **MLAAD-tiny diagnostic recordings**: https://huggingface.co/datasets/mueller91/MLAAD-tiny. Synthetic recordings: CC BY-NC 4.0; genuine recordings: upstream M-AILABS terms. Only public IDs, hashes, labels and results are included here. Review dataset terms before any redistribution or commercial use.
- **ASVspoof 5**: https://www.asvspoof.org/. Public-data protocols and official download references are documented in the project. Audio is not redistributed. Benchmark results refer only to the documented subsets.
- **Public Sans and IBM Plex Mono fonts**: SIL Open Font License 1.1, included under `third_party/`. Distributed font files originate from the pinned npm lockfile packages.
- **React, Vite, Motion, Lucide, FastAPI, PyTorch, Transformers and other dependencies** retain their respective upstream licenses. Full versions and dependency artifacts are specified in `package-lock.json` and `uv.lock`.

ECHOTRACE is a hackathon prototype addressing the sponsor's challenge, not an official NSA product or endorsement.
