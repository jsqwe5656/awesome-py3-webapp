#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import aiomysql,asyncio,sys
import logging; logging.basicConfig(level=logging.INFO)

#输出方法
def log(sql,args=()):
    logging.info('SQL %s,args=%s' % (sql,args))

#创建一个连接池,这里的二参**kw是一个dict
async def create_pool(loop,**kw):
    logging.info('create database connection pool..')
    global __pool
    #连接池由全局变量__pool存储，缺省情况下将编码设置为utf8，自动提交事务
    __pool = await aiomysql.create_pool(
        host=kw.get('host','localhost'),
        port=kw.get('port',3306),
        user=kw['user'],
        password=kw['password'],
        db=kw['database'],
        charset=kw.get('charset','utf8'),
        autocommit=kw.get('autocommit',True),           #设置自动提交
        maxsize=kw.get('maxsize',10),
        minsize=kw.get('minsize',1),
        loop=loop
    )

#关闭进程池方法
async def destroy_pool():
    global __pool
    if __pool is not None:
        __pool.close()              #关闭进程池
        await __pool.wait_closed()  #等待进程池关闭后关闭所有连接


#select 执行函数
async def selcet(sql,args,size=None):
    log(sql,args)
    global __pool
    #建立连接
    async with __pool.get() as conn:
        #建立游标
        async with conn.cursor(aiomysql.DictCursor) as cur:
            #SQL语句的占位符是?，而MySQL的占位符是%s，select()函数在内部自动替换。
            await cur.execute(sql.replace('?','%s'),args or ())
            #如果传入size参数，就通过fetchmany()获取最多指定数量的记录，否则，通过fetchall()获取所有记录。
            if size:
                rs = await cur.fetchmany(size)
            else:
                rs = await cur.fetchall()
        logging.info('rows returned : %s' % len(rs))
        #返回查询结果list元素是tuple
        return rs

#编写增删改的函数,默认自动提交
async def execute(sql,args,autocommit=True):
    log(sql,args)
    #建立连接
    async with __pool.get() as conn:
        if not autocommit:
            await conn.begin()
        try:
            #建立游标
            async with conn.cursor(aiomysql.DictCursor) as cur:
                #去除sql中的占位符再执行
                await cur.execute(sql.replace('?',"%s"),args)
                #返回影响结果数
                affected = cur.rowcount
            if not autocommit:
                await conn.commit()
        except BaseException as e:
            if not autocommit:
                await conn.rollback()
            raise
        finally:
            conn.close()
        return affected

#把查询字段计数并转化成sql识别的?
#比如 insert into 'tablename'('arg1','arg2'..) values(?,?,..)
def create_args_string(num):
    L = []
    for n in range(num):
        L.append('?')
    return ','.join(L)

#负责保存（数据库）表的字段名和字段类型
#英文字义：场，域
class Field(object):
    #表的字段包含名字、类型、主键和默认值
    def __init__(self,name,column_type,primary_key,default):
        self.name = name
        self.column_type = column_type
        self.primary_key = primary_key
        self.default = default

    #返回标的名字、字段类型和字段名
    def __str__(self):
        return '<%s,%s,%s>' %(self.__class__.__name__,self.column_type,self.name)

#映射varchar
class StringField(Field):
    def __init__(self,name=None,primary_key=False,default=None,ddl='varchar(100)'):
        super().__init__(name,ddl,primary_key,default)

#布尔类型不能作为主键
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

