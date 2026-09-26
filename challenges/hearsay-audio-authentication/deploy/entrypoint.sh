#!/usr/bin/env bash
set -euo pipefail

ARTIFACTS_DIR=/data/artifacts
WORKSPACE_DIR="${ECHOTRACE_WORKSPACE:-/data/workspace}"
NII_WEIGHTS="${ARTIFACTS_DIR}/nii-model/model.safetensors"
SPEAKER_DIR="${ARTIFACTS_DIR}/speaker-model"
WHISPER_MODEL="${ECHOTRACE_WHISPER_MODEL:-base}"
WHISPER_CACHE="${WORKSPACE_DIR}/models/faster-whisper"

log() { printf '[entrypoint] %s\n' "$*" >&2; }
fail() { log "ERROR: $*"; exit 1; }

dir_has_content() { [[ -d "$1" ]] && [[ -n "$(ls -A "$1" 2>/dev/null)" ]]; }

if [[ -z "${ECHOTRACE_PUBLIC_URL:-}" ]]; then
  fail "ECHOTRACE_PUBLIC_URL is not set. Set it in deploy/.env to https://<your-domain> (no trailing slash)."
fi
if [[ "${ECHOTRACE_PUBLIC_URL}" != https://* ]]; then
  log "WARNING: ECHOTRACE_PUBLIC_URL does not start with https://; session cookies will not be marked Secure."
fi

command -v ffmpeg >/dev/null || fail "ffmpeg is not on PATH."
command -v ffprobe >/dev/null || fail "ffprobe is not on PATH."

mkdir -p "${ARTIFACTS_DIR}" "${WORKSPACE_DIR}" "${HF_HOME:-/data/cache/huggingface}"
[[ -w "${ARTIFACTS_DIR}" && -w "${WORKSPACE_DIR}" ]] || fail "/data is not writable by uid $(id -u)."

if [[ ! -s "${NII_WEIGHTS}" ]]; then
  log "Pinned NII weights missing; downloading and verifying (~380 MB)..."
  echotrace setup-model || fail "NII model setup failed. Check network access to huggingface.co and free disk space."
fi

if [[ "${ECHOTRACE_INSTALL_SPEAKER:-0}" == "1" ]] && ! dir_has_content "${SPEAKER_DIR}"; then
  log "Installing pinned WavLM speaker model..."
  python -m echotrace.speaker || fail "Speaker model setup failed."
fi

if [[ "${ECHOTRACE_INSTALL_WHISPER:-0}" == "1" ]] && ! dir_has_content "${WHISPER_CACHE}"; then
  log "Installing faster-whisper '${WHISPER_MODEL}' into ${WHISPER_CACHE}..."
  python -m echotrace.transcription --model "${WHISPER_MODEL}" --cache-dir "${WHISPER_CACHE}" \
    || fail "Whisper model setup failed."
fi

log "Starting ECHOTRACE on :8000 (single worker)."
exec uvicorn echotrace.api:app \
  --host 0.0.0.0 \
  --port 8000 \
  --proxy-headers \
  --forwarded-allow-ips '*' \
  --workers 1
