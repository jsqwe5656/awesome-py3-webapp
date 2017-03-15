#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re,time,json,logging,hashlib,base64,asyncio
from www.webutlis import get,post
from aiohttp import web
from www.models import User,Comment,Blog,next_id

@get('/blog/{id}')
def get_blog(id):
    pass


@get('/api/comments')
def api_comments(*, page='1'):
    pass

@get('/')
async def index(request):
    users = await User.findAll()
    return {
        '__template__':'test.html',
        'users':users
    }





