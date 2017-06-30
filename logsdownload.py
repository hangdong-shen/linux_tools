import os
import glob
import commands
import time
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
import paramiko
#import wget
import argparse


# if the file exist, no longer downloading
def get_filelist(remote_path):
    print 'remote path: ' + remote_path
    ip='10.113.69.251'
    user='root'
    password='NextGen'
    port = 22

    #print remote_path
    s = paramiko.SSHClient()
    s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    s.connect(ip, port, user, password)
    stdin,stdout,stderr = s.exec_command('ls ' + remote_path)
    filelist=stdout.read()
    s.close()
#    for i in filelist:
#        print i
#        time.sleep(5)
    return filelist

def upload_files(local_dir, remote_path):
    ip='10.113.69.251'
    user='root'
    password='NextGen'
    port = 22
    
    #print remote_path
    s = paramiko.SSHClient()
    s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    s.connect(ip, port, user, password)
    sftp = s.open_sftp()

    local_files =  os.listdir(local_dir)
    if(len(local_files)==0):
        print "no files, no upload."
        return 0
    for i in local_files:
        try:
            sftp.put(os.path.join(local_dir, i), os.path.join(remote_path,i))
        except:
            print 'Failed to upload file ' + i
        else:
            print 'Successfuly upload file ' + i

def my_mkdirs(sr):
    sr = sr.strip()
    sr = sr.rstrip('\\')

    global forced
#    if(forced):
#        print 'Force to download'
#        return True
    # if the path exist
    global remote_dir
    remote_path = remote_dir
    filelist = get_filelist(remote_path)
    hasPath = filelist.find(sr)
    if(-1 == hasPath):
        ip='10.113.69.251'
        user='root'
        password='NextGen'
        port = 22

        s = paramiko.SSHClient()
        s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        s.connect(ip, port, user, password)
        stdin,stdout,stderr = s.exec_command('mkdir ' + remote_path + sr)
        stderr.read()
        if(0== len(stderr.read())):
            print 'success to mkdir: '+ ip + ':' + remote_path+sr
        s.close()
        return True
    else:
        print 'SR ' + sr + ' already exists!'
        return False

def my_login(browser):
    username = 'eastward.shen' #raw_input("input your sso username: ")
    password = 'Or060620' #raw_input("input your sso passward: ")
    username = username + '@oracle.com'
    
    elem = browser.find_element_by_id('sso_username')
    elem.clear()
    elem.send_keys(username)
    elem = browser.find_element_by_id('ssopassword')
    elem.clear()
    elem.send_keys(password)
    elem.submit()
    time.sleep(5)

def login_get_hrefs(browser):
    username = 'eastward.shen' #raw_input("input your sso username: ")
    password = 'Or060620' #raw_input("input your sso passward: ")
    username = username + '@oracle.com'
    
    elem = browser.find_element_by_id('sso_username')
    elem.clear()
    elem.send_keys(username)
    elem = browser.find_element_by_id('ssopassword')
    elem.clear()
    elem.send_keys(password)
    elem.submit()
    time.sleep(5)
    hrefs=get_path(browser)
    sr_get(browser)
    return hrefs
     
def get_path(browser):
    """    
    username = 'eastward.shen' #raw_input("input your sso username: ")
    password = 'Or060620' #raw_input("input your sso passward: ")
    username = username + '@oracle.com'
    
    elem = browser.find_element_by_id('sso_username')
    elem.clear()
    elem.send_keys(username)
    elem = browser.find_element_by_id('ssopassword')
    elem.clear()
    elem.send_keys(password)
    elem.submit()
    time.sleep(5)
    """
    path=[]
    path = browser.find_elements_by_xpath("//a[contains(@href, 'mode=checkout')]")    
    if (0 == len(path)):
        path=browser.find_elements_by_xpath("//a[contains(@href, 'filedownloadservlet')]")
    return path

