__author__ = 'weiya.bai'


import os, glob, sys
from subprocess import Popen, PIPE, call
from multiprocessing import Pool
import fcntl

path = sys.argv[1]
numOfProcesses = int(sys.argv[2])




def handle(line):
    print "Scanning %s ......" % line
    files = []
    for file in glob.glob("*.pcap*"):
        command =  "tshark -r %s diameter.Public-Identity eq tel:%s | wc -l" % (file, line)
        print "executing command: %s" % command
        sp = Popen(command, shell=True, stdout=PIPE, close_fds=True)
        ret = sp.communicate()[0]
        #print ret
        if int(ret) > 0:
            files.append("%s    %s" % (file, ret))

    if len(files) > 0:
        with open('result.txt', 'a') as r:
            fcntl.flock(r, fcntl.LOCK_EX)
            r.write("%s\n\n" % line)
            for item in files:
                r.write("    %s\n" % item)
            fcntl.flock(r, fcntl.LOCK_UN)


if __name__ == '__main__':
    try:
        pool = Pool(processes = numOfProcesses)

        call("cat /dev/null > result.txt", shell=True)

        with open(path, 'r') as m:
            for line in m:
                if len(line) == 0:
                    continue
                line = line.strip()
                ret = pool.apply_async(handle, args=(line,))

        pool.close()
        pool.join()
    except:
        raise
