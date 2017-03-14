#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from www.webutlis import get,post
from aiohttp import web


@get('/blog/{id}')
def get_blog(id):
    pass


@get('/api/comments')
def api_comments(*, page='1'):
    pass





