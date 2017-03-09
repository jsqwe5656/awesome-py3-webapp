#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import aiomysql
import logging; logging.basicConfig(level=logging.INFO)

#输出方法
def log(sql,args=()):
    logging.info('SQL %s,args=%s' % (sql,args))

#创建一个连接池
async def create_pool(loop,**kw):
    logging.info('create database connection pool..')
    global __pool
    #连接池由全局变量__pool存储，缺省情况下将编码设置为utf8，自动提交事务
    __pool = await aiomysql.create_pool(
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
async def selcet(sql,args,size=None):
    log(sql,args)
    global __pool
    async with __pool.get() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            #SQL语句的占位符是?，而MySQL的占位符是%s，select()函数在内部自动替换。
            await cur.execute(sql.replace('?','%s'),args or ())
            #如果传入size参数，就通过fetchmany()获取最多指定数量的记录，否则，通过fetchall()获取所有记录。
            if size:
                rs = await cur.fetchmang(size)
            else:
                rs = await cur.fetchall()
        logging.info('rows returned : %s' % len(rs))
        return rs

#编写增删改的函数
async def execute(sql,args,autocommit=True):
    log(sql)
    async with __pool.get() as conn:
        if not autocommit:
            await conn.begin()
        try:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql.replace('?',"%s"),args)
                #返回影响结果数
                affected = cur.rowcount
            if not autocommit:
                await conn.commit()
        except BaseException as e:
            if not autocommit:
                await conn.rollback()
            raise
        return affected

def create_args_string(num):
    L = []
    for n in range(num):
        L.append('?')
    return ','.join(L)

class Field(object):
    def __init__(self,name,column_type,primary_key,default):
        self.name = name
        self.column_type = column_type
        self.primary_key = primary_key
        self.default = default

    def __str__(self):
        return '<%s,%s,%s>' %(self.__class__.__name__,self.column_type,self.name)

#映射varchar
class StringField(Field):
    def __init__(self,name=None,primary_key=False,default=None,ddl='varchar(100)'):
        super().__init__(name,ddl,primary_key,default)

class BooleanField(Field):
    def __init__(self,name=None,default=False):
        super().__init__(name,'boolean',False,default)

class IntegerField(Field):
    def __init__(self,name=None,primary_key=False,default=0):
        super().__init__(name,'bigint',primary_key,default)

class FloatField(Field):
    def __init__(self,name=None,primary_key=False,default=0.0):
        super().__init__(name,'real',primary_key,default)

class TextField(Field):
    def __init__(self,name=None,defult=None):
        super().__init__(name,'text',False,defult)

#读取具体子类的映射信息
class ModelMetaclass(type):
    def __new__(cls, name,bases,attrs):
        #排除model类本身
        if name=='Model':
            return type.__new__(cls,name,bases,attrs)
        #获取table名称
        tableName = attrs.get('__table__',None) or name
        logging.info('found model: %s (table: %s)' %(name,tableName))
        #获取所有的field的主键名
        mappings = dict()
        fields=[]
        primaryKey = None
        for k,v in attrs.items():
            if isinstance(v,Field):
                logging.info('  found mapping: %s ==> %s' %(k,v))
                mappings[k] =v
                if v.primary_key:
                    #找到主键
                    if primaryKey:
                        raise RuntimeError('Duplicate primary key for field: %s' %k)
                    primaryKey = k
                else:
                    fields.append(k)
        if not primaryKey:
            raise RuntimeError('Primary key not found.')
        for k in mappings.keys():
            attrs.pop(k)
        escaped_fields = list(map(lambda f: '`%s`' %f,fields))
        attrs['__mappings__'] = mappings        #保留属性和列的映射关系
        attrs['__table__'] = tableName
        attrs['__primart_key__'] = primaryKey   #主键属性名
        attrs['__fields__'] = fields            #出主键外的属性名
        #构造默认的select,insert,update与delete语句
        attrs['__select__'] = 'select `%s`,%s from `%s`' % (primaryKey,','.join(escaped_fields),tableName)
        attrs['__insert__'] = 'insert into `%s` (%s,`%s`) values (%s)' %(tableName,','.join(escaped_fields),primaryKey,create_args_string(len(escaped_fields) + 1))
        attrs['__update__'] = 'update `%s` set %s where `%s`=?' % (tableName, ', '.join(map(lambda f: '`%s`=?' % (mappings.get(f).name or f), fields)), primaryKey)
        attrs['__delete__'] = 'delete from `%s` where `%s`=?'%(tableName,primaryKey)
        return type.__new__(cls,name,bases,attrs)

#ORM映射的基类
class Model(dict,metaclass=ModelMetaclass):
    def __init__(self,**kw):
        super(Model,self).__init__(**kw)

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Model' object has no attribute '%s',by zbf" %key)

    def __setattr__(self, key, value):
        self[key] = value

    def getVaule(self,key):
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

    @classmethod
    async def find(cls,pk):
        ' find object by primary key. '
        rs = await  selcet('%s where `%s`=?' %(cls.__select__,cls.__primary_key__),[pk],1)
        if len(rs) == 0:
            return None
        return cls(**rs[0])

    async def save(self):
        args = list(map(self.getValueOrDefault,self.__fields__))
        args.append(self.getValueOrDefault(self.__primary_key__))
        rows = await execute(self.__insert__,args)
        if rows !=1:
            logging.warning('failed to insert record:affeoted rows:%s' %rows)

    async def update(self):
        args = list(map(self.getValue,self.__fields__))
        args.append(self.getVaule(self.__primary_key__))
        rows = await execute(self.__update__,args)
        if rows != 1:
            logging.warning('failed to update bu primary key : affected rows: %s' % rows)

    async def remove(self):
        args = [self.getVaule(self.__primary_key__)]
        rows = await execute(self.__delete__,args)
        if rows !=1:
            logging.warning('failed to remove by primary key: affected rows:%s' % rows)
