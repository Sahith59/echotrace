from fastapi.testclient import TestClient
from echotrace.api import create_app


def test_advertised_opus_keeps_playable_media_type(tmp_path):
    app = create_app(root=tmp_path, analyzer=lambda p, progress=None: {'synthetic_score': .2})
    with TestClient(app) as client:
        upload = client.post('/api/analyses', files={'file': ('sample.opus', b'qa-test-content', 'audio/ogg')})
        assert upload.status_code == 202
        job = app.state.store.get(upload.json()['id'])
        assert job['path'].endswith('.opus')
        playback = client.get('/api/analyses/' + job['id'] + '/audio')
        assert playback.headers['content-type'].split(';')[0] == 'audio/ogg'
