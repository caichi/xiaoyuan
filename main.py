#! /usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
import time
import math
import logging
import logging.handlers
import thread
from flask import Flask, request, session, g, redirect, url_for, abort, \
     render_template, flash, json
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

InitLog()

@app.before_request
def Prepare():
	pass

def ConnectDB():
    return MySQLdb.connect(config.DB_HOST, config.DB_USER, config.DB_PASSWD, config.DB_NAME, config.DB_PORT)

# CreateUser
@app.route('/users', methods = ['POST'])
def CreateUser():
    app.logger.info('CreateUser')
    try:
		if not request.is_json():
			return make_response('request data must be json-formatted.', 400)
		
		d_map = None
    	try:
			d_map = request.get_json(force = True)
    	except Exception, e:
    	    app.logger.exception('CreateUserFail: %s' % str(e))
			return make_response('fail to decode request data', 400)
		
		if 0 == len(d_map):
			return make_response('request data must not be empty.', 400)
    	
    	db = ConnectDB()
    	try:
    	    cur = db.cursor()
			sql = 'insert into user(uid, info) values(%s, %s)' % 
    	    cur.execute(sql, (d_map['Uid'], json.dumps(d_map['Info'])))
    	    db.commit()
    	except (MySQLdb.Warning, MySQLdb.Error) as e:
    	    db.rollback()
    	    app.logger.exception('CreateUserFail: %s' % str(e))
			return make_response('internal error', 500)
    	except Exception, e:
    	    app.logger.exception('CreateUserFail: %s' % str(e))
			return make_response('internal error', 500)
    	finally:
    	    db.close()
		return make_response('', 201)
    except Exception, e:
        app.logger.exception('CreateUserFail: %s' % str(e))
	return make_response('internal error', 500)

       

if __name__ == '__main__':
    port = 2469
    if len(sys.argv) == 2:
        port = int(sys.argv[1])
    app.run(host = '0.0.0.0', port = port, debug = True)
