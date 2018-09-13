#datatime:2018/8/31
#配置文件
#Web App在运行时都需要读取配置文件，比如数据库的用户名、口令等，
# 在不同的环境中运行时，Web App可以通过读取不同的配置文件来获得正确的配置
#开发环境标准配置

configs = {
    'debug':True,
    'db':{
        'host':'127.0.0.1',
        'port':3306,
        'user':'root',
        'password':'123456',
        'database':'app'
    },
    'session':{
        'secret':'AweSome'
    }
}
