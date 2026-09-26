from fastapi.testclient import TestClient
from echotrace.api import create_app


def test_case_report_separates_evidence_and_escapes_html(tmp_path):
    app = create_app(root=tmp_path)
    store = app.state.store
    store.create('case', '<script>alert(1)</script>.wav', tmp_path / 'private.wav')
    store.update('case', status='completed', result={
        'synthetic_score': .15, 'score_kind': 'uncalibrated_model_score',
        'input': {'sha256': 'a' * 64}, 'model': {'version': 'baseline'},
    })
    with TestClient(app) as client:
        result = client.get('/api/analyses/case/case-report')
        assert result.status_code == 200
        data = result.json()
        assert data['synthesis']['synthetic_score'] == .15
        assert data['speaker_comparison'] is None
        assert data['claims'] == []
        assert data['transcript']['status'] == 'not_generated'
        assert 'path' not in data
        assert data['overall_authenticity_probability'] is None
        page = client.get('/api/analyses/case/case-report.html')
        assert page.status_code == 200
        assert '<script>alert(1)</script>' not in page.text
        assert '&lt;script&gt;' in page.text
        assert 'default-src' in page.headers['content-security-policy']


def test_reports_reject_missing_and_incomplete_cases(tmp_path):
    app = create_app(root=tmp_path)
    app.state.store.create('pending', 'a.wav', tmp_path / 'a.wav')
    with TestClient(app) as client:
        assert client.get('/api/analyses/missing/case-report').status_code == 404
        assert client.get('/api/analyses/pending/case-report').status_code == 409


def test_model_evaluation_discloses_failed_promotion_and_linked_weights(tmp_path):
    with TestClient(create_app(root=tmp_path)) as client:
        result = client.get('/api/model/evaluation')
        assert result.status_code == 200
        report = result.json()
        assert report['experiments'][0]['promoted'] is False
        assert report['experiments'][0]['candidate']['recall'] < .8
        assert len(report['experiments'][0]['candidate_weights_sha256']) == 64
        assert 'not sponsor' in report['scope'].lower()


def test_printable_report_surfaces_ai_notes_and_claim_timestamps():
    from echotrace.case_report import printable
    from echotrace.interpretation import evidence_for, evidence_hash
    synthesis = {'synthetic_score': .15, 'score_kind': 'uncalibrated_model_score'}
    synthesis['interpretation'] = {
        'status': 'generated', 'provider': 'xai', 'model': 'grok-test',
        'evidence_sha256': evidence_hash(evidence_for(synthesis)),
        'report': {'summary': 'Review <carefully>.',
                   'findings': [{'text': 'The score is uncalibrated.', 'evidence_ids': ['calibration']}],
                   'next_steps': ['Listen to the original.']},
    }
    report = {'filename': 'test.wav', 'job_id': 'case', 'created_at': '2026-09-26',
              'synthesis': synthesis, 'speaker_comparison': None,
              'transcript': {'text': 'A claim.', 'version': 1, 'source': 'automatic'},
              'claims': [{'text': 'A claim.', 'method': 'analyst', 'verdict': 'uncheckable',
                          'rationale': 'No source reviewed.', 'span': {'start_s': .02, 'end_s': 4.42},
                          'transcript_version': 1, 'evidence': []}]}
    page = printable(report)
    readable = page.split('<pre>')[0]
    assert 'AI interpretation (Grok)' in readable
    assert 'Review &lt;carefully&gt;.' in readable
    assert 'The score is uncalibrated. [calibration]' in readable
    assert 'Listen to the original.' in readable
    assert 'Passage 0.02–4.42 s · transcript version 1' in readable
    synthesis['synthetic_score'] = .8
    stale = printable(report).split('<pre>')[0]
    assert 'Review &lt;carefully&gt;.' not in stale
    assert 'Saved AI interpretation no longer matches the measurements.' in stale
