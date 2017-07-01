#!/usr/bin/env python
import os,sys,stat

config_args = {'serverIP':'localhost',
               'uwsgiPort':'2469', #uwsgi,nginx communication port
               'module':'main',
               'callable':'app',
               'processes':'1'
               }

nginx_bin_path = os.popen('which nginx').read().strip(' \n') 
nginx_config_path = '/etc/nginx/nginx.conf'


content_uwsgi_config = '''
<uwsgi>
    <pythonpath>%(pythonpath)s</pythonpath>
    <module>%(module)s</module>
    <callable>%(callable)s</callable>
    <socket>127.0.0.1:%(socket)s</socket>
    <master/>
    <processes>%(processes)s</processes>
    <memory-report/>
</uwsgi>
'''

# remove '--plugin python' in pip installation.
uwsgi_command = '''
sudo uwsgi -x %(path)s/app_config.xml &
'''

def create_config_file(python_path,
        module = config_args['module'], 
        callable_path=config_args['callable'], 
        processes = config_args['processes'], 
        socket = config_args['uwsgiPort']):
    f = open(python_path + '/app_config.xml', 'w')
    f.write(content_uwsgi_config % {'pythonpath':python_path,
                                    'module':module,
                                    'callable':callable_path,
                                    'processes':processes,
                                    'socket': socket})
    f.close()

def check_process(name):
    return int(os.system('ps -C %s' % name))

def check_uwsgi():
    if check_process('uwsgi'):
        print 'error: uwsgi is dead!'
        sys.exit(1)

def check_nginx():
    if check_process('nginx'):
        print 'error: nginx is dead!'
        sys.exit(1)

def check_env():
    check_nginx()
    #check_uwsgi()

def deploy(cur_dir):
    os.system(uwsgi_command % {'path':cur_dir })
    print 'success'

if __name__ == '__main__':
    if len(sys.argv) != 2 and len(sys.argv) != 3:
        print 'usage: process_num [uwsgi_port]'
        sys.exit(1)
    proc_num = sys.argv[1]
    uwsgi_port = 2469
    if len(sys.argv) >= 3:
        uwsgi_port = sys.argv[2]
    cur_dir, cur_file = os.path.split(os.path.abspath(sys.argv[0]))
    check_env()
    create_config_file(python_path = cur_dir, processes = proc_num, socket = uwsgi_port)
    deploy(cur_dir)
