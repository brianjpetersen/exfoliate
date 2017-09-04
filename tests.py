import pytest
import exfoliate
import concurrent.futures


class TestClient:
    
    def test_multiple_clients(self):
        client_1 = exfoliate.Client()
        client_2 = exfoliate.Client()
        future_1 = client_1.get('https://httpbin.org/anything')
        future_2 = client_2.get('https://httpbin.org/anything')
        assert future_1.response().json() == future_2.response().json()
        assert client_1.connector != client_2.connector
    
    def test_methods(self):
        client = exfoliate.Client()
        for method_name in ('GET', 'PUT', 'POST', 'DELETE', ):
            method = getattr(client, method_name.lower())
            future = method('https://httpbin.org/anything')
            response = future.response()
            assert response.status_code == 200
            assert response.json()['method'] == method_name

    def test_nonblocking(self):
        client = exfoliate.Client()
        blocking_future = client.get('https://httpbin.org/delay/1')
        nonblocking_future = client.get('https://httpbin.org/delay/0')
        target_futures = (nonblocking_future, blocking_future, )
        for future, target_future in zip(client.futures, target_futures):
            assert future == target_future
    
    def test_default_cookie_isolation(self):
        client = exfoliate.Client()
        future_1 = client.get('https://httpbin.org/cookies/set?a=1&c=3')
        future_2 = client.get('https://httpbin.org/cookies/set?b=2&c=3')
        response_1 = future_1.response().json()
        response_2 = future_2.response().json()
        assert response_1 == {'cookies': {'a': '1', 'c': '3'}}
        assert response_2 == {'cookies': {'b': '2', 'c': '3'}}
        
    def test_shared_cookies(self):
        cookie_jar = exfoliate.CookieJar()
        client = exfoliate.Client(cookie_jar=cookie_jar)
        future_1 = client.get('https://httpbin.org/cookies/set?a=1&c=3')
        response_1 = future_1.response().json()
        future_2 = client.get('https://httpbin.org/cookies/set?b=2&c=3')
        response_2 = future_2.response().json()
        assert response_1 == {'cookies': {'a': '1', 'c': '3'}}
        assert response_2 == {'cookies': {'a': '1', 'b': '2', 'c': '3'}}
    
    def test_headers(self):
        client = exfoliate.Client()
        headers = {'X-Test-Exfoliate': 'awesome'}
        future = client.get('https://httpbin.org/headers', headers=headers)
        response = future.response().json()
        assert response['headers']['X-Test-Exfoliate'] == 'awesome'
    
    def test_repeat_request(self):
        client = exfoliate.Client()
        future_initial = client.get('https://httpbin.org/anything')
        response_initial = future_initial.response().json()
        future_repeated = future_initial.repeat()
        response_repeated = future_repeated.response().json()
        assert response_repeated == response_initial


class TestFutures:
    
    def test_len(self):
        futures = exfoliate.Futures()
        future_1 = concurrent.futures.Future()
        future_2 = concurrent.futures.Future()
        futures.add(future_1)
        assert len(futures) == 1
        futures.add(future_1)
        assert len(futures) == 1
        futures.add(future_2)
        assert len(futures) == 2
    
    def test_iter(self):
        futures = exfoliate.Futures()
        future_1 = concurrent.futures.Future()
        future_2 = concurrent.futures.Future()
        future_3 = concurrent.futures.Future()
        future_1.set_result(None)
        futures.add(future_1)
        futures.add(future_2)
        future_2.set_result(None)
        futures.add(future_3)
        expected_futures = set((future_1, future_2, ))
        for i, future in enumerate(futures):
            if i == 0:
                assert future in expected_futures
                expected_futures.remove(future)
            if i == 1:
                assert future in expected_futures
                future_3.set_result(None)
            if i == 2:
                assert future == future_3
    
    def test_remove_and_contains(self):
        futures = exfoliate.Futures()
        future_1 = concurrent.futures.Future()
        future_2 = concurrent.futures.Future()
        future_2.set_result(1)
        futures.add(future_1)
        futures.add(future_2)
        assert len(futures) == 2
        assert future_1 in futures
        assert future_2 in futures
        futures.remove(future_1)
        assert len(futures) == 1
        assert future_2 in futures
        assert future_1 not in futures
        with pytest.raises(KeyError):
            futures.remove(future_1)


class TestResponse:
    
    def test_text(self):
        client = exfoliate.Client()
        future = client.get('https://httpbin.org/encoding/utf8')
        response = future.response()
        assert len(response.text()) == 7808
        assert len(response.content) == 14239