def sr_get(browser):
    sr_href=browser.find_elements_by_xpath("//a[contains(@href, 'https://mosemp.us.oracle.com/mosspui/src/sr/viewer')]")
    sr_att=sr_href[0].get_attribute('href')
    global sr_num
    sr_index =sr_att.find('3-',0)
    sr_num=sr_att[sr_index:sr_index+13]    
    return sr_num

def check_localdir():
    global local_dir
    os.chdir(local_dir)

    files=os.listdir('.')
    if(0 !=len(files)):
        need_fflash = raw_input("There are old logs, do we need to fflash? Y/N ")
        if(need_fflash.lower() == 'y'):
            a,b=commands.getstatusoutput('sudo rm -fr *.*')
            if(0 == a):
                print 'sucessfully fflush!'
            else:
                print 'fail to fflush, pls fflush manually!'

def accept(browser):
    handles=browser.window_handles
    currentW=browser.current_window_handle
    WebDriverWait(browser, 10)
    WebDriverWait(browser, 10).until(lambda d: len(d.window_handles) == 2)
    browser.switch_to.window(handles[1])
    #WebDriverWait(browser, 10).until(lambda d: d.title != "")
    #print 'success switch to ' + browser.current_url
    try:
        #button = WebDriverWait(browser, 10).until(EC.element_to_be_clickable((By.NAME, "accept")))
        print 'try to click a.x133'
        time.sleep(5)
        elem = browser.find_element_by_class_name('x133')
        elem.click()
    except:
        print 'Not find accpet button'
        print 'Swith to origin window'
    
    browser.switch_to.window(currentW)

def download(bugnum):
    global local_dir
    global remote_dir
    global sr_num
#    sr_pre = 'SR='
    filename_pre = 'FileName='
    login = 'https://login.oracle.com/mysso/signon.jsp'
   #first_tag=True
    url = 'https://bug.oraclecorp.com/pls/bug/webbug_print.show?c_rptno=' + bugnum
    href=''

    #if want to use default configuration
   #profile_dir="/root/.mozilla/firefox/dtlxqha6.default"
    profile_dir="/home/east/.mozilla/firefox/default.fox"
    profile = webdriver.FirefoxProfile(profile_dir) 
    browser = webdriver.Firefox(profile)

    #browser = webdriver.Firefox()
    if(browser):
        browser.get(url)
        browser.get_cookies()
        time.sleep(5)
        if(browser.current_url == login):
           # path=login_get_hrefs(browser)
            my_login(browser)
            sr_get(browser)
            path=get_path(browser)
            print 'SR is : ' + sr_num
            result = my_mkdirs(sr_num)
            currentW=browser.current_window_handle
            global forced
            if result:
                for i in path:
                    #may be after accept , it needs to switch back to main window
                    i.click()
                    time.sleep(5)
                    if(forced):
                        handles=browser.window_handles
                        if(1<len(handles)):
                            accept(browser)
                            forced=False
                        else:
                            print 'No need accpet'
                        """
                        handles=browser.window_handles
                        WebDriverWait(browser, 10)
                        WebDriverWait(browser, 10).until(lambda d: len(d.window_handles) == 2)
                        browser.switch_to.window(handles[1])
                        #WebDriverWait(browser, 10).until(lambda d: d.title != "")
                        #print 'success switch to ' + browser.current_url
                         #button = WebDriverWait(browser, 10).until(EC.element_to_be_clickable((By.NAME, "accept")))
                            #button = WebDriverWait(browser, 10).until(EC.element_to_be_clickable((By.NAME, "accept")))
                            print 'try to click a.x133'
                            time.sleep(5)
                            elem = browser.find_element_by_class_name('x133')
                            elem.click()
                        except:
                            print 'No need accpet'
                        print 'Swith to origin window'
                        browser.switch_to.window(currentW)
                        """
            else:
                remote_path = remote_dir + sr_num
                filelist = get_filelist(remote_path)
                print filelist
                for i in path:
                    href = i.get_attribute('href')
                    href_len = len(href)
                    filename_begin = href.find(filename_pre, 0, href_len)
                    filename_end = href.find('&', filename_begin+1, href_len)
                    filename=href[filename_begin+9:filename_end]
                    print filename
                    #remote list
                    if (-1 == filelist.find(filename, 0, len(filelist))):
                        i.click()
                       #wget.download(i)
                        time.sleep(5)
                        if(forced):
                            handles=browser.window_handles
                            if(1<len(handles)): 
                                accept(browser)
                                forced=False
                            else:
                                print 'No need accpet' 
                    else:
                        print 'file ' + filename + ' already exist!'
        else:
            path=get_path(browser)
            sr_get(browser)
            for i in path:
                i.click()    
                time.sleep(5)
               #print "find checkout."

        # TODO :: the new page need to click the accept 

        # mv the file to the issue path
        #if the file has .part, and when .part is finish, i think the file complete the download.
        while(1):
            os.chdir(local_dir)
            #print "time error?"
            time.sleep(10+5)
            localfiles=os.listdir('.')
            localfileslen=len(localfiles)
            print("files: %d" %(localfileslen))
            if(0 !=localfileslen):
                time.sleep(10)
                if(0 !=len(glob.glob('*.part'))):
                    time.sleep(30)
                else:
                    break
            else:
                break
    else:
        print "error"

    print '\033[1;32;40m'
    print "the downloaded files: \r\n"
    for i in localfiles:
        print i
    print '\033[0m'
    need_quit = raw_input("Do we need to quit browser? Y/N ")
    if('y' == need_quit):
        browser.quit()

