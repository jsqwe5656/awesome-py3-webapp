#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import hashlib
import json
import logging
import re
import time

from aiohttp import web

import markdown2
from apis import APIError, APIPermissionError, APIValueErrpr, Page
from config import configs
from models import User, Comment, Blog, next_id
from webutlis import get, post

COOKIE_NAME = 'awesession'
_COOKIE_KEY = configs.session.secret


def get_page_index(page_str):
    p = 1
    try:
        p = int(page_str)
    except ValueError as e:
        pass
    if p < 1:
        p = 1
    return p


def user2cookie(user, max_age):
    # 过期时间
    expires = str(int(time.time()) + max_age)
    s = '%s-%s-%s-%s' % (user.id, user.passwd, expires, _COOKIE_KEY)
    L = [user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]
    return '-'.join(L)


async def cookie2user(cookie_str):
    if not cookie_str:
        return None
    try:
        L = cookie_str.split('-')
        if len(L) != 3:
            return None
        uid, expires, sha1 = L
        if int(expires) < time.time():
            return None
        user = await User.find(uid)
        if user is None:
            return None
        s = '%s-%s-%s-%s' % (uid, user.passwd, expires, _COOKIE_KEY)
        if sha1 != hashlib.sha1(s.encode('utf-8')).hexdigest():
            logging.info('invalid sha1')
            return None
        user.passwd = '*******'
        return user
    except Exception as e:
        logging.exception(e)
        return None


@post('/api/authenticate')
async def authenticate(*, email, passwd):
    if not email:
        raise APIValueErrpr('email', 'Invalid email')
    if not passwd:
        raise APIValueErrpr('passwd', 'Invalid password')
    users = await User.findAll('email=?', [email])
    if len(users) == 0:
        raise APIValueErrpr('email', 'Email not exist')
    user = users[0]
    # 检查密码
    sha1 = hashlib.sha1()
    sha1.update(user.id.encode('utf-8'))
    sha1.update(b':')
    sha1.update(passwd.encode('utf-8'))
    if user.passwd != sha1.hexdigest():
        raise APIValueErrpr('passwd', 'Invalid password')
    # 验证通过赋值cookie
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passwd = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    logging.info(r)
    return r


# 检查是否为admin
def check_admin(request):
    print(request.__user__,request.__user__.admin)
    if request.__user__ is None or not request.__user__.admin:
        raise APIPermissionError()


@get('/')
async def index(*,page=1):
    page_index = get_page_index(page)
    num = await Blog.findNumber('count(id)')
    page = Page(num)
    if num ==0:
        blogs=[]
    else:
        blogs = await Blog.findAll(orderBy='created_at desc',limit=(page.offset,page.limit))
    return {
        '__template__': 'blogs.html',
        'blogs': blogs,
        'page': page
    }

@get('/register')
def api_register():
    return {
        '__template__': 'register.html'
    }


@get('/signin')
def signin():
    return {
        '__template__': 'signin.html'
    }


@get('/signout')
def singout(request):
    referer = request.headers.get('Referer')
    r = web.HTTPFound(referer or '/')
    r.set_cookie(COOKIE_NAME, '-deleted-', max_age=0, httponly=True)
    logging.info('user had signed out')
    return r

def text2html(text):
    lines = map(lambda s: '<p>%s</p>' % s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'),
                filter(lambda s: s.strip() != '', text.split('\n')))
    return ''.join(lines)

@get('/manage/')
def manage():
    return 'redirect:/manage/comments'

@get('/manage/comments')
def manage_comments(*,page='1'):
    return {
        '__template__' : 'manage_comments.html',
        'page_index':get_page_index(page)
    }

@get('/manage/blogs/create')
def manage_create_blog():
    return {
        '__template__': 'manage_blog_edit.html',
        'id': '',
        'action': '/api/blogs'
    }

@get('/manage/blogs/edit')
def manage_edit_blog(*,id):
    return {
        '__template__':'manage_blog_edit.html',
        'id':id,
        'action':'/api/blogs/%s' %id
    }

@get('/manage/blogs')
def manage_blogs(*,page='1'):
    return {
        '__template__':'manage_blogs.html',
        'page_index':get_page_index(page)
    }

@get('/manage/users')
def manage_users(*,page='1'):
    return {
        '__template__':'manage_users.html',
        'page_index':get_page_index(page)
    }

@get('/blog/{id}')
async def get_blog(id,request):
    blog = await Blog.find(id)
    comments = await Comment.findAll('blog_id=?', [id], orderBy='created_at desc')
    for c in comments:
        c.html_content = text2html(c.content)
    blog.html_content = markdown2.markdown(blog.content)
    return {
        '__template__': 'blog.html',
        'blog': blog,
        'comments': comments,
        '__user__':request.__user__
    }

