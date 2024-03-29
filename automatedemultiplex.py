'''
Created on 19 Sep 2016
This script loops through all the run folders in a directory looking for any newly completed runs ready to be demultiplexed
The run is deemed complete by the presense of a files called RTAComplete.txt. This will only be present when the run is ready for demultiplexing.
A sample sheet must be present so a samplesheet with the name of the flowcellid_samplesheet.csv must be present in the samplesheets folder.
Finally a check that the demultiplexing has (or is) not already being performed (by presence of the demultiplexing logfile).
If the run is ready for demultiplexing then a subprocess command is issued.
The stdout and stderr is written to a log file (the same file which is checked for above).
Could possibly add a check/message if it fails.
 
@author: aled
'''

import os
import subprocess
import datetime
import smtplib
from email.Message import Message
import fnmatch
import requests
import json


class get_list_of_runs():
    '''Loop through the directories in the directory containing the runfolders.
    This script is designed to be run as a cron job each hour. 
    A log file is created each time the script is run. If a folder is demultiplexed in that hour a second log file is created with the name timestamp_NGSrun#.
    To combine the two log files this extra class is required in order to capture the time stamp for where the cron job starts (I think!)'''
    
    def __init__(self):
        # directory of run folders - must be same as in ready2start_demultiplexing()
        self.runfolders ="/media/data1/share" # workstation
        self.now=""

    def loop_through_runs(self):
        #set a time stamp to name the log file
        self.now = str('{:%Y%m%d_%H}'.format(datetime.datetime.now()))

        # create a list of all the folders in the runfolders directory
        all_runfolders = os.listdir(self.runfolders)
        
        #create instance of the class which performs demultiplexing
        demultiplex=ready2start_demultiplexing()
        
        # for each folder (if it is not "samplesheets") pass the runfolder to ready2start_demultiplexing class
        for folder in all_runfolders:
            if folder != "samplesheets":
                if folder.endswith('.gz'):
                    pass
                else:
                    demultiplex.already_demultiplexed(folder, self.now)
        
        #call function to combine log files
        self.combine_log_files()

    def combine_log_files(self):
        # count number of log files that match the time stamp
        count=0
        list_of_logfiles=[]
        for file in os.listdir(ready2start_demultiplexing().script_logfile_path):
            if fnmatch.fnmatch(file,self.now+'*'):
                count=count+1
                list_of_logfiles.append(ready2start_demultiplexing().script_logfile_path+file)
        
        if count > 1:
            longest_name=max(list_of_logfiles, key=len)
            list_of_logfiles.remove(longest_name)
            remaining_files=" ".join(list_of_logfiles)

            # combine all into one file with the longest filename
            cmd = "cat " + remaining_files + " >> " + longest_name
            rmcmd= "rm " + remaining_files

            # run the command, redirecting stderror to stdout
            proc = subprocess.call([cmd], stderr=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)
            proc = subprocess.call([rmcmd], stderr=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)


