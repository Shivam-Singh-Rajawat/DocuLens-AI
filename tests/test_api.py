from fastapi.testclient import TestClient
from doculens.api import create_app


def test_api_health_ingest_chat_delete(service):
    client=TestClient(create_app(service))
    assert client.get('/api/health').json()['status']=='ok'
    upload=client.post('/api/documents/upload',content=b'Vector databases store embeddings for retrieval.',headers={'X-Filename':'facts.txt','Content-Type':'application/octet-stream'})
    assert upload.status_code==201,upload.text
    doc=upload.json()
    assert doc['chunks']>0
    result=client.post('/api/chat',json={'question':'What do vector databases store?','rerank':False})
    assert result.status_code==200,result.text
    assert result.json()['sources'][0]['source_id']==doc['id']
    assert client.get('/api/documents').json()[0]['id']==doc['id']
    assert client.get('/api/documents/'+doc['id']+'/file').status_code==200
    assert client.delete('/api/documents/'+doc['id']).json()['deleted']
    assert client.get('/api/documents/'+doc['id']).status_code==404


def test_api_validation(service):
    client=TestClient(create_app(service))
    assert client.post('/api/documents/text',json={'content':''}).status_code==422
    assert client.post('/api/documents/url',json={'url':'file:///etc/passwd'}).status_code in (400,422)
    assert client.post('/api/search',json={'question':'hi','top_k':100}).status_code==422


def test_api_token_required_when_configured(service):
    service.settings.app_token="demo-secret"
    client=TestClient(create_app(service))
    assert client.get('/api/documents').status_code==401
    assert client.get('/api/health').status_code==200
    assert client.get('/api/documents',headers={'X-App-Token':'demo-secret'}).status_code==200


def test_dashboard_is_served_from_the_api(service):
    client=TestClient(create_app(service))
    page=client.get('/')
    assert page.status_code==200 and 'Ask your documents' in page.text
    assert 'customInstructions' in page.text
    assert client.get('/app.js').status_code==200
    assert client.get('/styles.css').status_code==200