#为数据库表映射成封装类做准备的类
class ModelMetaclass(type):
    #控制__init__的执行
    #bases:代表继承父类的集合
    #attrs:类的方法集合
    def __new__(cls, name,bases,attrs):
        #排除model类本身
        if name=='Model':
            return type.__new__(cls,name,bases,attrs)
        #获取table名称，不存在则返回name
        tableName = attrs.get('__table__',None) or name
        logging.info('found model: %s (table: %s)' %(name,tableName))
        #获取所有的field的主键名
        mappings = dict()
        #保存除主键外的属性名
        fields=[]
        primaryKey = None
        for k,v in attrs.items():
            if isinstance(v,Field):
                logging.info('  found mapping: %s ==> %s' %(k,v))
                mappings[k] =v
                if v.primary_key:
                    #找到主键 并且在第一次找到主键时赋值，以后再出现主键就会引发错误
                    if primaryKey:
                        raise BaseException('Duplicate primary key for field: %s' %k)
                    primaryKey = k
                else:
                    fields.append(k)
        #表中必须且只能有一个主键
        if not primaryKey:
            raise BaseException('Primary key not found.')
        #从类属性中删除Field属性
        for k in mappings.keys():
            attrs.pop(k)
        #主键属性保存为''单引号形式，其余字段变成``反引号形式
        escaped_fields = list(map(lambda f: '`%s`' %f,fields))
        attrs['__mappings__'] = mappings        #保留属性和列的映射关系
        attrs['__table__'] = tableName
        attrs['__primary_key__'] = primaryKey   #主键属性名
        attrs['__fields__'] = fields            #出主键外的属性名
        #构造默认的select,insert,update与delete语句
        attrs['__select__'] = 'select `%s`,%s from `%s`' % (primaryKey,','.join(escaped_fields),tableName)
        attrs['__insert__'] = 'insert into `%s` (%s,`%s`) values (%s)' %(tableName,','.join(escaped_fields),primaryKey,create_args_string(len(escaped_fields) + 1))
        attrs['__update__'] = 'update `%s` set %s where `%s`=?' % (tableName, ', '.join(map(lambda f: '`%s`=?' % (mappings.get(f).name or f), fields)), primaryKey)
        attrs['__delete__'] = 'delete from `%s` where `%s`=?'%(tableName,primaryKey)
        return type.__new__(cls,name,bases,attrs)

#ORM映射的基类
#Model类的任意子类可以映射一个数据库表，可以看做对所有数据库表操作的基本定义的映射
#基于字典查询形式从dict集成拥有字典所有空能，并且实现特殊方法__getattr__和__setattr__，实现操作属性
#实现了数据库操作的所有方法，所有继承自Model的类也都具有这些方法
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

    def getValue(self,key):
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
    async def findAll(cls,where=None,args=None,**kw):
        'find objects by where clause'
        sql = [cls.__select__]
        #指定查询条件
        if where:
            #加入where关键字
            sql.append('where')
            #加入where参数
            sql.append(where)
        if args is None:
            args = []
        orderBy = kw.get('orderBy',None)
        if orderBy:
            sql.append('order by')
            sql.append(orderBy)
        limit = kw.get('limit',None)
        if limit is not None:
            sql.append('limit')
            if isinstance(limit,int):
                sql.append('?')
                args.append(limit)
            elif isinstance(limit,tuple) and len(limit) ==2 :
                sql.append('?,?')
                args.extend(limit)
            else:
                raise ValueError('Invalid limit value: %s' % str(limit))
        rs = await selcet(' '.join(sql),args)
        return [cls(**r) for r in rs]

    @classmethod
    async def findNumber(cls,selectField,where=None,args=None):
        'find number bu select and where'
        sql = ['select %s _num_ from `%s`'%(selectField,cls.__table__)]
        if where:
            sql.append('where')
            sql.append(where)
        rs = await selcet(' '.join(sql),args,1)
        if len(rs) ==0:
            return None
        return rs[0]['_num_']


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
        args.append(self.getValue(self.__primary_key__))
        rows = await execute(self.__update__,args)
        if rows != 1:
            logging.warning('failed to update bu primary key : affected rows: %s' % rows)

    async def remove(self):
        args = [self.getVaule(self.__primary_key__)]
        rows = await execute(self.__delete__,args)
        if rows !=1:
            logging.warning('failed to remove by primary key: affected rows:%s' % rows)
