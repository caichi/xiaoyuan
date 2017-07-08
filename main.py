#! /usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
import time
from datetime import datetime
import json
import math
import logging
import logging.handlers
import thread
from flask import Flask, request, session, g, redirect, url_for, abort, \
     render_template, flash, json, make_response
import MySQLdb
import urlparse
import base64
import re
import config
app = Flask(__name__)
# Load default config and override config from an environment variable

app.config.from_envvar('FLASKR_SETTINGS', silent = True)

def GetLogger(logName, logLevel = 'INFO'):
    fmt = '[%(asctime)s]\t[%(levelname)s]\t[%(thread)d]\t[%(pathname)s:%(lineno)d]\t%(message)s' 
    #set log config here when you want
    handler = logging.handlers.RotatingFileHandler(logName, maxBytes = 1024 * 1024 * 100, backupCount = 50) 
    formatter = logging.Formatter(fmt)
    handler.setFormatter(formatter)   
    logger = logging.getLogger()   
    logger.addHandler(handler)          
    if logLevel == 'DEBUG':
        logger.setLevel(logging.DEBUG)
    elif logLevel == 'WARNING':
        logLevel.setLevel(logging.WARNING)
    else:
        logger.setLevel(logging.INFO)
    return logger


def InitLog(logName = 'main.log'):
    fmt = '[%(asctime)s]\t[%(levelname)s]\t[%(thread)d]\t[%(pathname)s:%(lineno)d]\t%(message)s' 
    #set log config here when you want
    handler = logging.handlers.RotatingFileHandler(logName, maxBytes = 1024 * 1024 * 100, backupCount = 50) 
    formatter = logging.Formatter(fmt)
    handler.setFormatter(formatter)   
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('server is running...')

InitLog()

@app.before_request
def Prepare():
    pass

def ConnectDB():
    return MySQLdb.connect(config.DB_HOST, config.DB_USER, config.DB_PASSWD, config.DB_NAME, config.DB_PORT)

def get_user_id_by_name(nick_name):
    db = ConnectDB()
    try:
        cur = db.cursor()
        sql = "select uid from user where nick_name = %s" 
        cur.execute(sql, (nick_name,))
        return str(cur.fetchone()[0])
    except Exception, e:
        app.logger.exception('get_user_id_by_name: %s' % str(e))
        raise
    finally:
        db.close()

# create_user
@app.route('/users', methods = ['POST'])
def create_user():
    app.logger.info('create user')
    try:
        # "content-type: application/json" is required.
        if not request.is_json:
            return make_response('request data must be json-formatted.', 400)

        d_map = None
        try:
            d_map = request.get_json(force = True)
        except Exception, e:
            app.logger.exception('create user fail: %s' % str(e))
            return make_response('fail to decode request data', 400)
        
        if 0 == len(d_map):
            return make_response('request data must not be empty.', 400)
           
        if 'NickName' not in d_map or 0 == len(d_map['NickName']):
            return make_response('nick name must be included in request data.', 400)
        
        nick_name = d_map['NickName']
        del d_map['NickName']

        db = ConnectDB()
        try:
            cur = db.cursor()
            sql = "insert into user(nick_name, info) values(%s, %s) on duplicate key update info = %s, update_time = now()"
            cur.execute(sql, (nick_name, json.dumps(d_map['Info']), json.dumps(d_map['Info'])))
            db.commit()
        except (MySQLdb.Warning, MySQLdb.Error) as e:
            db.rollback()
            app.logger.exception('create user fail: %s' % str(e))
            return make_response('internal error', 500)
        except Exception, e:
            app.logger.exception('create user fail: %s' % str(e))
            return make_response('internal error', 500)
        finally:
            db.close()
        return make_response(get_user_id_by_name(nick_name), 201)
    except Exception, e:
        app.logger.exception('create user fail: %s' % str(e))
    return make_response('internal error', 500)

def is_existed_user(uid):
    db = ConnectDB()
    try:
        cur = db.cursor()
        sql = "select uid from user where uid = %s" 
        cur.execute(sql, (int(uid),))
        data = cur.fetchone()
        if data:
            return True
        return False
    except Exception, e:
        app.logger.exception('is_existed_user: %s' % str(e))
        raise
    finally:
        db.close()

def is_existed_testpaper(paper_id):
    db = ConnectDB()
    try:
        cur = db.cursor()
        sql = "select id from test_paper where id = %s" 
        cur.execute(sql, (int(paper_id),))
        data = cur.fetchone()
        if data:
            return True
        return False
    except Exception, e:
        app.logger.exception('is_existed_testpaper: %s' % str(e))
        raise
    finally:
        db.close()

