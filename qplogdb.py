#!/usr/bin/env python
# -*- coding: utf-8 -*-
import dateutil.parser
import datetime
import re
import traceback
import sqlite3
import argparse
import time
from dateutil.relativedelta import relativedelta
import glob

conn = None
def get_conn(reconnect = 0):
    global conn
    if (conn is None) or reconnect:
        conn = sqlite3.connect('qpcheck.db3')
        #conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
    return conn

def get_cur():
    return get_conn().cursor()

def create_db(do_clear = False):
    cursor = get_cur()
    if do_clear:
        cursor.execute("drop table if exists logdb")
    # create table to merge logs     
    cursor.execute("create table if not exists logdb(timestamp DATETIME, node text, source text, tag text, message text)")
    cursor.execute("CREATE INDEX if not exists checktm ON logdb(timestamp, node)")
    
    # create table to draw healthy data 
    cursor.execute("create table if not exists healthy(timestamp DATETIME, node text, healthy float, message text)")        
    
    # create table to show dashboard
    cursor.execute("create table if not exists check_summary(timestamp DATETIME, node text, check_item text, message text)")
    
    # create table to store scan/check history    
    cursor.execute("create table if not exists check_history(timestamp DATETIME, node text, check_item text, message text)")
    get_conn().commit()

node = 'local'
check_summary = {}
def set_node(new_node):
    global node
    node = new_node

def get_node(path = None):
    global node
    if path != None:        
        with open(path + '/hostname', 'r') as f:
            lines = f.readlines()
        node = lines[1].strip()
        print 'set node:', node
    return node

def set_check_summary(tag, message):
    global node
    if not check_summary.has_key(node):
        check_summary[node] = {}        
    check_summary[node][tag] = message
    print "Update check summary:", node, tag, message
    
def dump_summary():
    print '-' * 40
    print 'Summary:'
    for n in check_summary.keys():
        print '-- %s --' % n
        for item in check_summary[n].keys():
            print item, '\t detected: \t', check_summary[n][item]
    print '-' * 40
    
#global var to speed up
cursor = None
def add_log_item(timestamp, source, tag, message):
    global node, cursor
    if cursor is None:
        cursor = get_cur()
    cursor.execute("insert into logdb values (?,?,?,?,?)", [timestamp, node, source, tag, message])
    #print "add log:", timestamp, source, tag, message
    
def add_ha_value(timestamp, healthy, message):
    global node, cursor
    if cursor is None:
        cursor = get_cur()
    cursor.execute("insert into healthy values (?,?,?,?)", [timestamp, node, healthy, message])
    #print "add HA:", timestamp, healthy, message

def commit_log():
    global node, cursor
    get_conn().commit()
    if cursor is None:
        return
    cursor.close()
    cursor = None

def print_log(verbose=False):
    print '-' * 40
    print 'Log list:'
    cursor = get_cur()
    # no detail message
    if verbose:
        cursor.execute("select timestamp, node, source, tag,message from logdb order by timestamp")
    else:
        cursor.execute("select timestamp, node, source, tag from logdb order by timestamp")
    rows = cursor.fetchall()
    for row in rows:
        for c in row: 
            print c, '\t',
        print 
    cursor.close()
    print 'total count:', len(rows)
    print '-' * 40


def get_syslog_new_year_line(lines):
    new_year_line = 0
    line_no = 0
    month0 = 0
    for line in lines:
        if len(line)<3: continue
        line_no = line_no + 1
        d = datetime.datetime.strptime(line[:3],"%b")
        if d.month < month0:
            new_year_line = line_no
        month0 = d.month
    
    tk = lines[-1][:16]
    delta = dateutil.parser.parse(tk) - datetime.datetime.now()    
    #print "delta :", delta, trace_file
#need to implement the fix about feb 29
    if delta.days > 0:
        print "year delta : -1"
        year_delta = relativedelta(years=1)
    else:
        year_delta = relativedelta(years=0)    
            
    return new_year_line, year_delta
    
def check_time_moveback(lines):
    """
    delt_time = t - t0
        t0 = t
        # py2.6 use:
        if delt_time.seconds <0:
        #if delt_time.total_seconds() <0:
            tag = 'Time moved backwards % seconds' % delt_time.total_seconds()
            #print t, tag, delt_time.total_seconds(), ' seconds!'
            add_log_item(t,"syslog",tag,line)
            set_check_summary("ntp-time move back", line.strip()[:80])
    """    
    pass
    