@get('/api/blogs')
async def api_blogs(*,page='1'):
    page_index = get_page_index(page)
    num = await Blog.findNumber('count(id)')
    p = Page(num,page_index)
    if num ==0:
        return dict(page=p,blogs=())
    blogs = await Blog.findAll(orderBy='created_at desc',limit=(p.offset,p.limit))
    return dict(page=p,blogs=blogs)

@post('/api/blogs')
async def api_create_blogs(request, *, name, summary, content):
    check_admin(request)
    if not name or not name.strip():
        raise APIValueErrpr('name', 'name is not be empty')
    if not summary or not summary.strip():
        raise APIValueErrpr('summary', 'summary is not be empty')
    if not content or not content.strip():
        raise APIValueErrpr('content', 'content is not be empty')
    user = request.__user__
    blog = Blog(user_id=user.id, user_image=user.image, user_name=user.name, summary=summary.strip(),
                content=content.strip(), name=name.strip())
    await blog.save()
    return blog

@post('/api/blogs/{id}')
async def api_update_blog(id,request,*,name,summary,content):
    check_admin(request)
    blog = await Blog.find(id)
    if not name or not name.strip():
        raise APIValueErrpr('name','name cannot be cmpty')
    if not summary or not summary.strip():
        raise APIValueErrpr('summary','summary cannot be cmpty')
    if not content or not content.strip():
        raise APIValueErrpr('content','content cannot be cmpty')
    blog.name = name.strip()
    blog.summary = summary.strip()
    blog.content = content.strip()
    await blog.update()
    return blog

@post('/api/blogs/{id}/delete')
async def api_delete_blog(request,*,id):
    check_admin(request)
    blog = await Blog.find(id)
    await blog.remove()
    return dict(id=id)

@get('/api/blogs/{id}')
async def api_get_blog(*, id):
    blog = await Blog.find(id)
    return blog

@get('/api/comments')
async def api_comments(*, page='1'):
    page_index = get_page_index(page)
    num = await Comment.findNumber('count(id)')
    p = Page(num,page_index)
    if num == 0:
        return dict(page=p,comment=())
    comments = await Comment.findAll(orderBy='created_at desc',limit=(p.offset,p.limit))
    return dict(page=p,comments=comments)

@post('/api/blogs/{id}/comments')
async def api_create_comment(id,request,*,content):
    user = request.__user__
    if user is None:
        raise APIPermissionError('Please signin first')
    if not content or not content.strip():
        raise APIValueErrpr('content')
    blog = await Blog.find(id)
    if blog is None:
        raise APIPermissionError('blog')
    comment = Comment(blog_id=blog.id,user_id=user.id,user_name=user.name,user_image=user.image,content=content.strip())
    await comment.save()
    return comment

@post('/api/blogs/{id}/delete')
async def api_delete_comment(id,request):
    check_admin(request)
    c = await Comment.find(id)
    if c is None:
        raise APIPermissionError('comment')
    await c.remove()
    return dict(id=id)

_RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_SHA1 = re.compile(r'^[0-9a-f]{40}$')

@get('/api/users')
async def api_get_users(*,page='1'):
    page_index = get_page_index(page)
    num = await User.findNumber('count(id)')
    p = Page(num,page_index)
    if num ==0:
        return dict(page=p,users=())
    users = await User.findAll(orderBy='created_at desc',limit=(p.offset,p.limit))
    for u in users:
        u.passwd = '******'
    return dict(page=p,users=users)

@post('/api/users')
async def api_register_users(*, email, name, passwd):
    if not name or not name.strip():
        raise APIValueErrpr('name')
    if not email or not _RE_EMAIL.match(email):
        raise APIValueErrpr('email')
    if not passwd or not _RE_SHA1.match(passwd):
        raise APIValueErrpr('passwd')
    users = await User.findAll('email=?', [email])
    if len(users) > 0:
        raise APIError('register:failed', 'email', 'Email is already in use')
    uid = next_id()
    sha1_passwd = '%s:%s' % (uid, passwd)
    user = User(id=uid, name=name.strip(), email=email,
                passwd=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(),
                image='http://www.gravatar.com/avatar/%s?d=mm&s=120' % hashlib.md5(email.encode('utf-8')).hexdigest())
    await user.save()
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passwd = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r

@get('/api/test')
def api_test_json():
    return json.dumps(dict(name='zbf',age='23',content='zbf is the best')).encode('utf-8')