def out_of_service(uid, paper_id):
    db = ConnectDB()
    try:
        cur = db.cursor()
        sql = "select info from billing where uid = %s" 
        cur.execute(sql, (int(uid),))
        billing_info = json.loads(cur.fetchone()[0])
        expire_time = datetime.strptime(billing_info['ExpireTime'], '%Y-%m-%d %H:%M:%S')
        
        sql = "select create_time from test_paper where id = %s" 
        cur.execute(sql, (int(paper_id),))
        create_time = cur.fetchone()[0]
        if expire_time >= create_time:
            return False
        return True
    except Exception, e:
        app.logger.exception('out_of_service: %s' % str(e))
        raise
    finally:
        db.close()

# get_testpaper 
@app.route('/testpapers/<paper_id>', methods = ['GET'])
def get_testpaper(paper_id):
    app.logger.info('get testpaper')
    
    try:
        # check user credentials
        if 'Uid' not in request.headers:
            return make_response('Uid should be included in request headers.', 400)
        
        if not is_existed_user(request.headers['Uid']):
            return make_response('%s is not valid user.' % request.headers['Uid'], 403)
        
        # check user billing
        if out_of_service(request.headers['Uid'], paper_id):
            return make_response('%s is out of service, please recharge later.' % request.headers['Uid'], 403)
        
        db = ConnectDB()
        try:
            cur = db.cursor()
            sql = "select marker, count from test_paper where id = %s" 
            cur.execute(sql, (int(paper_id),))
            (marker, count) = cur.fetchone()
            
            sql = "select id, info from single_choice where id >= %s limit %s" 
            cur.execute(sql, (int(marker), int(count)))
            rows = cur.fetchall()
            res = {'Choices':{}}
            for row in rows:
                res['Choices'][row[0]] = json.loads(row[1])
            return json.dumps(res)
        except Exception, e:
            app.logger.exception('get_testpaper: %s' % str(e))
            return make_response('internal error', 500)
        finally:
            db.close()
    except Exception, e:
        app.logger.exception('get testpaper fail: %s' % str(e))
    return make_response('internal error', 500)

# list_testpaper 
@app.route('/testpapers', methods = ['GET'])
def list_testpaper():
    app.logger.info('list testpaper')
    
    try:
        db = ConnectDB()
        try:
            cur = db.cursor()
            sql = "select id, name, marker, count, info from test_paper" 
            cur.execute(sql)
            rows = cur.fetchall()
            res = {'TestPapers':[]}
            for row in rows:
                res['TestPapers'].append({'Id':row[0],'Name':row[1],'Marker':row[2],'Count':row[3],'Info':row[4]})
            return json.dumps(res)
        except Exception, e:
            app.logger.exception('list_testpaper: %s' % str(e))
            return make_response('internal error', 500)
        finally:
            db.close()
    except Exception, e:
        app.logger.exception('list testpaper fail: %s' % str(e))
    return make_response('internal error', 500)

def is_existed_user_paper(uid, paper_id):
    db = ConnectDB()
    try:
        cur = db.cursor()
        sql = "select uid, test_paper_id from user_paper where uid = %s and test_paper_id = %s" 
        cur.execute(sql, (int(uid), int(paper_id)))
        data = cur.fetchone()
        if data:
            return True
        return False
    except Exception, e:
        app.logger.exception('is_existed_user_paper: %s' % str(e))
        raise
    finally:
        db.close()

# create_user_paper
@app.route('/users/<uid>/testpapers/<paper_id>', methods = ['POST'])
def create_user_paper(uid, paper_id):
    app.logger.info('create user paper')
    
    try:
        # "content-type: application/json" is required.
        if not request.is_json:
            return make_response('request data must be json-formatted.', 400)

        # check user credentials
        if not is_existed_user(uid):
            return make_response('%s is not valid user.' % uid, 403)
        
        if not is_existed_testpaper(paper_id):
            return make_response('%s is not valid testpaper.' % paper_id, 403)

        if is_existed_user_paper(uid, paper_id):
            return make_response('%s has been submitted.' % int(paper_id), 400)
        
        d_map = None
        try:
            d_map = request.get_json(force = True)
        except Exception, e:
            app.logger.exception('create_user_paper: %s' % str(e))
            return make_response('fail to decode request data', 400)
        
        if 'Choices' not in d_map or 0 == len(d_map['Choices']):
            return make_response('request data must not be empty.', 400)

        db = ConnectDB()
        try:
            cur = db.cursor()
            sql = "insert into user_paper(uid, test_paper_id, info) values(%s, %s, %s)" 
            cur.execute(sql, (int(uid), int(paper_id), json.dumps(d_map['Choices'])))
            db.commit()
        except Exception, e:
            app.logger.exception('create_user_paper: %s' % str(e))
            return make_response('internal error', 500)
        finally:
            db.close()
        return make_response('', 201)
    except Exception, e:
        app.logger.exception('create_user_paper: %s' % str(e))
    return make_response('internal error', 500)