def parse_syslog(log_file):
    print "check syslog:", log_file    
    rules = {
        'BIOS-provided physical RAM map': "reboot",
        'Error': "Error",
        'Warning': "Warning",
        'service_qp': 'service_qp',
        "ntpd\[\d+\]: Deleting interface": 'lost ip'
        }
    rules_re = {}
    for k in rules.keys():
        rules_re[k] = re.compile(k, re.IGNORECASE)
        #print 'Check item:', k, rules[k]

    with open(log_file, 'r') as f:
        lines = f.readlines()

    #check time move back
    check_time_moveback(lines)
    
    #check whether new year in file    
    new_year_line,year_delta = get_syslog_new_year_line(lines)
    
    line_no = 0    
    for line in lines:
        line_no = line_no + 1
        # modify year
        if line_no <new_year_line:
            #t = t - relativedelta(years=1)
            continue        
        #print line_no,
        #if line_no > 15000: break
        #Mar 31 08:09:52
        if len(line)<16: continue
        t = dateutil.parser.parse(line[:16]) - year_delta        
        #print delt_time
        #print t, line[16:]
        for k in rules.keys():
            #print 'check :', k
            m = rules_re[k].search(line[16:])
            if m is None: continue
            tag = rules[k]
            add_log_item(t,"syslog",tag,line)
            set_check_summary("syslog-"+tag, line.strip()[:80])
        #break
    commit_log()
    print "total lines parsed:", line_no
    
def parse_tpd_faillog(path):
    log_file = path + "/var/TKLC/log/syscheck/fail_log"
    with open(log_file, 'r') as f:
        lines = f.readlines()
    tm_pattern = re.compile(r'(\d+)\(')
    
    rules = {
        'FAILURE': "failure",
        'CRITICAL': "critical",
        'Gone Backwards': "time-move-back",        
        }        
    n = datetime.datetime.now()      
    for line in  lines:
        match = re.match(tm_pattern,line)
        if not match: continue        
        tk = datetime.datetime.fromtimestamp(int(match.groups()[0]))
        
        if tk.year < n.year: continue 
        
        for rule in rules.keys():
            if rule in line:
                #print line 
                add_log_item(tk,"faillog",rules[rule],line.strip())
    commit_log()
    
def convert_to_epoch(year, month, day, hour, minute, second, timezone):
    tz = pytz.timezone(timezone)
    date_and_time  = datetime.datetime(int(year), int(month), int(day), int(hour), int(minute), int(second))
    date_and_time_with_tz = tz.localize(date_and_time)
    epoch = calendar.timegm(date_and_time_with_tz.utctimetuple())
    return epoch

def send_graphite():
    import statsd
    import socket

    CARBON_SERVER = '0.0.0.0'
    CARBON_PORT = 2003
    sock = socket.socket()
    sock.connect((CARBON_SERVER, CARBON_PORT))
    if False:
        msg = 'qpplot.%s.overallcpu %s %d\n' % (log_file[:-4],fields[4] , tk)
        #sock.sendall(msg)
        msg = 'qpplot.%s.mem %s %d\n' % (log_file[:-4],fields[1] , tk)
        #sock.sendall(msg)
        msg = 'qpplot.%s.iowait %s %d\n' % (log_file[:-4],fields[2] , tk)
        #sock.sendall(msg)
        msg = 'qpplot.%s.cpu0 %s %d\n' % (log_file[:-4],fields[4] , tk)
        #sock.sendall(msg)
        msg = 'qpplot.%s.cpu1 %s %d\n' % (log_file[:-4],fields[5] , tk)
        sock.sendall(msg)
    #statsd_client = statsd.StatsClient('localhost', 8125)
    print int(time.time())
    sock.close()

def get_qpplot_date(log_file):
    # get date
    date_items = log_file[:-4].split('-')
    year =  int(date_items[-3])
    month = int(date_items[-2])
    day  =  int(date_items[-1])
    return year, month, day

def get_qpplot_time(year, month, day,timestamp):
    tm_items = timestamp.split(':')
    hour = int(tm_items[0])
    min  = int(tm_items[1])
    sec  = int(tm_items[2])
    timestamp = datetime.datetime(year,month,day,hour,min,sec)
    tk = time.mktime(timestamp.timetuple())
    return tk

