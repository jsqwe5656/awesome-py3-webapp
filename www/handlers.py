#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re, time, json, logging, hashlib, base64, asyncio
from www.webutlis import get, post
from aiohttp import web
from www.models import User, Comment, Blog, next_id
from www.apis import APIError,APIPermissionError,APIValueErrpr
from conf.config import configs

COOKIE_NAME = 'awesession'
_COOKIE_KEY = configs.session.secret

def user2cookie(user,max_age):
    #过期时间
    expires = str(int(time.time()) + max_age)
    s = '%s-%s-%s-%s'%(user.id,user.passwd,expires,_COOKIE_KEY)
    L = [user.id,expires,hashlib.sha1(s.encode('utf-8')).haxdigest()]
    return '-'.join(L)

async def cookie2user(cookie_str):
    if not cookie_str:
        return None
    try:
        L = cookie_str.split('-')
        if len(L) !=3:
            return None
        uid,expires,sha1 = L
        if int(expires) < time.time():
            return None
        user = await User.find(uid)
        if user is None:
            return None
        s ='%s-%s-%s-%s' %(uid,user.passwd,expires,_COOKIE_KEY)
        if sha1 != hashlib.sha1(s.encode('utf-8')).hexdigest():
            logging.info('invalid sha1')
            return None
        user.passwd = '*******'
        return user
    except Exception as e:
        logging.exception(e)
        return None

@post('/api/authenticate')
async def authenticate(*,email,passwd):
    if not email:
        raise APIValueErrpr('email','Invalid email')
    if not passwd:
        raise APIValueErrpr('passwd','Invalid password')
    user = await U

@get('/blog/{id}')
def get_blog(id):
    pass


@get('/api/comments')
def api_comments(*, page='1'):
    pass

@get('/register')
def api_register():
    return {
        '__template__':'register.html'
    }


@get('/')
async def index(request):
    summary = 'Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.'
    blogs = [
        Blog(id='1', name='Test Blog', summary=summary, created_at=time.time() - 120),
        Blog(id='2', name='Something New', summary=summary, created_at=time.time() - 3600),
        Blog(id='3', name='Learn Swift', summary=summary, created_at=time.time() - 7200)
    ]
    return {
        '__template__': 'blogs.html',
        'blogs': blogs
    }

_RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_SHA1 = re.compile(r'^[0-9a-f]{40}$')

@get('/api/users')
async def api_get_users(*,email,name,passwd):
    if not name or not name.strip():
        raise APIValueErrpr('name')
    if not email or not _RE_EMAIL.match(email):
        raise APIValueErrpr('email')
    if not passwd or not _RE_SHA1.match(passwd):
        raise APIValueErrpr('passwd')
    users = await User.findAll('email=?',[email])
    if len(users)>0:
        raise APIError('register:failed','email','Email is already in use')
    uid = next_id()
    sha1_passwd = '%s:%s' %(uid,passwd)
    user = User(id=uid,name=name.strip(),email=email,
                passwd=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(),
                image='http://www.gravatar.com/avatar/%s?d=mm&s=120' %hashlib.md5(email.encode('utf-8')).hexdigest())
    await user.save()
    r = web.Response()
    r.set_cookie(COOKIE_NAME,user2cookie(user,86400),max_age=86400,httponly=True)
    user.passwd = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user,ensure_ascii=False).encode('utf-8')
    return r




