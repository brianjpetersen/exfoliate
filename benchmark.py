""" A simple benchmark of exfoliate vs aiohttp.

Compares the performance of aiohttp to exfoliate for making 1000 requests to an aiohttp server that 
is spawned automatically by the script.  The server returns random content with random size between 
0 bytes and 1 MB.

Of course, as with any benchmark, your mileage may vary, and if performance is critical, you should 
benchmark exfoliate using a workload representative of yours to assess its suitability for your 
needs.
"""
import multiprocessing
import requests
import timeit


def wait_for_server_to_start(url):
    while True:
        try:
            response = requests.get('http://127.0.0.1:8080/')
            response.raise_for_status()
        except:
            pass
        else:
            break


def run_server():
    
    import aiohttp.web
    import asyncio
    import random
    import os
    
    async def root(request):
        content_length = random.randint(0, 1000000) # between 0 bytes and 1 MB
        content = os.urandom(content_length)
        response = aiohttp.web.Response(body=content)
        return response
        
    async def set_seed(request):
        seed = request.match_info.get('seed')
        random.seed(seed)
        response = aiohttp.web.Response()
        return response
    
    app = aiohttp.web.Application()
    app.router.add_get('/', root)
    app.router.add_put('/seed/{seed}', set_seed)
    def noop_print(*args, **kwargs): pass
    # runs at http://127.0.0.1:8080/
    aiohttp.web.run_app(app, print=noop_print)


server_process = multiprocessing.Process(target=run_server)
server_process.daemon = True
server_process.start()
wait_for_server_to_start('http://127.0.0.1:8080/')


setup = """
import aiohttp
import asyncio
import requests

NUMBER_OF_REQUESTS = 1000

requests.put('http://127.0.0.1:8080/seed/1')
"""

execute = """
async def make_request(url, session):
    async with session.get(url) as response:
        content = await response.read()
        return response.status

async def make_requests():
    async with aiohttp.ClientSession() as session:
        tasks = [
            asyncio.ensure_future(
                make_request('http://127.0.0.1:8080/', session)
            ) for _ in range(NUMBER_OF_REQUESTS)
        ]
        status_codes = await asyncio.gather(*tasks)
        for status_code in status_codes:
            assert status_code == 200

loop = asyncio.get_event_loop()
future = asyncio.ensure_future(make_requests())
loop.run_until_complete(future)
"""

aiohttp_time = timeit.timeit(execute, setup=setup, number=3)
print('aiohttp: {} seconds'.format(round(aiohttp_time, 1)))


setup = """
import exfoliate
import requests

requests.put('http://127.0.0.1:8080/seed/1')

NUMBER_OF_REQUESTS = 1000
"""

execute = """
client = exfoliate.Client()

for _ in range(NUMBER_OF_REQUESTS):
    client.get('http://127.0.0.1:8080/')

for future in client.futures:
    response = future.result()
    assert response.status_code == 200
"""

exfoliate_time = timeit.timeit(execute, setup=setup, number=3)
print('exfoliate: {} seconds'.format(round(exfoliate_time, 1)))
