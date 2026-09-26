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