class ready2start_demultiplexing():
    '''This class checks if a run is ready to be demultiplexed (samplesheet present, run finished and not previously demultiplexed) and if so demultiplexs run''' 
    def __init__(self):
        # directory of run folders - must be same as in get_list_of_runs()
        self.runfolders ="/media/data1/share" # workstation
        
        #set the samplesheet folders
        self.samplesheets = self.runfolders + "/samplesheets"
        
        # file which denotes end of a run
        self.complete_run = "RTAComplete.txt"
        
        # log file which denotes that demultiplexing is underway/complete 
        self.demultiplexed = "demultiplexlog.txt"

        # set empty variables to be defined based on the run  
        self.runfolder = ""
        self.runfolderpath = ""
        self.samplesheet = ""
        self.list_of_samplesheets=[]

        # path to bcl2fastq
        self.bcl2fastq = "/usr/local/bcl2fastq2-v2.17.1.14/bin/bcl2fastq"
        
        #succesful run message
        self.logfile_success="Processing completed with 0 errors and 0 warnings."

        #bcl2fastq test file
        self.bcltest= "/home/mokaguys/Documents/automate_demultiplexing_logfiles/bcl2fastq.txt"
        
        #logfile
        self.script_logfile_path="/home/mokaguys/Documents/automate_demultiplexing_logfiles/Demultiplexing_log_files/" # workstation
        self.logfile_name=""
        
        #email server settings
        self.user = ''
        self.pw   = ''
        self.host = ''
        self.port = 0
        self.me   = ''
        self.you  = ('',)
        self.smtp_do_tls = True
        
        # email message
        self.email_subject=""
        self.email_message=""
        self.email_priority=3

        #rename log file
        self.rename=""
        self.name=""
        self.now=""

        #smartsheet API
        self.api_key=""
        
        #sheet id
        self.sheetid=
        #newly inserted row
        self.rowid=""

        #time stamp
        self.smartsheet_now=""

        #columnIds
        self.ss_title=str()
        self.ss_description=str()
        self.ss_samples=str()
        self.ss_status=str()
        self.ss_priority=str()
        self.ss_assigned=str()
        self.ss_received=str()
        self.ss_completed=str()
        self.ss_duration=str()
        self.ss_metTAT=str()

        #requests info
        self.headers={"Authorization": "Bearer "+self.api_key,"Content-Type": "application/json"}
        self.url='https://api.smartsheet.com/2.0/sheets/'+str(self.sheetid)


    def already_demultiplexed(self, runfolder, now):
        '''check if the runfolder has been demultiplexed (demultiplex_log is present)'''
        self.now=now
        
        #open the logfile for this hour's cron job as append.
        self.logfile_name=self.script_logfile_path+self.now+".txt"
        self.script_logfile=open(self.logfile_name,'a')

        # capture the runfolder 
        self.runfolder = str(runfolder)
               
        # create full path to runfolder
        self.runfolderpath = self.runfolders + "/" + self.runfolder
        
        self.script_logfile.write("\n----------------------"+str('{:%Y-%m-%d %H:%M:%S}'.format(datetime.datetime.now()))+"-----------------\nAssessing......... " + self.runfolderpath+"\n")
        
        # if the demultiplex log file is present
        if os.path.isfile(self.runfolderpath + "/" + self.demultiplexed):
            # stop
            self.script_logfile.write("Checking if already demultiplexed .........Demultiplexing has already been completed  -  demultiplex log found @ "+self.runfolderpath + "/" + self.demultiplexed+" \n--- STOP ---\n")
        else:
            self.script_logfile.write("Checking if already demultiplexed .........Run has not yet been demultiplexed\n")
            # else proceed
            self.has_run_finished()

    def has_run_finished(self):
        ''' check for presence of RTAComplete.txt to denote a finished sequencing run'''
        # check if the RTAcomplete.txt file is present
        if os.path.isfile(self.runfolderpath + "/" + self.complete_run):
            self.script_logfile.write("Run has finished  -  RTAcomplete.txt found @ "+ self.runfolderpath + "/" + self.complete_run+"\n")
            
            #if so proceed
            self.look_for_sample_sheet()
        else:
            # else stop 
            self.script_logfile.write("run is not yet complete \n--- STOP ---\n")
                  

    def look_for_sample_sheet(self):
        '''check sample sheet is present'''
        # set name and path of sample sheet to find
        self.samplesheet=self.samplesheets + "/" + self.runfolder + "_SampleSheet.csv"
        
        # get a list samplesheets in folder
        all_runfolders = os.listdir(self.samplesheets)
        for samplesheet in all_runfolders:
            # convert all to capitals
            self.list_of_samplesheets.append(samplesheet.upper())

        # set the expected samplesheet name (convert to uppercase)
        expected_samplesheet = self.runfolder.upper() + "_SAMPLESHEET.CSV"
        
        #if the samplesheet exists
        if expected_samplesheet in self.list_of_samplesheets:
            self.script_logfile.write("Looking for a samplesheet .........samplesheet found @ " +self.samplesheet+"\n")
            #send an email:
            self.email_subject="MOKAPIPE ALERT: Demultiplexing initiated"
            self.email_message="demultiplexing for run " + self.runfolder + " has been initiated"
            self.send_an_email()
            # proceed
            self.run_demuliplexing()
        else:
            # stop
            self.script_logfile.write("Looking for a samplesheet ......... no samplesheet present \n--- STOP ---\n")
      

    def run_demuliplexing(self):
        '''Run bcl2fastq'''
        
        #print "demultiplexing ..... "+self.runfolder
        # example command sudo /usr/local/bcl2fastq2-v2.17.1.14/bin/bcl2fastq -R /media/data1/share/160914_NB551068_0007_AHGT7FBGXY --sample-sheet /media/data1/share/samplesheets/160822_NB551068_0006_AHGYM7BGXY_SampleSheet.csv --no-lane-splitting
                
        # test bcl2fastq install
        self.test_bcl2fastq()
        
        #update smartsheet
        self.smartsheet_demultiplex_in_progress()
        
        # create the command
        command = self.bcl2fastq + " -R " + self.runfolders+"/"+self.runfolder + " --sample-sheet " + self.samplesheet + " --no-lane-splitting"
        
        self.script_logfile.write("running bcl2fastq ......... \ncommand = " + command+"\n")
        
        # open log file to record bcl2fastq stdout and stderr - use to define when/if demultiplexing has been performed
        demultiplex_log = open(self.runfolders+"/"+self.runfolder+"/"+self.demultiplexed,'w')
        
        # run the command, redirecting stderror to stdout
        proc = subprocess.Popen([command], stderr=subprocess.STDOUT, stdout=subprocess.PIPE, shell=True)
        
        # capture the streams (err is redirected to out above)
        (out, err) = proc.communicate()
        
        # write this to the log file
        demultiplex_log.write(out)
        
        # close log file
        demultiplex_log.close()
        
        # call_log_file_check
        self.check_demultiplexlog_file()
        
    def check_demultiplexlog_file(self):
    '''read the log file containing stderr and stdout to see if any errors were reported'''
        #open log file
        logfile=open(self.runfolders+"/"+self.runfolder+"/"+self.demultiplexed,'r')
        
        count=0
        lastline=""
        for i in logfile:
            count=count+1
            lastline=i
        #print "line count = "+str(count)
        
        if  "Processing completed with 0 errors and 0 warnings." in lastline:
            self.script_logfile.write("demultiplexing complete\n")
            self.email_subject="MOKAPIPE ALERT: Demultiplexing complete"
            self.email_message="run:\t"+self.runfolder+"\nPlease see log file at: "+self.runfolders+"/"+self.runfolder+"/"+self.demultiplexed
            self.send_an_email()
            
            #update smartsheet
            self.smartsheet_demultiplex_complete()

            self.script_logfile.close()
            self.rename=self.rename+self.runfolder
            os.rename(self.logfile_name,self.script_logfile_path+self.now+"_"+self.rename+".txt")

            

        else:
            self.script_logfile.write("ERROR - DEMULTIPLEXING UNSUCCESFULL - please see "+self.runfolders+"/"+self.runfolder+"/"+self.demultiplexed+"\n")
            self.email_subject="MOKAPIPE ALERT: DEMULTIPLEXING FAILED"
            self.email_priority=1
            self.email_message="run:\t"+self.runfolder+"\nPlease see log file at: "+self.runfolders+"/"+self.runfolder+"/"+self.demultiplexed
            self.send_an_email()
    
    def send_an_email(self):
        #body = self.runfolder
        self.script_logfile.write("Sending an email to..... " +self.me)
        #msg  = 'Subject: %s\n\n%s' % (self.email_subject, self.email_message)
        m = Message()
        #m['From'] = self.me
        #m['To'] = self.you
        m['X-Priority'] = str(self.email_priority)
        m['Subject'] = self.email_subject
        m.set_payload(self.email_message)
        
        
        server = smtplib.SMTP(host = self.host,port = self.port,timeout = 10)
        server.set_debuglevel(1)
        server.starttls()
        server.ehlo()
        server.login(self.user, self.pw)
        server.sendmail(self.me, [self.you], m.as_string())
        self.script_logfile.write("................email sent\n")

    def test_bcl2fastq(self):
        command = self.bcl2fastq

        # run the command, redirecting stderror to stdout
        proc = subprocess.Popen([command], stderr=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)
        
        # capture the streams (err is redirected to out above)
        (out, err) = proc.communicate()
        
        if "BCL to FASTQ file converter" not in err:
            self.email_subject="MOKAPIPE ALERT: ERROR - PRESENCE OF BCL2FASTQ TEST FAILED"
            self.email_priority=1
            self.email_message="The test to check if bcl2fastq is working ("+command+") failed"
            self.send_an_email()
            raise Exception, "bcl2fastq not installed"

        # write this to the log file
        self.script_logfile.write("bcl2fastq check passed\n")

    def smartsheet_demultiplex_in_progress(self):
        '''This function updates smartsheet to say that demultiplexing is in progress'''
        
        # take current timestamp for recieved
        self.smartsheet_now = str('{:%Y-%m-%d}'.format(datetime.datetime.utcnow()))
        
        # #uncomment this block if want to get the column ids for a new sheet
        ########################################################################
        # # Get all columns.
        # url=self.url+"/columns"
        # r = requests.get(url, headers=self.headers)
        # response= r.json()
        # 
        # # get the column ids
        # for i in response['data']:
        #     print i['title'], i['id']
        ########################################################################
        
        #capture the NGS run number and count
        count = 0
        with open(self.samplesheet,'r') as samplesheet:
            for line in samplesheet:
                if line.startswith("NGS"):
                    count=count+1
                    runnumber=line.split("_")[0]
        
        # set all values to be inserted
        payload='{"cells": [{"columnId": '+self.ss_title+', "value": "Demultiplex '+runnumber+'"}, {"columnId": '+self.ss_description+', "value": "Demultiplex"}, {"columnId": '+self.ss_samples+', "value": '+str(count)+'},{"columnId": '+self.ss_status+', "value": "In Progress"},{"columnId": '+self.ss_priority+', "value": "Medium"},{"columnId": '+self.ss_assigned+', "value": "aledjones@nhs.net"},{"columnId": '+self.ss_received+', "value": "'+str(self.smartsheet_now)+'"}],"toBottom":true}'
        
        # create url for uploading a new row
        url=self.url+"/rows"
        
        # add the row using POST 
        r = requests.post(url,headers=self.headers,data=payload)
        
        # capture the row id
        response= r.json()
        print response
        for i in response["result"]:
            if i == "id":
                self.rowid=response["result"][i]

        #check the result of the update attempt
        for i in response:  
            if i == "message":
                if response[i] =="SUCCESS":
                    self.script_logfile.write("smartsheet updated to say in progress\n")
                else:
                    #send an email if the update failed
                    self.email_subject="MOKAPIPE ALERT: SMARTSHEET WAS NOT UPDATED"
                    self.email_message="Smartsheet was not updated to say demultiplexing is inprogress"
                    self.send_an_email()
                    self.script_logfile.write("smartsheet NOT updated at in progress step\n"+str(response))

    def smartsheet_demultiplex_complete(self):
        '''update smartsheet to say demultiplexing is complete (add the completed date and calculate the duration (in days) and if met TAT)'''
        #build url tp read a row
        url='https://api.smartsheet.com/2.0/sheets/'+str(self.sheetid)+'/rows/'+str(self.rowid)
        #get row
        r = requests.get(url, headers=self.headers)
        #read response in json
        response= r.json()
        #loop through each column and extract the recieved date
        for col in response["cells"]:
            if str(col["columnId"]) == self.ss_received:
                recieved=datetime.datetime.strptime(col['value'], '%Y-%m-%d')
        
        # take current timestamp
        self.smartsheet_now = str('{:%Y-%m-%d}'.format(datetime.datetime.utcnow()))
        now=datetime.datetime.strptime(self.smartsheet_now, '%Y-%m-%d')
        
        #calculate the number of days taken (add one so if same day this counts as 1 day not 0)
        duration = (now-recieved).days+1
        
        # set flag to show if TAT was met.
        TAT=1
        if duration > 4:
            TAT=0
        
        #build payload used to update the row
        payload = '{"id":"'+str(self.rowid)+'", "cells": [{"columnId":"'+ str(self.ss_duration)+'","value":"'+str(duration)+'"},{"columnId":"'+ str(self.ss_metTAT)+'","value":"'+str(TAT)+'"},{"columnId":"'+ str(self.ss_status)+'","value":"Complete"},{"columnId": '+self.ss_completed+', "value": "'+str(self.smartsheet_now)+'"}]}' 
        
        #build url to update row
        url=self.url+"/rows"
        update_OPMS = requests.request("PUT", url, data=payload, headers=self.headers)
        
        #check the result of the update attempt
        response= update_OPMS.json()
        print response
        for i in response:
            if i == "message":
                if response[i] =="SUCCESS":
                    self.script_logfile.write("smartsheet updated to say complete\n")
                else:
                    #send an email if the update failed
                    self.email_subject="MOKAPIPE ALERT: SMARTSHEET WAS NOT UPDATED"
                    self.email_message="Smartsheet was not updated to say demultiplexing was completed"
                    self.send_an_email()
                    self.script_logfile.write("smartsheet NOT updated at complete step\n"+str(response))



if __name__ == '__main__':
    # Create instance of get_list_of_runs
    runs = get_list_of_runs()
    # call function
    runs.loop_through_runs()