def upload(bugnum):
    global remote_dir
    global local_dir
    sr_pre = 'SR='
    global sr_num
    if(len(sr_num) == 0):
        login = 'https://login.oracle.com/mysso/signon.jsp'
 
        url = 'https://bug.oraclecorp.com/pls/bug/webbug_print.show?c_rptno=' + bugnum

        #if want to use default configuration

        profile_dir="/home/east/.mozilla/firefox/default.fox"
        profile = webdriver.FirefoxProfile(profile_dir) 
        browser = webdriver.Firefox(profile)

        if(browser):
            browser.get(url)
            time.sleep(5)
            if(browser.current_url == login):
                my_login(browser)
            #if there is no need login, then add no login algo here
        else:
            print "Error!"
        sr_get(browser)
        browser.quit()

    print("got the SR %s to upload" %(sr_num))
    remote_path = remote_dir + sr_num +'/'

    upload_files(local_dir, remote_path)
    

#global para
sr_num=""
forced=False
forceu=False
#remote_dir='/home/pteam2/SR_logs/'
remote_dir='/var/issues/'
local_dir='/home/east/bug/logs/'

def main():
    
    os.environ['DISPLAY'] = ":2"
    #add option 
    desc = "Help to download and upload the logs."
    usage = """
            Example:
            %prog clear|download| upload|tar all
            """
    check_localdir()

    parser = argparse.ArgumentParser(description =usage)
    parser.add_argument('-b', '--bugnumber', help = "set the bug number")
    parser.add_argument('-d', '--download', action ='store_true', help ="download the logs")
    parser.add_argument('-f', '--forced', action ='store_true', help ="force download the logs")

    parser.add_argument('-u', '--upload', action ='store_true', help = "upload the logs")

    args = parser.parse_args()
    if args.bugnumber:
        bugnum = args.bugnumber
       
    if args.forced:
        global forced
        forced=True
        print 'force download'
    if args.download:
        download(bugnum)

    if args.upload:
        upload(bugnum)
#    if args.forceu:
#        forceu=True
            #begin_upload = raw_input("Need to upload(type when you finish downlod: Y/N ")
        #if(begin_upload.lower() == 'y'):
        
   
if __name__ == "__main__":

    main()

    check_localdir()            

