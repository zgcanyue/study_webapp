#app骨架，datatime:2018/8/27
import logging;logging.basicConfig(level=logging.INFO)
import asyncio,os,json,time
from datetime import datetime
from aiohttp import web

def index(request):
    return web.Response(body=b'<h1>Simple App<h1>',content_type='text/html')

async def init(loop):
    app = web.Application()
    app.router.add_route('GET','/',index)
    srv = await loop.create_server(app._make_handler(),'127.0.0.1',8000)
    logging.info('server started at http://127.0.0.1:8000')
    return srv
loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()