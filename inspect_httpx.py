import httpx, inspect

print('AsyncClient signature:', inspect.signature(httpx.AsyncClient))
print(httpx.AsyncClient.__init__.__doc__)
