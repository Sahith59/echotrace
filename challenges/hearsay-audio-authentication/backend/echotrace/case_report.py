"""Read-only case exports: separate synthesis, speaker, words and external claims."""
from __future__ import annotations

import html
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from .claims_router import load_claim_artifacts
from .interpretation import evidence_for, evidence_hash
from .analyst_review import load_analyst_review

SUMMARY_PATH = Path(__file__).with_name('validation_summary.json')
BOUNDARY = ('Synthesis, voice similarity and factual claims are independent assessments. '
            'No combined authenticity probability is calculated. Neither voice similarity '
            'nor a synthesis score proves identity, intent or factual truth.')


def case_report(store, job_id):
    try:
        job = store.get(job_id)
    except KeyError:
        raise HTTPException(404, 'Recording not found') from None
    if job['status'] != 'completed':
        raise HTTPException(409, 'Complete analysis before exporting a case report.')
    with store.connect() as db:
        row = db.execute('SELECT report FROM speaker_comparisons WHERE job_id=?', (job_id,)).fetchone()
        detector = db.execute('SELECT report FROM detector_comparisons WHERE job_id=?', (job_id,)).fetchone()
    return {
        'schema_version': 'echotrace.case.v1', 'job_id': job_id,
        'filename': job['filename'], 'created_at': job['created_at'],
        'synthesis': job['result'],
        'speaker_comparison': json.loads(row['report']) if row else None,
        'detector_comparison': json.loads(detector['report']) if detector else None,
        'analyst_review': load_analyst_review(store, job_id),
        **load_claim_artifacts(store, job_id),
        'overall_authenticity_probability': None, 'interpretation_boundary': BOUNDARY,
    }


