# -*- coding: utf-8 -*-

import www.orm
import asyncio
from www.models import User,Blog,Comment

orm = www.orm

async def test():
    await orm.create_pool(loop=loop,user='zbf',password='123456',db='awesome')
    u = User(name='test',email='516845590@qq.com',passwd='123456',image='about:blank')
    await u.save()


loop = asyncio.get_event_loop()
loop.run_until_complete(test())
loop.close()

#for x in test():
#    print(x)





