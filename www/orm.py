#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio,aiomysql
import logging; logging.basicConfig(level=logging.INFO)

def log(sql,atgs=()):
    logging.info('SQL %s' % sql)

#创建一个连接池
@asyncio.coroutine
def create_pool(loop,**kw):
    logging.info('create database connection pool..')
    global __pool
    #连接池由全局变量__pool存储，缺省情况下将编码设置为utf8，自动提交事务
    __pool = yield from aiomysql.create_pool(
        host=kw.get('host','localhost'),
        port=kw.get('port',3306),
        user=kw['user'],
        password=kw['password'],
        db=kw['db'],
        charset=kw.get('charset','utf8'),
        autocommit=kw.get('autocommit',True),
        maxsize=kw.get('maxsize',10),
        minsize=kw.get('minsize',1),
        loop=loop
    )

#select 执行函数
@asyncio.coroutine
def selcet(sql,args,size=None):
    log(sql,args)
    global __pool
    with (yield from __pool) as conn:
        cur = yield from conn.cursor(aiomysql.DictCursor)
        #SQL语句的占位符是?，而MySQL的占位符是%s，select()函数在内部自动替换。
        yield from cur.execute(sql.replace('?','%s'),args or ())
        #如果传入size参数，就通过fetchmany()获取最多指定数量的记录，否则，通过fetchall()获取所有记录。
        if size:
            rs = yield from cur.fetchmang(size)
        else:
            rs = yield from cur.fetchall()
        yield from cur.close()
        logging.info('rows returned : %s' % len(rs))
        return rs

#编写增删改的函数
@asyncio.coroutine
def execute(sql,args):
    log(sql)
    with (yield from __pool) as conn:
        try:
            cur = yield from conn.cursor()
            yield from cur.execute(sql.replace('?',"%s"),args)
            #返回影响结果数
            affected = cur.rowcount
            yield from cur.close()
        except BaseException as e:
            raise
        return affected

class ModelMetaclass(type):
    pass

#ORM映射的基类
class Model(dict,metaclass=ModelMetaclass):
    def __init__(self,**kw):
        super(Model,self).__init__(**kw)

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Model' object has no attribut '%s',by zbf" %key)

    def __setattr__(self, key, value):
        self[key] = value

    def getVaules(self,key):
        return getattr(self,key,None)

    def getValueOrDefault(self,key):
        value = getattr(self,key,None)
        if value is None:
            field = self.__mappings__[key]
            if field.default is not None:
                value = field.default() if callable(field.default) else field.default
                logging.debug('using default balue for %s:%s' % (key,str(value)))
                setattr(self,key,value)
        return value









