# exfoliate
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) [![Python: v3.6](https://img.shields.io/pypi/pyversions/exfoliate.svg)](https://pypi.python.org/pypi/exfoliate)

Exfoliate is the asynchronous HTTP client for developers who prefer synchronous Python.  Enjoy the benefits of a scalable, asynchronous HTTP client without worrying about coroutines or event loops.

Exfoliate is the gentler, more Pythonic way to scrape the web.

# Example

The exfoliate client makes requests with the same call signature of methods on ```aiohttp.ClientSession``` and returns an ```concurrent.futures.Future``` instance.  The future instance resolves to an HTTP ```Response``` instance, which attempts to mimic the ```requests.Response``` class, or an exception if the request failed.  If something unexpected happens, you can retry the request with ```future.repeat()```.

Check it out:

```python
>>> import exfoliate
>>> urls = (
...     'https://github.com/requests/requests',
...     'https://github.com/aio-libs/aiohttp',
...     'https://github.com/ross/requests-futures',
...     'https://github.com/kennethreitz/grequests',
...     'https://github.com/brianjpetersen/exfoliate',
... )
>>> client = exfoliate.Client()
>>> futures = exfoliate.Futures([client.get(url) for url in urls])
>>> for future in futures:
...     response = future.response()
...     content_length = len(response.content)
...     print(content_length)
```

Compare to similar code written with aiohttp:

```python
>>> import asyncio
>>> import aiohttp
>>> urls = (
...     'https://github.com/requests/requests',
...     'https://github.com/aio-libs/aiohttp',
...     'https://github.com/ross/requests-futures',
...     'https://github.com/kennethreitz/grequests',
...     'https://github.com/brianjpetersen/exfoliate',
... )
>>> async def get_content_length(url, session):
...     async with session.get(url) as response:
...         content = await response.read()
...         return len(content)
>>> async def make_requests():
...     async with aiohttp.ClientSession() as session:
...         tasks = [asyncio.ensure_future(get_content_length(url, session)) for url in urls]
...         content_lengths = await asyncio.gather(*tasks)
...         for content_length in content_lengths:
...             print(content_length)
>>> loop = asyncio.get_event_loop()
>>> future = asyncio.ensure_future(make_requests())
>>> loop.run_until_complete(future)
```

# Motivation

What Python developer doesn't love [requests](https://github.com/requests/requests)?  Its beautiful API has saved an untold number of keystrokes and has rendered thumbing through documentation to accomplish something that should be **simple** a relic of the past.

Unfortunately, for all its many strengths, requests is synchronous.  This means that if you have a lot of requests to make, you have to make them sequentially instead of concurrently.  This can be **slow**.

There are several potential solutions to this problem:

* You can use requests within a ```ThreadPoolExecutor``` to achieve concurrency.  This approach retains the familar syntax of synchronous Python and the lovely requests API, and there is even a [library](https://github.com/ross/requests-futures) that wraps requests to make this approach seamless.  Unfortunately, Python threads are **heavy**: the OS reserves a separate stack for each thread, and on OSX and many flavors of Linux, each thread consumes 8MB of memory.  This can artificially limit concurrency if you have many requests to make.
* You can monkeypatch Python's networking libaries to use asynchronous primitives.  Kenneth Reitz has an asynchronous version of requests called [grequests](https://github.com/kennethreitz/grequests) which monkeypatches the standard library using gevent.  Opinions vary as to the wisdom of monkeypatching in Python, but using a library like grequests preserves a nice, familiar API while allowing a high degree of concurrency.
* You can use an asynchronous library instead of requests, such as Twisted, Tornado, or aiohttp.  This achieves high concurrency without the memory implications of thread pools or the hackiness of monkeypatching, but now you can't benefit from the beautiful Pythonic API for which requests is known.  Using these libraries often requires vebose boilerplate to set up and manage event loops and callback handlers.  In the case of aiohttp, it requires the developer to learn Python's new async/await syntax and semantics and be familiar with asyncio, which can be intimidating for a novice and confusing even for a [seasoned Pythonista](http://lucumr.pocoo.org/2016/10/30/i-dont-understand-asyncio/).

As a developer, you don't care about threads, event loops, coroutines, or asynchronous context managers.  As a developer, you don't want to have to reason about whether monkeypatching the standard library will break any of your existing code.  

As a developer, what you want is to make lots of requests quickly and concurrently with a readable, familar API.  That is the objective of the exfoliate library.

# How It Works

Under the hood, exfoliate is a thin abstraction over the comprehensive aiohttp client with all the asynchronous machinery hidden away in a thread that is spawned upon instantiating the Client.  If multiple clients are used, multiple independent threads are spawned, each with its own asyncio event loop and isolated ```aiohttp.ClientSession``` and ```aiohttp.TCPConnector``` instances by default.

Due to the fact that it is also running a synchronous thread, exfoliate suffers slightly degraded performance relative to pure aiohttp.  The [simple benchmark](./benchmark.py) included here attempts to quantify this degradation, which is generally found to be less than 10% in terms of runtime for making many of requests.  Of course, as with any benchmark, your mileage may vary, and if performance is critical, you should benchmark exfoliate using a workload representative of yours to assess its suitability for your needs.  In short: caveat emptor!

# Installing, Testing, and Benchmarking

To install exfoliate, visit your local neighborhood [cheeseshop](https://wiki.python.org/moin/CheeseShop):

```
$ pip install exfoliate
```

To run the tests, issue the following command:

```
$ python setup.py test
```

To run the benchmark, issue the following command:

```
$ python setup.py benchmark
```
