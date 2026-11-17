"""Tiny stdlib helper so the instructor demos need no host dependencies."""
import json
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

def request(method,url,data=None,expected=(200,),retries=0):
    payload=json.dumps(data).encode() if data is not None else None
    req=Request(url,data=payload,method=method,headers={"Content-Type":"application/json"})
    for attempt in range(retries+1):
        try:
            with urlopen(req,timeout=5) as response:
                status=response.status;body=json.loads(response.read())
        except HTTPError as error:
            status=error.code;body=json.loads(error.read())
        except URLError:
            if attempt==retries: raise RuntimeError(f"Service not ready at {url}; run 'make up' first")
            time.sleep(1)
            continue
        if status not in expected:
            if attempt < retries:
                time.sleep(1)
                continue
            raise RuntimeError(f"Unexpected status {status}: {body}")
        return status,body
