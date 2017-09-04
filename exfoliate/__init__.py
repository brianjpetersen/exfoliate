import os
from . import exfoliate


__where__ = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(__where__, 'VERSION.txt'), 'rb') as f:
    __version__ = f.read().decode('ascii').strip()
    
    
TCPConnector = exfoliate.TCPConnector
CookieJar = exfoliate.CookieJar
DummyCookieJar = exfoliate.DummyCookieJar
Futures = exfoliate.Futures
Client = exfoliate.Client
RequestException = exfoliate.RequestException
HTTPError = exfoliate.HTTPError
