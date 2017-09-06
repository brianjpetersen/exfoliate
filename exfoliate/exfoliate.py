"""Exfoliate is the asynchronous HTTP client for developers who prefer synchronous Python.

Enjoy the benefits of a scalable, asynchronous HTTP client without worrying about coroutines or 
event loops.  Exfoliate is the gentler, more Pythonic way to scrape the web.
"""
import asyncio
import aiohttp
import threading
import types
import concurrent.futures
import atexit
import json
import collections
import time
import chardet


# expose relevant aiohttp classes here
TCPConnector = aiohttp.TCPConnector
CookieJar = aiohttp.CookieJar
DummyCookieJar = aiohttp.DummyCookieJar


class Futures(collections.abc.Collection):
    """ A container object that supports iterating over futures as the complete.
    
    The two main differences between this class and concurrent.futures.as_completed are:
    
    * concurrent.futures.as_completed works on any iterable containing futures, whereas Futures
        is a tailored container object
    * the Futures class reflects futures added to it during iteration
    
    The latter of these differences is important to make exfoliate easier to use during web
    scraping.
    
    """
    
    LOCK = threading.RLock()
    
    def __init__(self, futures=None):
        self._complete_set = set()
        self._pending_set = set()
        self._pending_deque = collections.deque()
        if futures is not None:
            with self.LOCK:
                for future in futures:
                    self.add(future)
    
    @property
    def completed(self):
        return self._complete_set
        
    @property
    def pending(self):
        return self._pending_set
    
    def add(self, future):
        if future.done():
            self._complete_set.add(future)
        elif future not in self._pending_set:
            with self.LOCK:
                self._pending_set.add(future)
                self._pending_deque.append(future)
    
    def remove(self, future):
        if future in self._pending_set:
            with self.LOCK:
                self._pending_set.remove(future)
                self._pending_deque.remove(future)
        elif future in self._complete_set:
            self._complete_set.remove(future)
        else:
            raise KeyError(f'Futures object does not contain {future}')
    
    def __contains__(self, future):
        with self.LOCK:
            return (future in self._complete_set) or (future in self._pending_deque)
        
    def __iter__(self):
        for future in self._complete_set:
            yield future
        while len(self._pending_deque):
            future = self._pending_deque[-1]
            if future.done():
                with self.LOCK:
                    self._pending_set.remove(future)
                    self._pending_deque.pop()
                    self._complete_set.add(future)
                yield future
            else:
                self._pending_deque.rotate(1)
                time.sleep(0.1)
    
    def __len__(self):
        with self.LOCK:
            return len(self._complete_set) + len(self._pending_set)
    
    def __repr__(self):
        return 'Futures(({}))'.format(
            ', '.join(repr(future) for future in self._complete_set.union(self._pending_set))
        )



class RequestException(IOError):
    """ An ambiguous exception in completing a Request meant for subclassing.
    """
    def __init__(self, *args, **kwargs):
        response = kwargs.pop('response', None)
        self.response = response
        super(RequestException, self).__init__(*args, **kwargs)


class HTTPError(RequestException):
    """An HTTP error occurred."""


class Response:
    """ A thin wrapper over aiohttp.ClientResponse to allow interaction with the response outside 
        the event loop.
    
    Attributes:
    
        url (str): URL of request
        method (str): method of request, eg 'get'
        version (aiohttp.HttpVersion): HTTP version of response
        status_code (int): HTTP status code of response, eg 200
        headers (multidict.CIMultiDictProxy): case-insensitive multidict representing the HTTP 
            headers of the response
        history (tuple): Response instances of preceding requests (earliest request first) if there 
            were redirects, an empty tuple otherwise
        cookies (http.cookies.SimpleCookie): HTTP cookies of response
        content (bytes): HTTP body of response
    
    """
    def __init__(self, url, method, version, status_code, headers, cookies, history, body):
        self.url = url
        self.method = method
        self.version = version
        self.status_code = status_code
        self.headers = headers
        self.history = history
        self.cookies = cookies
        self.body = self.content = body
    
    def raise_for_status(self):
        if 400 <= self.status_code < 500:
            http_error_message = f'{self.status_code} Server Error for url: {self.url}'
        elif 500 <= self.status_code < 600:
            http_error_message = f'{self.status_code} Server Error for url: {self.url}'
        else:
            http_error_message = None
        if http_error_message is not None:
            raise HTTPError(http_error_message, response=self)
    
    def json(self):
        return json.loads(self.body)
        
    def text(self, encoding=None, errors='strict'):
        if encoding is None:
            encoding = self._get_encoding()
        return self.body.decode(encoding, errors=errors)
        
    def _get_encoding(self):
        ctype = self.headers.get(aiohttp.helpers.hdrs.CONTENT_TYPE, '').lower()
        mtype, stype, _, params = aiohttp.helpers.parse_mimetype(ctype)
        encoding = params.get('charset')
        if not encoding:
            if mtype == 'application' and stype == 'json':
                # RFC 7159 states that the default encoding is UTF-8.
                encoding = 'utf-8'
            else:
                encoding = chardet.detect(self.body)['encoding']
        if not encoding:
            encoding = 'utf-8'
        return encoding
        
    def __repr__(self):
        return '<Response [{}]>'.format(self.status_code)


