#datatime:2018/8/28
#封装数据库常用操作SELECT、INSERT、UPDATE和DELETE
import aiomysql,asyncio
import logging


#暂时不知道此函数有何意义，猜测是SQL语句必须带参数，防止注入 (''or 1=1;#)

def log(sql,args=()):
    logging.info('SQL:%s'%sql)

#数据库连接池
async def create_pool(loop,**kw):
    logging.info('create database connection pool...')
    global __pool
    __pool = await aiomysql.create_pool(
        host = kw.get('host','localhost'),
        port = kw.get('port',3306),
        user = kw['user'],
        password = kw['password'],
        db = kw['db'],
        charset = kw.get('charset','utf8'),
        autocommit = kw.get('autocommit',True),
        maxsize = kw.get('maxsize',10),
        minsize = kw.get('minsize',1),
        loop = loop
    )

#数据库查询函数select
async def select(sql,args,size=None):
    log(sql,args)
    global __pool
    with (await __pool) as conn:
        cur =await conn.cursor(aiomysql.DictCursor) #返回字典的游标
        await cur.execute(sql.replace('?','%s'),args or ())#替换占位符
        if size:
            rs = await cur.fetchmany(size)
        else:
            rs = await cur.fetchall()
        await cur.close()
        logging.info('rows returned:%s'%len(rs))
        return rs

#Insert, Update, Delete通用的操作，需要相同的参数并且返回一个整数表示影响的行数
# async  def execute(sql,args):
#     log(sql)
#     with (await __pool) as conn:
#         try:
#             cur = await conn.cursor() #创建游标
#             await cur.execute(sql.replace('?','%'),args) #执行sql语句
#             affected = cur.rowcount #影响的行数
#             await cur.close() #关闭连接
#         except BaseException as e: #抛出异常
#             raise
#         return affected

async def execute(sql,args,autocommit=True):
    log(sql)
    async with __pool.get() as conn:
        if not autocommit:
            await conn.begin()
        try:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql.replace('?','%s'),args)
                affected =cur.rowcount
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
    def __init__(self, name, column_type, primary_key, default):
        self.name = name
        self.column_type = column_type
        self.primary_key = primary_key
        self.default = default

    def __str__(self):
        return '<%s,%s:%s>' % (self.__class__.__name__, self.column_type, self.name)

# 映射varchar的StringField
class StringField(Field):
    def __init__(self, name=None, primary_key=False, default=None, dd1='varchar(100)'):
        super().__init__(name, dd1, primary_key, default)

class IntegerField(Field):
    def __init__(self, name=None, primary_key=False, default=0):
        super().__init__(name, 'bigint', primary_key, default)

class BooleanField(Field):
    def __init__(self, name=None, default=False):
        super().__init__(name, 'boolean', False, default)

class FloatField(Field):
    def __init__(self, name=None, primary_key=False, default=0.0):
        super().__init__(name, 'real', primary_key, default)

class TextField(Field):
    def __init__(self, name=None, default=None):
        super().__init__(name, 'text', False, default)


#通过MedolMetaclass将具体的子类映射信息读取出来
class ModelMetaclass(type):
    def __new__(cls, name, bases,attrs):
        #排除Model类本身
        if name =='Model':
            return type.__new__(cls,name,bases,attrs)
        #获取table名称
        tableName = attrs.get('__table__',None) or name
        logging.info('found model:%s(table:%s)'%(name,tableName))
        #获取所有的Field和主键名
        mappings = dict()
        fields = []
        primaryKey = None
        for k,v in attrs.items():
            if isinstance(v,Field):
                logging.info('found mapping:%s ==>%s'%(k,v))
                mappings[k] = v
                if v.primary_key:
                    #找到主键
                    if primaryKey:
                        raise RuntimeError('Duplicate primary key for field:%s'%k)
                    primaryKey = k
                else:
                    fields.append(k)
        if not primaryKey:
            raise RuntimeError('Primary key not found')
        for k in mappings.keys():
            attrs.pop(k)
        escaped_field = list(map(lambda f:'`%s`'%f,fields))
        attrs['__mappings__'] = mappings #保存属性和列的映射关系
        attrs['__table__'] = tableName
        attrs['__primary_key__'] = primaryKey
        attrs['__fields__'] = fields
        #构造默认的select、insert、delete、updateaaaa语句
        attrs['__select__'] = 'select `%s`,%s from `%s`'%(primaryKey,','.join(escaped_field),tableName)
        attrs['__insert__'] = 'insert into `%s` (%s,`%s`) values(%s)'%(tableName,','.join(escaped_field),primaryKey,create_args_string(len(escaped_field)+1))
        attrs['__update__'] = 'update `%s` set %s where `%s`=?'%(tableName,','.join(map(lambda f:'`%s`=?'%(mappings.get(f).name or f),fields)),primaryKey)
        attrs['__delete__'] = 'delete from `%s` where `%s`=?'%(tableName,primaryKey)
        return type.__new__(cls,name,bases,attrs)

#所有ORM映射的基类
class Model(dict,metaclass=ModelMetaclass):
    def __init__(self,**kw):
        super(Model,self).__init__(**kw)

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r" 'Model' object has no attribute '%s'"% key)

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
                logging.debug('using default value for %s: %s'%(key,str(value)))
                setattr(self,key,value)
        return value

    @classmethod
    async def findAll(cls,where=None,args=None,**kw):
        sql = [cls.__select__]
        if where:
            sql.append('where')
            sql.append(where)
        if args:
            args = []
        orderBy = kw.get('orderBy',None)
        if orderBy:
            sql.append('orderBy')
            sql.append(orderBy)
        limit = kw.get('limit',None)
        if limit is not None:
            sql.append('limit')
            if isinstance(limit,int):
                sql.append('?')
                args.append(limit)
            elif isinstance(limit,tuple) and len(limit)==2:
                sql.append('?,?')
                args.extend(limit)
            else:
                raise ValueError('Invalid limit value:%s'%str(limit))
        rs = await select(' '.join(sql),args)
        return [cls(**r) for r in rs]

    @classmethod
    async def findNumber(cls, selectField, where=None, args=None):
        ' find number by select and where. '
        sql = ['select %s _num_ from `%s`' % (selectField, cls.__table__)]
        if where:
            sql.append('where')
            sql.append(where)
        rs = await select(' '.join(sql), args, 1)
        if len(rs) == 0:
            return None
        return rs[0]['_num_']

    @classmethod
    async def find(cls,pk):
        #查询主键
        rs = await select('%s where `%s`=?'%(cls.__select__,cls.__primary_key__),[pk],1)
        if len(rs) == 0:
            return None
        return cls(**rs[0])

    async def save(self):
        #保存User实例
        args = list(map(self.getValueOrDefault,self.__fields__))
        args.append(self.getValueOrDefault(self.__primary_key__))
        rows = await execute(self.__insert__,args)
        if rows !=1:
            logging.info('failed to insert record:affected rows:%s'%rows)

    async def update(self):
        args = list(map(self.getValue, self.__fields__))
        args.append(self.getValue(self.__primary_key__))
        rows = await execute(self.__update__, args)
        if rows != 1:
            logging.warn('failed to update by primary key: affected rows: %s' % rows)

    async def remove(self):
        args = [self.getValue(self.__primary_key__)]
        rows = await execute(self.__delete__, args)
        if rows != 1:
            logging.warn('failed to remove by primary key: affected rows: %s' % rows)