def printable(report):
    esc = lambda value: html.escape(str(value), quote=True)
    synthesis = report['synthesis']
    score = synthesis.get('synthetic_score')
    score_text = f'{score * 100:.2f} / 100' if isinstance(score, (int, float)) else 'Unavailable'
    speaker = report['speaker_comparison']
    speaker_text = (f"Cosine similarity {speaker['similarity']['cosine']:.4f} · uncalibrated · "
                    f"reference: {speaker['reference']['label']}" if speaker else 'No reference comparison performed.')
    detector = report.get('detector_comparison')
    detector_text = ('Primary ' + esc(f"{detector['primary_score'] * 100:.2f}") + ' / 100 · experimental NII ' +
                     esc(f"{detector['candidate_score'] * 100:.2f}") + ' / 100 · difference ' +
                     esc(f"{detector['score_difference'] * 100:+.2f}") + ' score points (0–100 scale). ' + esc(detector['limitation'])
                     if detector else 'No experimental detector comparison generated.')
    analyst = report.get('analyst_review') or {"status": "needs_review", "notes": "", "version": 0}
    analyst_text = ('<p><b>' + esc(analyst['status'].replace('_', ' ')) + '</b> · revision ' +
                    esc(analyst.get('version', 0)) + '</p><p>' +
                    esc(analyst.get('notes') or 'No analyst notes recorded.') + '</p>')
    interpretation = synthesis.get('interpretation')
    provider_label = {'groq': 'Groq', 'xai': 'Grok'}.get((interpretation or {}).get('provider'), 'Unknown provider')
    ai_title = '<h3>AI interpretation (' + provider_label + ')</h3>'
    ai_html = '<h3>AI interpretation</h3><p>No AI interpretation generated.</p>'
    if interpretation and interpretation.get('status') == 'generated':
        saved_evidence = interpretation.get('evidence')
        expected_evidence = saved_evidence if isinstance(saved_evidence, list) else evidence_for(synthesis)
        if interpretation.get('evidence_sha256') != evidence_hash(expected_evidence):
            ai_html = ai_title + '<p>Saved AI interpretation no longer matches the measurements.</p>'
        else:
            brief = interpretation['report']
            ai_html = (ai_title + '<small>AI-written · ' +
                esc(interpretation.get('model', '')) + ' · Review against the measurements.</small><p>' +
                esc(brief['summary']) + '</p><ul>' + ''.join('<li>' + esc(finding['text']) +
                ' [' + esc(', '.join(finding['evidence_ids'])) + ']</li>' for finding in brief['findings']) +
                '</ul><p><b>Suggested next steps</b></p><ul>' +
                ''.join('<li>' + esc(step) + '</li>' for step in brief['next_steps']) + '</ul>')
    def passage(item):
        span = item.get('span')
        if not span:
            return ''
        return '<p><small>Passage ' + esc(f"{span['start_s']:.2f}–{span['end_s']:.2f} s · transcript version {item.get('transcript_version', '—')}") + '</small></p>'
    transcript = report['transcript']
    claims = ''.join('<article><h3>' + esc(item['text']) + '</h3><p><b>' +
        esc(item.get('verdict', 'uncheckable').replace('_', ' ')) + '</b> · ' + esc(item.get('method', '')) +
        '</p><p>' + esc(item.get('rationale', '')) + '</p>' + passage(item) +
        ('<p><b>Transcript changed; this review needs rechecking.</b></p>' if item.get('stale_transcript') else '') +
        '<ul>' + ''.join('<li>' + esc(source.get('title') or source['url']) + '<br>' + esc(source['url']) + '</li>'
                        for source in item.get('evidence', [])) + '</ul></article>' for item in report['claims'])
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
        '<title>ECHOTRACE · Case report</title><style>body{font:15px/1.65 system-ui,sans-serif;color:#202124;max-width:850px;'
        'margin:50px auto;padding:0 24px}h1{font-size:30px}h2{font-size:19px;margin-top:32px;border-top:1px solid #ddd;'
        'padding-top:22px}small{color:#666}pre{font:11px/1.5 monospace;white-space:pre-wrap;overflow-wrap:anywhere}'
        'p,li{overflow-wrap:anywhere}article{border-left:2px solid #bbb;padding-left:18px} @media print{body{margin:0;'
        'max-width:none}details{display:block}article{break-inside:avoid}}</style>'
        '<body><small>ECHOTRACE / INDEPENDENT AUDIO REVIEW</small><h1>' + esc(report['filename']) + '</h1><p>Case ' +
        esc(report['job_id']) + ' · ' + esc(report['created_at']) + '</p><p>' + esc(BOUNDARY) + '</p>'
        '<h2>1. Synthesis assessment</h2><p><b>' + esc(score_text) + '</b> · ' +
        esc(synthesis.get('score_kind', 'uncalibrated model score')) + '</p><p>A low score does not establish authenticity.</p>'
        + ai_html + '<h2>2. Speaker reference</h2><p>' + esc(speaker_text) + '</p><p>Similarity is not an identity verdict.</p>'
        '<h2>Experimental detector comparison</h2><p>' + detector_text + '</p>'
        '<h2>Analyst review</h2>' + analyst_text +
        '<h2>3. Transcript</h2><p>' + esc(transcript.get('text') or 'No transcript generated.') + '</p>'
        '<small>Version ' + esc(transcript.get('version', '—')) + ' · ' + esc(transcript.get('source', 'unavailable')) + '</small>'
        '<h2>4. Claim reviews</h2>' + (claims or '<p>No claims reviewed.</p>') +
        '<h2>Full evidence and provenance</h2><pre>' + esc(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False)) + '</pre></body></html>')


def create_case_router(store):
    router = APIRouter()

    @router.get('/api/analyses/{job_id}/case-report')
    def download(job_id: str):
        return JSONResponse(case_report(store, job_id), headers={
            'Content-Disposition': 'attachment; filename="echotrace-case.json"', 'Cache-Control': 'no-store'})

    @router.get('/api/analyses/{job_id}/case-report.html')
    def report_html(job_id: str):
        return HTMLResponse(printable(case_report(store, job_id)), headers={
            'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'",
            'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'no-store'})

    @router.get('/api/model/evaluation')
    def evaluation():
        return json.loads(SUMMARY_PATH.read_text())

    return router