async def _arequest(method_name, event_loop, connector, cookie_jar, *args, **kwargs):
    """The workhorse async request aiohttp machinery underlying the synchronous Client.
    
    Arguments:
    
        method_name (str): the lowercase HTTP verb (eg, get or post) for the request
        event_loop (asyncio.AbstractEventLoop): the event loop used for aiohttp
        connector (aiohttp.TCPConnector): a connection pool to be shared by requests; this is managed
            external to the session (see connector_owner=False)
        cookie_jar (aiohttp.AbstractCookieJar): the cookie jar to be used for the request
        *args: positional arguments to pass to aiohttp.method request
        **kwargs: keyword arguments to pass to aiohttp.method request
    
    Returns:
    
        response (Response): the HTTP response
    
    A session is created per request to ensure cookie isolation on a per request basis by default.
    This is necessasry for correct handling of cookies for requests resulting in redirects.  The 
    recommended aiohttp solution for this problem is using aiohttp.helpers.DummyCookieJar, but this
    doesn't correctly handle cookies for requests resulting in redirects; see 
    https://github.com/aio-libs/aiohttp/issues/2067 for more details.
    
    """
    session = aiohttp.ClientSession(
        loop=event_loop,
        connector=connector,
        cookie_jar=cookie_jar,
        connector_owner=False,
    )
    async with session:
        method = getattr(session, method_name.lower())
        async with method(*args, **kwargs) as response:
            history = []
            for redirect in response.history:
                body = await redirect.read()
                history.append(
                    Response(
                        redirect.url,
                        redirect.method,
                        redirect.version,
                        redirect.status,
                        redirect.headers,
                        redirect.cookies,
                        (),
                        body,
                    )
                )
            body = await response.read()
            return Response(
                response.url,
                response.method,
                response.version,
                response.status,
                response.headers,
                response.cookies,
                tuple(history),
                body,
            )


class Client:
    """An asynchronous HTTP client that lets you remain ignorant of coroutines, event loops, etc.
    
    Example:
    
        >>> client = Client()
        >>> client.get('https://httpbin.org') # doesn't block!
        >>> future = client.get(
        ...     'https://httpbin.org/headers', 
        ...      headers={'testing': 'exfoliate'},
        ... ) # returns a future!
        >>> for future in client.futures: # iterate over the futures as they resolve!
        ...     response = future.result()
        ...     print(response)
        <Response [200]>
        <Response [200]>
    
    Arguments:
        
        connections (int): number of connections to use for connection pooling in the event a 
            connector is not supplied and one needs to be instantiated
        cookie_jar (aiohttp.AbstractCookieJar or None): the cookie jar to be used for all requests 
            made through this client; if None, use a separate cookie jar for each request
        connector (aiohttp.TCPConnector): a connection pool to be shared by requests
    
    There are several known bugs affecting requests through aiohttp with proxies:
    
    * https://github.com/aio-libs/aiohttp/issues/1340
    * https://github.com/aio-libs/aiohttp/issues/1568
    * http://bugs.python.org/issue29406
    
    In addition, connection pooling with proxies in aiohttp seems to be bug-ridden as well.  
    For example:
    
    >>> client = Client()
    >>> client.get('https://httpbin.org/ip')
    >>> client.get('https://httpbin.org/ip', proxy='...')
    
    Both response bodies will show the IP address of the machine on which the client is being run.
    The workaround is defining a custom TCPConnector and force connections to close:
    
    >>> client = Client(connector=aiohttp.TCPConnector(force_close=True))
    
    This has an appreciable negative impact on performance.
    
    """
    def __init__(self, connections=100, cookie_jar=None, connector=None):
        self.cookie_jar = cookie_jar
        if connector is None:
            self.event_loop = asyncio.SelectorEventLoop()
            connector = aiohttp.TCPConnector(limit=connections, loop=self.event_loop)
        else:
            self.event_loop = connector._loop
        self.connector = connector
        atexit.register(self.connector.close)
        self.futures = Futures()
        self.thread = threading.Thread(target=self.event_loop.run_forever, daemon=True)
        self.thread.start()
    
    def get(self, *args, **kwargs):
        return self._request('get', *args, **kwargs)
    
    def put(self, *args, **kwargs):
        return self._request('put', *args, **kwargs)
    
    def post(self, *args, **kwargs):
        return self._request('post', *args, **kwargs)
    
    def delete(self, *args, **kwargs):
        return self._request('delete', *args, **kwargs)
    
    def head(self, *args, **kwargs):
        return self._request('head', *args, **kwargs)
    
    def options(self, *args, **kwargs):
        return self._request('options', *args, **kwargs)
    
    def _request(self, method_name, *args, **kwargs):
        """Submit the request to the event loop running in thread and bind the future to the client.
        """
        request = _arequest(
            method_name,
            self.event_loop,
            self.connector,
            self.cookie_jar,
            *args, 
            **kwargs,
        )
        future = asyncio.run_coroutine_threadsafe(request, self.event_loop)
        future.response = future.result
        future._request = {
            'client': self,
            'method_name': method_name,
            '*args': args,
            '**kwargs': kwargs,
        }
        def repeat(future):
            """Repeat the request that yielded this future with the same client and arguments.
            """
            request = future._request
            client = request['client']
            method = getattr(client, method_name)
            args = request['*args']
            kwargs = request['**kwargs']
            return method(*args, **kwargs)
        future.repeat = future.retry = types.MethodType(repeat, future)
        self.futures.add(future)
        return future