def parse_qpplot(log_file):
    print "check ", log_file
    with open(log_file, 'r') as f:
        lines = f.readlines()
    line_no = 0
    y,m,d =get_qpplot_date(log_file)
    # XXX hack data so we see it easily
    #month = 3
    #day = 23
    # XXX end of hack
    tk0 = 0
    total_cpus = 0
    for line in lines:
        if len(line)<8: continue
        if line[0] == '#': continue
        line_no = line_no + 1
        fields=line.split()
        #print fields[0],fields[4]
        #statsd_client.gauge('qp1cpu', float(fields[4]))

        tk =get_qpplot_time(y,m,d,fields[0])        
        tk_str = "%02d-%02d-%02d %s" %(y,m,d,fields[0])
        #print tk
        if line_no > 1:
            dt = tk - tk0
            if dt<0:
                add_log_item(tk_str,"qpplot","time move back",line)
                set_check_summary("qpplot-time-move-back", tk_str)            
            elif dt > 3:
                msg =  "possible qpstat lost data caused by CPU spike at: %s, delta seconds=%d" % (tk_str, dt)                
                add_log_item(tk_str,"qpplot","CPU spike",msg)
                set_check_summary("qpplot-CPU spike", msg)            
        else:
            #print "fileds:", len(fields)
            total_cpus = len(fields) - 4            
        tk0 = tk
        for i in range(4,total_cpus):
            cpu_usage = float(fields[i])
            if cpu_usage > 90:
                msg= "CPU spike: CPU %d  usage %s at %s" % (i, fields[i], tk_str)                
                add_log_item(tk_str,"qpplot","CPU spike",msg)
                set_check_summary("qpplot-CPU spike", msg)            
        #if  line_no > 1000: break

    commit_log()
    print "done"

def parse_cmha():
    PATH = r"D:\bugs\KT\20160229\savelogs_plat.Guro2-MPE2-A.48626"
    file = r"comcol_traces\qp_procmgr"
    # 0129:031519.661  QP1   Going to Active [39587/QpProcMgr.cxx:327]
    with open(PATH + "\\" + file, 'r') as f:
        lines = f.readlines()

    for line in lines:
        if len(line) < 1: continue

def get_tracelog_new_year_line(lines):
    new_year_line = 0
    line_no = 0
    s1 = lines[0][:2]
    tm_pattern = re.compile(r'(\d\d)(\d\d):(\d\d)(\d\d)(\d\d)\.(\d\d\d)')
    for line in lines:
        line_no = line_no + 1
        match = re.match(tm_pattern,line)
        if not match: continue
        last_timestamp = line[:2]
        if last_timestamp < s1:            
            new_year_line = line_no
            #print "NEW YEAR:", line_no, line
            #print 'NEW YEAR:\t',trace_file    
        s1 = last_timestamp
        
    # check whether log is from previous year
    line = lines[-1]
    tk  = line[0:2] + '-' + line[2:4] + ' ' +line[5:15]
    delta = dateutil.parser.parse(tk) - datetime.datetime.now()    
    #print "delta :", delta, trace_file
    if delta.days > 0:
        print "year delta : -1"
        year_delta = relativedelta(years=1)
    else:
        year_delta = relativedelta(years=0)    
            
    return new_year_line, year_delta
    
def parse_qp_procmgr(trace_file):
    print "check qp trace:", trace_file
    qp_procmgr_rules = {
        'Process was blocked': {'tag':"CPU spike?", 'score':0},
        'PROGRAM TERMINATED':  {'tag':"Stop",       'score':0},
        'PROGRAM STARTED':     {'tag':"Start",      'score':0},
        'I am going to die':   {'tag':"app died",   'score':180},
        'Going to OOS':        {'tag':'HA role changed', 'score':200},
        'Going to Spare':      {'tag':'HA role changed', 'score':210},
        'Going to Standby':    {'tag':'HA role changed', 'score':220},
        'Going to Active ':    {'tag':'HA role changed', 'score':230},
        "We are told to restart": {'tag':'user restart', 'score':0}
        }
    rules_re = {}
    for k in qp_procmgr_rules.keys():
        rules_re[k] = re.compile(k, re.IGNORECASE)
        #print 'Check item:', k, qp_procmgr_rules[k]
        
    with open(trace_file, 'r') as f:
        lines = f.readlines()

    #adjust years    
    new_year_line,year_delta = get_tracelog_new_year_line(lines)
    #print "new year line:", new_year_line, "->",lines[new_year_line] 
    
    tm_pattern = re.compile(r'(\d\d)(\d\d):(\d\d)(\d\d)(\d\d)\.(\d\d\d)')            
    
    # scan logs
    line_no = 0    
    ha_value = 0
    for line in lines:
        line_no = line_no +1 
        if line_no < new_year_line: continue
        if len(line) < 1: continue
        
        # parse timestamp        
        match = re.match(tm_pattern,line)
        if not match: continue
        
        tk  = line[0:2] + '-' + line[2:4] + ' ' +line[5:15] 
        t = dateutil.parser.parse(tk) - year_delta
        
        #if line_no <= num:
        #    t = t - datetime.timedelta(days=366)
        pattern1 = re.compile(r'Going')
        match1 = re.search(pattern1, line)
        if not match1: continue
        
        
        line = line.strip()
        for r in qp_procmgr_rules.keys():
            if r in line:
                tag = r # qp_procmgr_rules[r]['tag']
                add_log_item(t,"procmgr",tag,line)             
                if qp_procmgr_rules[r]['score'] >=0:
                    ha_value = qp_procmgr_rules[r]['score']
                    add_ha_value(t, ha_value, line)
                    
        """for k in qp_procmgr_rules.keys():
            #print 'check :', k
            m = rules_re[k].search(line[16:])
            if m is None: continue
            tag = qp_procmgr_rules[k]['tag']
            add_log_item(t,"procmgr",tag,line)             
        """
    commit_log()    
    print "total lines parsed: ", line_no 

