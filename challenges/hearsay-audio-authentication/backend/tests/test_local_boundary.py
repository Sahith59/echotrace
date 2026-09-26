from fastapi.testclient import TestClient
from echotrace.api import create_app


def test_local_api_rejects_cross_site_mutation_before_processing(tmp_path):
    with TestClient(create_app(root=tmp_path)) as client:
        response = client.post('/api/analyses', headers={'Origin': 'https://unrelated.example'}, files={'file': ('a.wav', b'bad', 'audio/wav')})
        assert response.status_code == 403
        assert client.get('/api/analyses').json() == []


def test_local_api_rejects_unrecognized_host_and_allows_local_origin(tmp_path):
    with TestClient(create_app(root=tmp_path)) as client:
        assert client.get('/api/analyses', headers={'Host': 'unrelated.example'}).status_code == 400
        assert client.post('/api/exports', headers={'Origin': 'http://127.0.0.1:5173'}, json={'ids': []}).status_code != 403


def test_analyst_csv_does_not_execute_filename_as_spreadsheet_formula(tmp_path):
    app = create_app(root=tmp_path)
    store = app.state.store
    store.create('safe-id', '=QA formula.wav', tmp_path/'a.wav')
    store.update('safe-id', status='completed', result={'synthetic_score':.4,'model':{'name':'test'},'input':{'sha256':'a'*64}})
    with TestClient(app) as client:
        import csv, io
        response=client.post('/api/exports',json={'ids':['safe-id']})
        assert response.status_code == 200
        row=next(csv.DictReader(io.StringIO(response.text)))
        assert row['filename'] == "'=QA formula.wav"
        assert client.get('/api/analyses/safe-id').json()['filename'] == '=QA formula.wav'
