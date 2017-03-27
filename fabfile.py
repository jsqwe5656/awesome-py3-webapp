#!/usr/bin/env python
#-*- coding: utf-8 -*-

import os,re
from datetime import datetime

#导入fabric API
from fabric.api import *

#服务器登录用户名
env.user = 'zbf'
#sudo 用户为root
env.sudo_user = 'root'
#服务器地址
env.hosts = ['www.bfzhang.cn']

#服务器mysql 用户名与口令
db_user = 'zbf'
db_password = '123456'