def get_qpplot_mem(file):
    with open(file, 'r') as f:
        f.readline()
        line = f.readline()
    #print line.split()
    return float(line.split()[1])
    
def check_qpplot(path):
    files = glob.glob(path + "/var/camiant/log/plot/cpu*.dat")
    files.sort(key=get_qpplot_date)
    m1 = get_qpplot_mem(files[0])
    m2 = get_qpplot_mem(files[-1])
    delta_mem = m2 - m1
    print "qpplot memory change in days:", delta_mem, "%"
    if delta_mem > 3:
        set_check_summary("qpplot-memleak", "memory usage change is %.2f%%" % delta_mem)
        
    for f in files:
        parse_qpplot(f)
        
def check_multiple(paths):    
    for path in paths:
        # check syslog
        get_node(path)
        # syslog checking
        parse_syslog(path+r"/var/log/messages")
        
        # check qp plot data
        check_qpplot(path)
        
        # check cm ha
        # check qp_procmgr        
        parse_qp_procmgr(path+"/comcol_traces/qp_procmgr")
        
        #TPD fail log
        parse_tpd_faillog(path)
        
    print_log()
    dump_summary()
    
def main():
    #syslog1 = ['D:/bugs/KT/20160229/savelogs_plat.Guro2-MPE2-A.48626/var/log/messages']

    desc = "Help to collect logs into a central place."
    usage = """
        Example:
        %prog --syslog D:/bugs/KT/20160229/savelogs_plat.Guro2-MPE2-A.48626/var/log/messages'
    """
    parser = argparse.ArgumentParser(description=usage)
    parser.add_argument('--node',   help="set node name")
    parser.add_argument('--syslog', action='append',default=[], help="syslog file name")
    parser.add_argument('--procmgr',action='append',default=[],help='procmgr log file name')

    parser.add_argument('--qpplot', help="parse qp plot file")
    parser.add_argument('--cmha',   help="parse cmha")
    parser.add_argument('--dump',   action='store_true', help="dump log table")    
    parser.add_argument('--verbose',action='store_true', help="dump verbose log table")    
    parser.add_argument('--check', action='append',default=[], help="do sanity check on one or multiple save state logs")
    parser.add_argument('--clear',  dest='clear', action='store_true', help='clear the database')

    args = parser.parse_args( )
    #args = parser.parse_args( ['--syslog', 'D:/bugs/KT/20160229/savelogs_plat.Guro2-MPE2-A.48626/var/log/messages'] )
    #args = parser.parse_args( ['--dump'] )
    #args = parser.parse_args( ['--syslog',
    #    'D:/bugs/KT/20160229/savelogs_plat.Guro2-MPE2-A.48626/var/log/messages'])

    #args = parser.parse_args( ['--qpplot',
    #    r'C:\Jing\qplog\Guro2-MPE3-A.plot\cpustat-2016-2-19.dat'] )

    if args.node:
        set_node(args.node)
        
    if args.clear:
        create_db(True)
    else:
        create_db()
        
    if args.cmha:
        parse_cmha()
        
    for f in args.syslog:
        parse_syslog(f)

    for f in args.procmgr:        
        parse_qp_procmgr(f)

    if args.qpplot:
        parse_qpplot(args.qpplot)

    if args.check:
        check_multiple(args.check)
        
    if args.dump:
        print_log(args.verbose)

if __name__ == "__main__":
    main()

#import dateutil.relativedelta
#t = dateutil.parser.parse('2014-02-13 17:33:41.817981+08:00')
#print t

#COMCOL trace: 0129:015838.238
# app event log:
#t = dateutil.parser.parse('02/24/2016 10:14:15.585')
#print t

#python /root/timeline.py -t '2016-02-15 00:00:00 2016-02-25 00:00:00 GMT' -d '/var/camiant/issues/3-12208253751/savelogs_plat.Guro2-MPE3-A.64196/,/var/camiant/issues/3-12208253751/savelogs_plat.Guro2-MPE3-B.50799/'

"""
https://docs.python.org/2/library/sqlite3.html
dump db:
# Convert file existing_db.db to SQL dump file dump.sql
import sqlite3, os
con = sqlite3.connect('existing_db.db')
with open('dump.sql', 'w') as f:
    for line in con.iterdump():
        f.write('%s\n' % line)
"""