# get_user_paper 
@app.route('/users/<uid>/testpapers/<paper_id>', methods = ['GET'])
def get_user_paper(uid, paper_id):
    app.logger.info('get user paper')
    
    try:
        # check user credentials
        if not is_existed_user(uid):
            return make_response('%s is not valid user.' % uid, 403)

        db = ConnectDB()
        try:
            cur = db.cursor()
            sql = "select info from user_paper where uid = %s and test_paper_id = %s" 
            cur.execute(sql, (int(uid), int(paper_id)))
            info = cur.fetchone()
            
            return '{"Choices":%s}' % info
        except Exception, e:
            app.logger.exception('get_user_paper: %s' % str(e))
            return make_response('internal error', 500)
        finally:
            db.close()
    except Exception, e:
        app.logger.exception('get user paper fail: %s' % str(e))
    return make_response('internal error', 500)

# list_user_paper 
@app.route('/users/<uid>/testpapers', methods = ['GET'])
def list_user_paper(uid):
    app.logger.info('list user paper')
    
    try:
        # check user credentials
        if not is_existed_user(uid):
            return make_response('%s is not valid user.' % uid, 403)
        
        db = ConnectDB()
        try:
            cur = db.cursor()
            sql = "select tp.id, tp.name from test_paper tp join user_paper up where tp.id = up.test_paper_id and up.uid = %s" 
            cur.execute(sql, (int(uid),))
            rows = cur.fetchall()
            res = {'TestPapers':[]}
            for row in rows:
                res['TestPapers'].append({row[0]:row[1]})
            return json.dumps(res)
        except Exception, e:
            app.logger.exception('list_user_paper: %s' % str(e))
            return make_response('internal error', 500)
        finally:
            db.close()
    except Exception, e:
        app.logger.exception('list user paper fail: %s' % str(e))
    return make_response('internal error', 500)

# get_user_quota 
@app.route('/users/<uid>/quota', methods = ['GET'])
def get_user_quota(uid):
    app.logger.info('get user quota')
    
    try:
        # check user credentials
        if not is_existed_user(uid):
            return make_response('%s is not valid user.' % uid, 403)
        
        db = ConnectDB()
        try:
            cur = db.cursor()
            sql = "select info from quota where uid = %s" 
            cur.execute(sql, (int(uid),))
            info = cur.fetchone()
            return info
        except Exception, e:
            app.logger.exception('get_user_quota: %s' % str(e))
            return make_response('internal error', 500)
        finally:
            db.close()
    except Exception, e:
        app.logger.exception('get user quota fail: %s' % str(e))
    return make_response('internal error', 500)

# modify_user_bill
@app.route('/users/<uid>/bill', methods = ['POST', 'PUT'])
def modify_user_bill(uid):
    app.logger.info('modify user bill')
    
    try:
        # "content-type: application/json" is required.
        if not request.is_json:
            return make_response('request data must be json-formatted.', 400)
        
        d_map = None
        try:
            d_map = request.get_json(force = True)
        except Exception, e:
            app.logger.exception('modify_user_bill: %s' % str(e))
            return make_response('fail to decode request data', 400)
        
        if 'Bill' not in d_map or 0 == len(d_map['Bill']):
            return make_response('request data must not be empty.', 400)

        db = ConnectDB()
        try:
            cur = db.cursor()
            sql = "insert into billing(uid, info) values(%s, %s) on duplicate key update info = %s"
            cur.execute(sql, (int(uid), json.dumps(d_map['Bill']), json.dumps(d_map['Bill'])))
            db.commit()
        except Exception, e:
            app.logger.exception('modify_user_bill: %s' % str(e))
            return make_response('internal error', 500)
        finally:
            db.close()
        return make_response('', 201)
    except Exception, e:
        app.logger.exception('modify_user_bill: %s' % str(e))
    return make_response('internal error', 500)

if __name__ == '__main__':
    port = 2469
    if len(sys.argv) == 2:
        port = int(sys.argv[1])
    app.run(host = '0.0.0.0', port = port, debug = True)
