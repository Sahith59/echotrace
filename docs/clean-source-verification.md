# HEARSAY clean-source verification

Verification date: 2026-09-26

Verified source commit:
`a3123392482d0922105c8e125f9974499baa93a0`.

This is a record of the clean-source gate at that commit. Later commits were
deliberately excluded from this record and require the final integration gate.
No `.env`, workspace dataset, downloaded model cache, or untracked file was
copied into the source tree used below. No remote Git operation or paid service
was used.

## Environment

- macOS arm64
- Python 3.11.14
- uv 0.11.19
- FFmpeg 8.1.1, already installed on the host
- Node.js 26.0.0 and npm 11.12.1
- Common native thread pools and uv download/build concurrency capped at four

The GitHub Actions workflow separately pins Python 3.11 and Node.js 20. The
local frontend result therefore checks the locked package graph and build on a
newer Node runtime as an additional compatibility point; CI remains the Node
20 release gate.

## Isolated source

From the repository root:

```sh
verify_dir=$(mktemp -d /tmp/echotrace-release-head.XXXXXX)
git archive a3123392482d0922105c8e125f9974499baa93a0 | tar -x -C "$verify_dir"
find "$verify_dir" -name .env -o -name '*.wav' -o -name '*.mp3'
```

The `find` command returned no paths. The archive contained the locked backend
and frontend inputs, AASIST configuration, and public-pilot provenance manifest.

## Backend

From `challenges/hearsay-audio-authentication/backend` inside the archive:

```sh
UV_CONCURRENT_DOWNLOADS=4 \
UV_CONCURRENT_BUILDS=4 \
CMAKE_BUILD_PARALLEL_LEVEL=4 \
OMP_NUM_THREADS=4 \
OPENBLAS_NUM_THREADS=4 \
MKL_NUM_THREADS=4 \
uv sync --python 3.11 --frozen --all-groups

uv run python -c 'import sys; assert sys.version_info[:2] == (3, 11), sys.version'

cert_file=$(uv run python -m certifi)
SSL_CERT_FILE="$cert_file" \
UV_CONCURRENT_DOWNLOADS=4 \
OMP_NUM_THREADS=4 \
OPENBLAS_NUM_THREADS=4 \
MKL_NUM_THREADS=4 \
uv run echotrace setup-model

UV_CONCURRENT_DOWNLOADS=4 \
OMP_NUM_THREADS=4 \
OPENBLAS_NUM_THREADS=4 \
MKL_NUM_THREADS=4 \
uv run pytest -q
```

Results:

- Frozen sync installed 60 locked packages under Python 3.11.14.
- `setup-model` downloaded the pinned official AASIST-L checkpoint and verified
  SHA-256
  `814331d088032bb4c3fa61cc014789eadeed464209dd094ab3a2dd6ffbdce27a`.
- Model status reported `available: true`, upstream revision
  `a04c9863f63d44471dde8a6abcb3b082b07cd1d1`, and CPU device.
- Backend: 240 tests passed. One third-party Starlette/httpx deprecation warning
  was emitted.

The host Python's system CA store initially rejected GitHub's certificate. The
successful command above used the locked `certifi` CA bundle and retained full
TLS verification; no insecure TLS option was used.

## Frontend

After the backend result was recorded, its temporary `.venv` and downloaded
checkpoint were removed to stay within the host's temporary-volume limit. From
`challenges/hearsay-audio-authentication/frontend` in the same archive:

```sh
npm_config_jobs=4 npm ci
UV_THREADPOOL_SIZE=4 npm test
UV_THREADPOOL_SIZE=4 npm run build
```

Results:

- `npm ci` installed 193 locked packages and reported zero vulnerabilities.
- Frontend: 30 tests passed across five test files.
- TypeScript and Vite production build passed.

## Public example setup

The first live trial exposed a release defect: the pinned Hugging Face resolve
URL returned a signed HTTP 302 to `us.aws.cdn.hf.co`, while the downloader
rejected every redirect. The fix was developed test-first:

- RED: `bfd6c3a7dcd56499368fab3aad7c074188deb878`
- GREEN: `e6bb9463a68e768b382d811f21723212a7474b74`

The downloader now permits one HTTPS hop from the exact pinned
`huggingface.co` resolve path to a fixed Hugging Face delivery-host allowlist.
It rejects other hosts, cleartext URLs, credentials, ports, fragments, and a
second redirect. Exact per-file byte counts and SHA-256 values remain mandatory.

Using the archived `echotrace.setup_examples` module and Python 3.11:

```sh
clips_dir=$(mktemp -d /tmp/echotrace-release-head-clips.XXXXXX)
python3.11 -m echotrace.setup_examples \
  --confirm-source-review \
  --output "$clips_dir"

python3.11 -m echotrace.setup_examples \
  --confirm-source-review \
  --output "$clips_dir"
```

`SSL_CERT_FILE` was set to the same verified `certifi` bundle for these commands
on this host. The first run downloaded and verified all 24 files, totaling
5,274,736 bytes. The second run downloaded zero files and verified/skipped all
24 existing files. The command printed the dataset, attribution, license, and
terms links and stated that the confirmation flag does not accept or determine
legal terms.

## Optional model setup entrypoints

The archived source was used for help-only checks; no speaker or Whisper model
was downloaded:

```sh
python -m echotrace.speaker --help
python -m echotrace.transcription --help
```

Both returned status zero and displayed the bounded cache/model arguments.

## Setup feature commits

The original reproducible setup and CI work was also developed test-first:

- RED: `07fc2cfbf1d146727ba08a948e947845216cc7e8`
- GREEN: `0752a3ce4723a4789ec13f630c0a8dfe2de78808`

