#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2016 <+YOU OR YOUR COMPANY+>.
#
# This is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this software; see the file COPYING.  If not, write to
# the Free Software Foundation, Inc., 51 Franklin Street,
# Boston, MA 02110-1301, USA.
#
from __future__ import print_function#print without newline print('.', end="")
import numpy
from gnuradio import gr
import pmt,functools,csv,md5,collections,copy,sqlite3,atexit,time,re,sys
#old imports: folium
from datetime import datetime
from datetime import timedelta
import multirds.chart as chart
from multirds.tmc_classes import tmc_dict,tmc_message,language

from PyQt4 import Qt, QtCore, QtGui
import pprint,code,pickle#for easier testing
pp = pprint.PrettyPrinter()
import cProfile, pstats, StringIO #for profiling
pr = cProfile.Profile()

#from threading import Timer#to periodically save DB

from PyQt4.QtCore import QObject, pyqtSignal
from bitstring import BitArray

#language="de"#currently supported: de, en (both partially) #defined in tmc_classes.py


class rds_parser_table_qt_Signals(QObject):
    DataUpdateEvent = QtCore.pyqtSignal(dict)
    def __init__(self, parent=None):
        super(QtCore.QObject, self).__init__()
class rds_parser_table_qt(gr.sync_block):#START
    """
    docstring for block qtguitest
    """
    def goodbye(self):
        self.clean_data_and_commit_db()
        print("quitting rds parser table, closing db")
        if self.writeDB:
        #self.db.commit()
            self.db.close()
    def __init__(self,signals,nPorts,slot,freq,log,debug,workdir,writeDB):
        gr.sync_block.__init__(self,
            name="RDS Table",
            in_sig=None,
            out_sig=None)
        if nPorts==1:
            self.message_port_register_in(pmt.intern('in'))
            self.set_msg_handler(pmt.intern('in'), functools.partial(self.handle_msg, port=0))
        else:
            for i in range(nPorts):
                self.message_port_register_in(pmt.intern('in%d'%i))
                self.set_msg_handler(pmt.intern('in%d'%i), functools.partial(self.handle_msg, port=i))
        self.nPorts=nPorts
        self.message_port_register_in(pmt.intern('freq'))
        self.set_msg_handler(pmt.intern('freq'), self.set_freq)
        self.message_port_register_out(pmt.intern('ctrl'))
        self.message_port_register_out(pmt.intern('tmc_raw'))
        
        self.TMC_without_CT=False
        self.log=log
        self.debug=debug
        self.writeDB=writeDB
        self.signals=signals
        self.RDS_data={}
        self.change_freq_tune=slot
        self.tuning_frequency=int(freq)
        self.printcounter=0
        self.ODA_application_names={}
        self.TMC_data={}
        self.IH_data={}
        self.decoder_frequencies={}
        self.decoders=[]
        for i in range(nPorts):
            self.decoders.append({'synced':False,'freq':None,'PI':"",'pilot_strength':0})
        #self.decoder_synced={}
        #self.colorder=['ID','freq','name','PTY','AF','time','text','quality','buttons']
        self.colorder=['ID','freq','name','buttons','PTY','AF','time','text','quality','pilot_strength','RT+']
        self.workdir=workdir
        self.PI_dict={}#contains PI:numpackets (string:integer)
        self.tmc_messages=tmc_dict()

        if self.writeDB:
                #create new DB file
            db_name=workdir+'RDS_data'+datetime.now().strftime("%Y%m%d_%H%M%S")+'.db'
            db=sqlite3.connect(db_name, check_same_thread=False)
            self.db=db
            #create tables
            try:
                db.execute('''CREATE TABLE stations
                      (PI text PRIMARY KEY UNIQUE,PSN text, freq real, PTY text,TP integer)''')
                db.execute('''CREATE TABLE groups
                      (time text,PI text,PSN text, grouptype text,content blob)''')
                db.execute('''CREATE TABLE data
                      (time text,PI text,PSN text, dataType text,data blob)''')
                db.execute('''CREATE TABLE grouptypeCounts
                      (PI text,grouptype text,count integer,unique (PI, grouptype))''')
              #  db.execute('''CREATE TABLE TMC
              #        (hash text PRIMARY KEY UNIQUE,time text,PI text, F integer,event integer,location integer,DP integer,div integer,dir integer,extent integer,text text,multi text,rawmgm text)''')
                db.commit()

            except sqlite3.OperationalError:
                print("ERROR: tables already exist")

            #self.dbc.execute('''CREATE TABLE rtp
        #     (time text,PI text,rtp_string text)''')
        reader = csv.reader(open(self.workdir+'RDS_ODA-AIDs_names_only.csv'), delimiter=',', quotechar='"')
        reader.next()#skip header
        for row in reader:
            self.ODA_application_names[int(row[0])]=row[1]
        #read location code list:
        reader = csv.reader(open(self.workdir+'LCL15.1.D-160122_utf8.csv'), delimiter=';', quotechar='"')
        reader.next()#skip header
        self.lcl_dict=dict((int(rows[0]),rows[1:]) for rows in reader)
        #read RT+ class name list:
        reader = csv.reader(open(self.workdir+'RTplus_classnames.csv'), delimiter=',', quotechar='"')
        reader.next()#skip header
        self.rtp_classnames=dict((int(rows[0]),rows[1]) for rows in reader)
        #read TMC-event list
        reader = csv.reader(open(self.workdir+'event-list_with_forecast_sort.csv'), delimiter=',', quotechar='"')
        reader.next()#skip header
        self.ecl_dict=dict((int(rows[0]),rows[1:]) for rows in reader)
        #Code,Text  CEN-English,Text (German),Text (German) kein Quantifier,Text (Quantifier = 1),Text (Quantifier >1),N,Q,T,D,U,C,R ,Comment
        #N:nature (blank): information, F:forecast, S:silent
        #Q:quantifier type: (0..12) or blank (no quantifier)
        #T:duration type: D:dynamic, L:long lasting, in brackets or if time-of-day quantifier (no 7) is used in message -> no display, only for management
        #D:direction: 1:unidirectional, 2:bidirectional
        #U:urgency: blank: normal, X:extremely urgent, U:urgent
        #C: update class:

        #read update classes
        reader = csv.reader(open(self.workdir+'tmc_update_class_names.csv'), delimiter=',', quotechar='"')
        reader.next()#skip header, "code(C),english,german"
        if language=="de":
            self.tmc_update_class_names=dict((int(rows[0]),rows[2]) for rows in reader)#german names
        else:
            self.tmc_update_class_names=dict((int(rows[0]),rows[1]) for rows in reader)#english names
        #read supplementary information code list
        reader = csv.reader(open(self.workdir+'label6-supplementary-information-codes.csv'), delimiter=',', quotechar='"')
        reader.next()#skip header, "code,english,german"
        if language=="de":
            self.label6_suppl_info=dict((int(rows[0]),rows[2]) for rows in reader)#german
        else:
            self.label6_suppl_info=dict((int(rows[0]),rows[1]) for rows in reader)#english
        #read PTY list
        f=open(self.workdir+'pty-list.csv')
        reader = csv.reader(f, delimiter=',', quotechar='"')
        reader.next()#skip header
        self.pty_dict=dict((int(rows[0]),rows[1]) for rows in reader)
        f.close()
        self.minute_count=0
        self.minute_count_max=0
        self.minute_count_timer=time.time()
        self.save_data_timer=time.time()

        atexit.register(self.goodbye)

    def clean_data_and_commit_db(self):
        for PI in self.PI_dict:
            self.PI_dict[PI]-=1
        #print(self.PI_dict)
        if self.writeDB:
            self.db.commit()
    def update_freq(self):
            #  "&#9;" is a tab character
        message_string="decoder frequencies:"
        for num in self.decoder_frequencies:
            freq=self.decoder_frequencies[num]
            pilot_strength=self.decoders[num]['pilot_strength']
            if self.decoders[num]['synced']:
                message_string+="<span style='color:green'>&emsp; %i:%0.1fM (%i dB)</span>"% (num,freq/1e6,pilot_strength)
                #print("'color:green'>%i:%0.1fM</span>"% (num,freq/1e6))
            else:#elif self.decoders[num]['synced']==False:
                #print("'color:red'>%i:%0.1fM</span>"% (num,freq/1e6))
                message_string+="<span style='color:red'>&emsp; %i:%0.1fM (%i dB)</span>"% (num,freq/1e6,pilot_strength)
        message_string+="&emsp; tuned frequency:%0.1fM"%(self.tuning_frequency/1e6)
        self.signals.DataUpdateEvent.emit({'decoder_frequencies':message_string})
        #print(message_string)
        #self.signals.DataUpdateEvent.emit({'row':decoder_num,'freq':freq_str})
        #print("nr:%i freq:%s"%(tgtnum,freq_str))
    def set_freq_tune(self,freq):
        self.tuning_frequency=int(freq)
        self.update_freq()
    def set_freq(self,msg):
        m = pmt.symbol_to_string(msg)
        decoder_num=int(m.split()[0])-1#msgs are 1-indexed, decoder_num is 0-indexed
        freq_str=m.split()[1]
        try:
            freq=float(freq_str)
            self.decoder_frequencies[decoder_num]=freq
            freq_str="%i:%0.1fM"% (decoder_num,freq/1e6)
        except ValueError:
            pass#leave string as is
        self.update_freq()
    def init_data_for_PI(self,PI):
        self.RDS_data[PI]={}
        #self.RDS_data[PI]["blockcounts"]={}# no defaults (works aswell)
        #defaults are to keep colors in piechart  consistent between stations:

        coverage_area={"0":"local,","1":"international,","2":"national,","3":"supranational,"}
        pi_str=""
        if list(PI)[1] in "456789ABCDEF":
            pi_str+="regional, "
        else:
            pi_str+=coverage_area[list(PI)[1]]
        bundeslaender={"0":"Baden-Württemberg","1":"Bayern","2":"Berlin","3":"Brandenburg","4":"Bremen und Bremerhaven",
   "5":"Hamburg","6":"Hessen","7":"Mecklenburg-Vorpommern","8":"Niedersachsen","9":"Nordrhein-Westfalen","A":"Rheinland-Pfalz",
   "B":"Saarland","C":"Sachsen","D":"Sachsen-Anhalt","E":"Schleswig-Holstein","F":"Thüringen"}
        if list(PI)[0] in "D1":
            pi_str+="germany?, "
            pi_str+=bundeslaender[list(PI)[2]]+", "
            pi_str+="NR:"+list(PI)[3]
        self.RDS_data[PI]["CC"]=list(PI)[0]
        self.RDS_data[PI]["PI-meaning"]=pi_str
        self.RDS_data[PI]["blockcounts"]={"0A":0,"1A":0,"2A":0,"3A":0,"4A":0,"6A":0,"8A":0,"12A":0,"14A":0}
        self.RDS_data[PI]["blockcounts"]["any"]=0
        self.RDS_data[PI]["AID_list"]={}
        self.RDS_data[PI]["PSN"]="_"*8
        self.RDS_data[PI]["PSN_valid"]=[False]*8
        self.RDS_data[PI]["AF"]={"set":set(),"rxset":set()}
        self.RDS_data[PI]["TP"]=-1
        self.RDS_data[PI]["TA"]=-1
        self.RDS_data[PI]["PTY"]=""
        self.RDS_data[PI]["DI"]=[2,2,2,2]
        self.RDS_data[PI]["internals"]={"last_rt_tooltip":"","unfinished_TMC":{},"last_valid_rt":"","last_valid_psn":"","RT_history":[]}
        self.RDS_data[PI]["time"]={"timestring":"88:88","datestring":"00-00-0000","datetime":None}
        self.RDS_data[PI]["wrong_block_ratio"]=1#100%
    def handle_msg(self, msg, port):#port from 0 to 3
        if pmt.to_long(pmt.car(msg))==1L:
            synced=pmt.to_python(pmt.cdr(msg))
            #print("port:%i, data: %s"%(port,data))
            self.decoders[port]['synced']=synced
            self.update_freq()
            PI=self.decoders[port]['PI']
            if self.RDS_data.has_key(PI) and not synced:
                dots="."*self.RDS_data[PI]["blockcounts"]["any"]
                wrong_block_ratio=1#100%
                self.RDS_data[PI]["wrong_block_ratio"]=wrong_block_ratio
                self.signals.DataUpdateEvent.emit({'PI':PI,'wrong_block_ratio':wrong_block_ratio,'dots':dots})
        elif pmt.to_long(pmt.car(msg))==2L:
            wrong_block_ratio=pmt.to_python(pmt.cdr(msg))
            PI=self.decoders[port]['PI']
            if self.RDS_data.has_key(PI):
                dots="."*self.RDS_data[PI]["blockcounts"]["any"]
                self.RDS_data[PI]["wrong_block_ratio"]=wrong_block_ratio
                self.signals.DataUpdateEvent.emit({'PI':PI,'wrong_block_ratio':wrong_block_ratio,'dots':dots})
        elif pmt.to_long(pmt.car(msg))==3L: #carrier quality message
            pilot_strength=pmt.to_long(pmt.cdr(msg))
            self.decoders[port]['pilot_strength']=pilot_strength
            self.update_freq()
            PI=self.decoders[port]['PI']
            if self.RDS_data.has_key(PI):            
                self.signals.DataUpdateEvent.emit({'PI':PI,'pilot_strength':pilot_strength})
        else: #elif pmt.to_long(pmt.car(msg))==0L
            array=pmt.to_python(msg)[1]

            if time.time()-self.save_data_timer > 10:#every 10 seconds
                self.save_data_timer=time.time()
                self.clean_data_and_commit_db()

            if time.time()-self.minute_count_timer > 3:#every 3 second
                self.minute_count_max=self.minute_count
                self.signals.DataUpdateEvent.emit({'group_count':self.minute_count,'group_count_max':self.minute_count_max})
                self.minute_count=0
                self.minute_count_timer=time.time()
            #pr.enable()#disabled-internal-profiling
            self.minute_count+=1
            #self.signals.DataUpdateEvent.emit({'group_count':self.minute_count,'group_count_max':self.minute_count_max})
            if self.writeDB:
                #db=sqlite3.connect(self.db_name)
                db=self.db


            groupNR=array[2]&0b11110000
            groupVar=array[2]&0b00001000
            if (groupVar == 0):
                groupType=str(groupNR >> 4)+"A"
            else:
                groupType=str(groupNR >> 4)+"B"
            #if self.debug:
                #PI=str(port)+"_%02X%02X" %(array[0],array[1])
            #else:
                #PI="%02X%02X" %(array[0],array[1])
            PI="%02X%02X" %(array[0],array[1])
            self.decoders[port]['PI']=PI
            TP=(array[2]>>2)&0x1
            block2=(array[2]<<8)|(array[3]) #block2
            PTY=(block2>>5)&0x1F
            #wrong_blocks=int(array[12])

            try:
                self.PI_dict[PI]+=1
            except KeyError:
                pass

            if not self.RDS_data.has_key(PI):#station invalid/new
                if not self.PI_dict.has_key(PI):#1st group
                    self.PI_dict[PI]=1
                    return#dont decode further if not yet valid
                elif self.PI_dict[PI]>2:#count station as valid if more than 2 packets received
                    self.init_data_for_PI(PI)#initialize dict for station
                    if self.log:
                        print("found station %s"%PI)
                else:
                    return#dont decode further if not yet valid

            if self.decoder_frequencies.has_key(port):
                freq=self.decoder_frequencies[port]
                freq_str="%i:%0.1fM"% (port,freq/1e6)
                self.RDS_data[PI]["tuned_freq"]=freq
                #self.signals.DataUpdateEvent.emit({'PI':PI,'freq':freq_str})
            if self.RDS_data[PI]["blockcounts"].has_key(groupType):
                self.RDS_data[PI]["blockcounts"][groupType] +=1 #increment
            else:
                self.RDS_data[PI]["blockcounts"][groupType] = 1 #initialize (1st group of this type)
            self.RDS_data[PI]["blockcounts"]["any"]+=1
            if self.RDS_data[PI]["blockcounts"]["any"]==5:
                self.RDS_data[PI]["blockcounts"]["any"]=0
                if self.writeDB:
                    t=(str(PI),groupType,self.RDS_data[PI]["blockcounts"][groupType])#TODO only update DB every few seconds
                    db.execute("INSERT OR REPLACE INTO grouptypeCounts (PI,grouptype,count) VALUES (?,?,?)",t)
            dots="."*self.RDS_data[PI]["blockcounts"]["any"]
            self.RDS_data[PI]["TP"]=TP
            self.RDS_data[PI]["PTY"]=self.pty_dict[PTY]

            self.signals.DataUpdateEvent.emit({'PI':PI,'PTY':self.pty_dict[PTY],'TP':TP,'wrong_block_ratio':self.RDS_data[PI]["wrong_block_ratio"],'dots':dots})
            #self.signals.DataUpdateEvent.emit({'PI':PI,'PTY':self.pty_dict[PTY],'TP':TP})



            #add any received groups to DB (slow)
            #content="%02X%02X%02X%02X%02X" %(array[3]&0x1f,array[4],array[5],array[6],array[7])
            #t=(str(datetime.now()),PI,self.RDS_data[PI]["PSN"],groupType,content)
            #db.execute("INSERT INTO groups  VALUES (?,?,?,?,?)",t)

            if (groupType == "0A"):#AF PSN
                adr=array[3]&0b00000011
                segment=self.decode_chars(chr(array[6])+chr(array[7]))
                d=(array[3]>>2)&0x1
                self.RDS_data[PI]["DI"][3-adr]=d#decoder information
                #DI[0]=d0     0=Mono                  1=Stereo
                #d1           Not artificial head     Artificial head
                #d2           Not compressed          Compressed
                #d3           Static PTY              Dynamic PTY
                TA=(array[3]>>4)&0x1
                MS=(array[3]>>3)&0x1
                self.RDS_data[PI]["TA"]=TA
                #style='font-family:Courier New;color:%s'
                flag_string="<span style=''>TP:%i, TA:%i, MS:%i, DI:%s</span>"%(TP,TA,MS,str(self.RDS_data[PI]["DI"]))
                pty_colored=self.RDS_data[PI]["PTY"]
                if TP==1:
                    if TA==1:
                        color="red"
                    elif TA==0:
                        color="green"
                    else:
                        color="yellow"
                    pty_colored="<span style='color:%s'>%s</span>"%(color,self.RDS_data[PI]["PTY"])

                self.signals.DataUpdateEvent.emit({'row':port,'PI':PI,'flags':flag_string,'PTY':pty_colored})

                #224 1110 0000 = no AF
                #225 1110 0001 = 1AF
                #249 1111 1001 = 25AF
                fillercode=205#1100 1101
                if not self.RDS_data[PI]["AF"].has_key("main") and self.RDS_data[PI].has_key("tuned_freq"):
                #if self.RDS_data[PI].has_key("tuned_freq"):#update main freq even if one exists -> DB problem
                    freq=self.decode_AF_freq(array[4])
                    if freq==self.RDS_data[PI]["tuned_freq"]:
                        self.RDS_data[PI]["AF"]["main"]=freq
                        if self.log:
                            print("main frequency found in 0A: station:%s, freq:%0.1fM"% (self.RDS_data[PI]["PSN"],freq/1e6))
                        freq_str="0A:%0.1fM"% (freq/1e6)
                        self.signals.DataUpdateEvent.emit({'PI':PI,'freq':freq_str})
                        t=(PI,self.RDS_data[PI]["PSN"],float(freq),self.RDS_data[PI]["PTY"],int(self.RDS_data[PI]["TP"]))
                        if self.writeDB:
                            db.execute("INSERT INTO stations (PI,PSN,freq,PTY,TP) VALUES (?,?,?,?,?)",t)
                    freq=self.decode_AF_freq(array[5])
                    if freq==self.RDS_data[PI]["tuned_freq"]:
                        self.RDS_data[PI]["AF"]["main"]=freq
                        if self.log:
                            print("main frequency found in 0A: station:%s, freq:%0.1fM"% (self.RDS_data[PI]["PSN"],freq/1e6))
                        freq_str="0A:%0.1fM"% (freq/1e6)
                        self.signals.DataUpdateEvent.emit({'PI':PI,'freq':freq_str})
                        t=(PI,self.RDS_data[PI]["PSN"],float(freq),self.RDS_data[PI]["PTY"],int(self.RDS_data[PI]["TP"]))
                        if self.writeDB:
                            db.execute("INSERT INTO stations (PI,PSN,freq,PTY,TP) VALUES (?,?,?,?,?)",t)
                if self.RDS_data[PI].has_key("tuned_freq") :#TODO add secondary freqs
                    freq=self.decode_AF_freq(array[4])
                    diff=abs(freq-self.RDS_data[PI]["tuned_freq"])
                    if diff<100000:
                        self.RDS_data[PI]["AF"]["rxset"].add(freq)
                    freq=self.decode_AF_freq(array[5])
                    diff=abs(freq-self.RDS_data[PI]["tuned_freq"])
                    if diff<100000:
                        self.RDS_data[PI]["AF"]["rxset"].add(freq)

                if(array[4]>= 224 and array[4]<= 249):
                    #print("AF1 detected")
                    self.RDS_data[PI]["AF"]['number']=array[4]-224
                    #self.RDS_data[PI]["AF"]['main']=self.decode_AF_freq(array[5])
                    self.signals.DataUpdateEvent.emit({'row':port,'PI':PI,'AF':self.RDS_data[PI]["AF"]})
                if(array[5]>= 224 and array[5]<= 249):
                    print("AF2 detected (shouldn't happen) %s"%array[5])


                #add frequencies to set
                self.RDS_data[PI]["AF"]["set"].add(self.decode_AF_freq(array[4]))
                self.RDS_data[PI]["AF"]["set"].add(self.decode_AF_freq(array[5]))
                try:
                    self.RDS_data[PI]["AF"]["set"].remove(0)#remove control characters
                except KeyError:
                    pass

                name_list=list(self.RDS_data[PI]["PSN"])
                if (name_list[adr*2:adr*2+2]==list(segment)):#segment already there
                    segmentcolor="green"
                elif(name_list[adr*2:adr*2+2]==['_']*2): #segment new
                    segmentcolor="orange"
                    name_list[adr*2:adr*2+2]=segment
                else:#name changed (böse)
                    segmentcolor="red"
                    name_list=['_']*8 #reset name
                    name_list[adr*2:adr*2+2]=segment
                    #reset stored text:
                    self.RDS_data[PI]["PSN"]="_"*8
                    self.RDS_data[PI]["PSN_valid"]=[False]*8
                self.RDS_data[PI]["PSN_valid"][adr*2:adr*2+2]=[True] *2
                self.RDS_data[PI]["PSN"]="".join(name_list)
                #determine if text is valid
                valid=True
                for i in range(0,8):
                    if (not self.RDS_data[PI]["PSN_valid"][i]):
                        valid = False
                if(valid):
                    #textcolor="black"
                    textcolor=""#use default color (white if background is black)
                    if not self.RDS_data[PI]["internals"]["last_valid_psn"]==self.RDS_data[PI]["PSN"]:#ignore duplicates
                        t=(str(datetime.now()),PI,self.RDS_data[PI]["PSN"],"PSN_valid",self.RDS_data[PI]["PSN"])
                        if self.writeDB:
                            db.execute("INSERT INTO data (time,PI,PSN,dataType,data) VALUES (?,?,?,?,?)",t)
                        t=(self.RDS_data[PI]["PSN"],PI)
                        if self.writeDB:
                            db.execute("UPDATE OR IGNORE stations SET PSN=? WHERE PI IS ?",t)
                        self.RDS_data[PI]["internals"]["last_valid_psn"]=self.RDS_data[PI]["PSN"]
                else:
                    textcolor="gray"
                formatted_text=self.color_text(self.RDS_data[PI]["PSN"],adr*2,adr*2+2,textcolor,segmentcolor)
                self.signals.DataUpdateEvent.emit({'row':port,'PI':PI,'PSN':formatted_text})
            elif (groupType == "1A"):#PIN programme item number
                #wer nutzt 1A gruppen?
                #antenne1: variants: 0(ECC),
                PIN=(array[6]<<8)|(array[7])
                SLC=(array[4]<<8)|(array[5])&0xfff#slow labeling code
                radio_paging=array[3]&0x1f
                LA=array[4]>>7#linkage actuator
                variant=(array[4]>>4)&0x7
                PIN_day=(PIN>>11)&0x1f
                PIN_hour=(PIN>>6)&0x1f
                PIN_minute=PIN&0x3f
                PIN_valid= PIN_day in range(1,32) and PIN_hour in range(0,24) and PIN_minute in range(0,60)
                if PIN_valid:
                    self.RDS_data[PI]["PIN"]=[PIN_day,PIN_hour,PIN_minute]
                    data_string="variant:%i,SLC:%04X,PIN (valid):%s "%(variant,SLC,str([PIN_day,PIN_hour,PIN_minute]))
                else:
                    data_string="variant:%i,SLC:%04X,PIN:%04X "%(variant,SLC,PIN)
                #%02X%02X%02X%02X%02X

                t=(str(datetime.now()),PI,self.RDS_data[PI]["PSN"],"PIN",data_string)
                if self.writeDB:
                    db.execute("INSERT INTO data (time,PI,PSN,dataType,data) VALUES (?,?,?,?,?)",t)
                if self.debug and not variant==0:#print if not seen before
                    print("PI:%s PSN:%s uses variant %i of 1A"%(PI,self.RDS_data[PI]["PSN"],variant))
                if variant==0:
                    paging=array[4]&0xf
                    extended_country_code=array[5]
                    self.RDS_data[PI]["ECC"]=extended_country_code
                    if self.debug:
                        print("1A variant 0: PI:%s PSN:%s,ECC:%s"%(PI,self.RDS_data[PI]["PSN"],hex(extended_country_code)))
                elif variant==1:
                    TMC_info=SLC
                elif variant==2:
                    paging_info=SLC
                elif variant==3:
                    language_codes=SLC
                    if self.debug:
                        print("PI:%s PSN:%s,language_codes:%s"%(PI,self.RDS_data[PI]["PSN"],hex(language_codes)))
                elif variant==6:
                    #for use by broadcasters
                    if self.debug:
                        print("PI:%s PSN:%s uses variant 6 of 1A"%(PI,self.RDS_data[PI]["PSN"]))
                elif variant==7:
                    ESW_channel_identification=SLC
                #end of 1A decode
            elif (groupType == "2A"):#RT radiotext
                if(not self.RDS_data[PI].has_key("RT_0")):#initialize variables
                    self.RDS_data[PI]["RT_0"]={"RT":"_"*64,"RT_valid":[False]*64,"RT_all_valid":False}
                    self.RDS_data[PI]["RT_1"]={"RT":"_"*64,"RT_valid":[False]*64,"RT_all_valid":False}
                    #self.RDS_data[PI]["RT"]="_"*64
                    #self.RDS_data[PI]["RT_valid"]=[False]*64
                    #self.RDS_data[PI]["RT_all_valid"]=False
                    self.RDS_data[PI]["RT_last_ab_flag"]=2

                adr=    array[3]&0b00001111
                ab_flag=(array[3]&0b00010000)>>4

                self.RDS_data[PI]["RT_last_ab_flag"] =ab_flag

                #segment=self.decode_chars(chr(array[4])+chr(array[5])+chr(array[6])+chr(array[7]))
                segment=chr(array[4])+chr(array[5])+chr(array[6])+chr(array[7])#EDIT:latedecode

                #print("RT:adress: %d, segment:%s"%(adr,segment))
                #self.signals.DataUpdateEvent.emit({'col':5,'row':port,'PI':PI,'groupType':groupType,'adress':adr,'segment':segment})
                text_list=list(self.RDS_data[PI]["RT_"+str(ab_flag)]["RT"])
                #determine text length:
                try:
                    text_end=text_list.index('\r')
                except ValueError:
                    text_end=64 #assume whole string is important
                    pass
                predicted=False
                if (text_list[adr*4:adr*4+4]==list(segment)):#segment already there
                    segmentcolor="green"
                elif (text_list[adr*4:adr*4+4]==['_']*4):#segment new
                    segmentcolor="orange"
                    text_list[adr*4:adr*4+4]=segment
                else:
                    segmentcolor="red"
                    text_list=['_']*64 #clear text
                    text_list[adr*4:adr*4+4]=segment
                    #reset stored text:
                    self.RDS_data[PI]["RT_"+str(ab_flag)]["RT"]="_"*64
                    self.RDS_data[PI]["RT_"+str(ab_flag)]["RT_valid"]=[False]*64
                    #predict RT from last texts:
                    for rt in self.RDS_data[PI]["internals"]["RT_history"]:
                        if rt[adr*4:adr*4+4]==list(segment):
                            self.RDS_data[PI]["RT_"+str(ab_flag)]["RT"]="".join(rt)
                            predicted=True

                self.RDS_data[PI]["RT_"+str(ab_flag)]["RT_valid"][adr*4:adr*4+4]=[True] *4
                if not predicted:
                    self.RDS_data[PI]["RT_"+str(ab_flag)]["RT"]="".join(text_list)

                #determine if (new) text is valid
                self.RDS_data[PI]["RT_"+str(ab_flag)]["RT_all_valid"]=True
                for i in range(0,text_end):
                    if (not self.RDS_data[PI]["RT_"+str(ab_flag)]["RT_valid"][i]):
                        self.RDS_data[PI]["RT_"+str(ab_flag)]["RT_all_valid"] = False
                if(self.RDS_data[PI]["RT_"+str(ab_flag)]["RT_all_valid"]):
                    #textcolor="black"
                    textcolor=""#use default color (white if background is black)
                    l=list(self.RDS_data[PI]["RT_"+str(ab_flag)]["RT"])
                    rt="".join(l[0:text_end])#remove underscores(default symbol) after line end marker
                    if not self.RDS_data[PI]["internals"]["last_valid_rt"]==rt:#ignore duplicates #TODO add 2nd order duplicates ABAB
                        self.RDS_data[PI]["internals"]["RT_history"].append(l)
                        if len(self.RDS_data[PI]["internals"]["RT_history"])>10:#only store last 10 RTs
                            self.RDS_data[PI]["internals"]["RT_history"].pop(0)
                        if self.writeDB:
                            t=(str(datetime.now()),PI,self.RDS_data[PI]["PSN"],"RT",self.decode_chars(rt))
                            db.execute("INSERT INTO data (time,PI,PSN,dataType,data) VALUES (?,?,?,?,?)",t)
                        self.RDS_data[PI]["internals"]["last_valid_rt"]=rt
                        try:#save rt+ if it exist
                            if self.writeDB:
                                t=(str(datetime.now()),PI,self.RDS_data[PI]["PSN"],"RT+",self.decode_chars(str(self.RDS_data[PI]["RT+"])))
                                db.execute("INSERT INTO data (time,PI,PSN,dataType,data) VALUES (?,?,?,?,?)",t)
                        except KeyError:
                            pass#no rt+ -> dont save
                else:
                    textcolor="gray"
                display_text=self.decode_chars(self.RDS_data[PI]["RT_"+str(ab_flag)]["RT"].split("\r")[0])
                formatted_text=self.color_text(display_text,adr*4,adr*4+4,textcolor,segmentcolor)
                rtcol=self.colorder.index('text')
                self.signals.DataUpdateEvent.emit({'col':rtcol,'row':port,'PI':PI,'string':formatted_text})

            elif (groupType == "3A"):#ODA announcements (contain application ID "AID")
                AID=int((array[6]<<8)|(array[7]))#combine 2 bytes into 1 block
                app_data=int((array[4]<<8)|(array[5]))#content defined by ODA-app
                app_group_raw=int(array[3]&0x1f) #group type in which this app is sent
                if (app_group_raw&0x1 == 0):
                    app_group=str(app_group_raw >> 1)+"A"
                else:
                    app_group=str(app_group_raw >> 1)+"B"

                if not self.RDS_data[PI]["AID_list"].has_key(AID):#new ODA found
                    try:
                        app_name=self.ODA_application_names[AID]
                    except KeyError:
                        if self.debug:
                            print("ERROR: ODA-app-id (AID) '%i' not found in list on station %s, app group:%s"%(AID,app_group,PI))
                        app_name="unknown"
                    self.RDS_data[PI]["AID_list"][AID]={}
                    self.RDS_data[PI]["AID_list"][AID]["groupType"]=app_group
                    self.RDS_data[PI]["AID_list"][AID]["app_name"]=app_name
                    self.RDS_data[PI]["AID_list"][AID]["app_data"]=app_data
                    if AID==52550:#TMC alert-c initialize
                        self.RDS_data[PI]["AID_list"][AID]["provider name"]="________"
                    if self.log:
                        print("new ODA: AID:%i, name:'%s', app_group:%s, station:%s" %(AID,app_name,app_group,PI))
                #decode 3A group of TMC
                if AID==52550:#TMC alert-c (continuously update)
                    variant=app_data>>14
                    if variant==0:
                        self.RDS_data[PI]["AID_list"][AID]["LTN"]=(app_data>>6)&0x3f#location table number (6 bits)
                        self.RDS_data[PI]["AID_list"][AID]["AFI"]=(app_data>>5)&0x1#alternative frequency indicator
                        self.RDS_data[PI]["AID_list"][AID]["M"]=(app_data>>4)&0x1#transmission mode indicator
                        #Message Geographical Scope:
                        self.RDS_data[PI]["AID_list"][AID]["scope"]=""
                        if (app_data>>3)&0x1==1:
                            self.RDS_data[PI]["AID_list"][AID]["scope"]+="I"#international (EUROROAD)
                        if (app_data>>2)&0x1==1:
                            self.RDS_data[PI]["AID_list"][AID]["scope"]+="N"#national
                        if (app_data>>1)&0x1==1:
                            self.RDS_data[PI]["AID_list"][AID]["scope"]+="R"#regional
                        if (app_data>>0)&0x1==1:
                            self.RDS_data[PI]["AID_list"][AID]["scope"]+="U"#urban
                        #self.RDS_data[PI]["AID_list"][AID]["I"]=(app_data>>3)&0x1#international (EUROROAD)
                        #self.RDS_data[PI]["AID_list"][AID]["N"]=(app_data>>2)&0x1#national
                        #self.RDS_data[PI]["AID_list"][AID]["R"]=(app_data>>1)&0x1#regional
                        #self.RDS_data[PI]["AID_list"][AID]["U"]=(app_data>>0)&0x1#urban
                    elif variant==1:
                        self.RDS_data[PI]["AID_list"][AID]["SID"]=(app_data>>6)&0x3f#service identifier
                        #timing parameters (used to switch away from TMC station without missing messages):
                        self.RDS_data[PI]["AID_list"][AID]["G"]=(app_data>>12)&0x3#gap parameter
                        self.RDS_data[PI]["AID_list"][AID]["activity_time"]=(app_data>>4)&0x3
                        self.RDS_data[PI]["AID_list"][AID]["window_time"]=(app_data>>2)&0x3
                        self.RDS_data[PI]["AID_list"][AID]["delay_time"]=(app_data>>0)&0x3
                    elif self.debug:
                        print("unknown variant %i in TMC 3A group"%variant)
                    if self.RDS_data[PI]["AID_list"].has_key(52550):
                        try:
                            send_pmt = pmt.pmt_to_python.pmt_from_dict({
                            "type":"3A_meta",
                            "PI":PI,
                            "data":self.RDS_data[PI]["AID_list"][52550]})
                            self.message_port_pub(pmt.intern('tmc_raw'), send_pmt)
                        except TypeError as e:
                            print(e)
                            print("this gnuradio instance doesnt seem to be able to convert from numpy.int64 to pmt")
                            code.interact(local=locals())
            elif (groupType == "4A"):#CT clock time
                bits=BitArray('uint:8=%i,uint:8=%i,uint:8=%i,uint:8=%i,uint:8=%i'%tuple(array[3:8]))
                spare,datecode,hours,minutes,offsetdir,local_time_offset = bits.unpack("uint:6,uint:17,uint:5,uint:6,uint:1,uint:5")
                local_time_offset*=0.5
                #datecode=((array[3] & 0x03) << 15) | (array[4] <<7)|((array[5] >> 1) & 0x7f)#modified julian date
                if datecode==0:
                    #do not update!!
                    if self.debug:
                        print("station:%s sent empty 4A group"%self.RDS_data[PI]["PSN"])
                else:
                    #hours=((array[5] & 0x1) << 4) | ((array[6] >> 4) & 0x0f)
                    #minutes=((array[6] &0x0F)<<2)|((array[7] >>6)&0x3)
                    #offsetdir=(array[7]>>5)&0x1
                    #local_time_offset=0.5*((array[7])&0x1F)
                    if(offsetdir==1):
                        local_time_offset*=-1
                    try:
                        date=datetime(1858,11,17)+timedelta(days=int(datecode))#convert from MJD (modified julian date)
        
                        timestring="%02i:%02i (%+.1fh)" % (hours,minutes,local_time_offset)
                        datestring=date.strftime("%d.%m.%Y")
                        ctcol=self.colorder.index('time')
                        self.signals.DataUpdateEvent.emit({'col':ctcol,'row':port,'PI':PI,'string':timestring,'tooltip':datestring})
                        self.RDS_data[PI]["time"]["timestring"]=timestring
                        self.RDS_data[PI]["time"]["datestring"]=datestring
                        self.RDS_data[PI]["time"]["datetime"]=datetime(date.year,date.month,date.day,hours,minutes)+timedelta(hours=local_time_offset)
                        if self.writeDB:
                            t=(str(datetime.now()),PI,self.RDS_data[PI]["PSN"],"CT",datestring+" "+timestring+"; datecode(MJD):"+str(datecode))
                            db.execute("INSERT INTO data (time,PI,PSN,dataType,data) VALUES (?,?,?,?,?)",t)
                    except ValueError as e:
                        print("ERROR: could not interpret time or date:")
                        print(e)

            elif (groupType == "6A"):#IH inhouse data -> save for analysis
                """In House Data:
      {'130A': {'1E1077FFFF': {'count': 1,
                               'last_time': '2016-12-08 16:26:54.767596'},
                '1F23022015': {'count': 1,
                               'last_time': '2016-12-08 16:26:56.341271'}},
       'D00F': {'1E1023FFFF': {'count': 1,
                               'last_time': '2016-12-08 16:26:54.769165'},
                '1F28032008': {'count': 3,
                               'last_time': '2016-12-08 16:26:58.272420'}}}"""
                ih_data="%02X%02X%02X%02X%02X" %(array[3]&0x1f,array[4],array[5],array[6],array[7])
                if not self.IH_data.has_key(PI):
                    self.IH_data[PI]={}
                if not self.IH_data[PI].has_key(ih_data):
                    self.IH_data[PI][ih_data]={}
                    self.IH_data[PI][ih_data]["count"]=0
                self.IH_data[PI][ih_data]["count"]+=1
                self.IH_data[PI][ih_data]["last_time"]=str(datetime.now())
            #TMC-alert-c (grouptype mostly 8A):
            elif self.RDS_data[PI]["AID_list"].has_key(52550) and self.RDS_data[PI]["AID_list"][52550]["groupType"]==groupType:#TMC alert-C
                tmc_x=array[3]&0x1f #lower 5 bit of block2
                tmc_y=(array[4]<<8)|(array[5]) #block3
                tmc_z=(array[6]<<8)|(array[7])#block4
                datetime_received=self.RDS_data[PI]["time"]["datetime"]
                psn=self.RDS_data[PI]["PSN"]
                if datetime_received==None:
                    datetime_str=""
                else:
                    datetime_str=datetime_received.strftime("%Y-%m-%d %H:%M:%S")
                if datetime_received!=None or self.TMC_without_CT==True:
                    send_pmt = pmt.pmt_to_python.pmt_from_dict({
                        "type":"alert-c",
                        "PI":PI,
                        "PSN":psn,
                        "datetime_str":datetime_str,
                        "TMC_X":int(tmc_x),
                        "TMC_Y":int(tmc_y),
                        "TMC_Z":int(tmc_z)
                    })#this gnuradio instance doesnt seem to be able to convert from numpy.int64 to pmt
                    self.message_port_pub(pmt.intern('tmc_raw'), send_pmt)
                
                #~ tmc_hash=md5.new(str([PI,tmc_x,tmc_y,tmc_z])).hexdigest()
                tmc_T=tmc_x>>4 #0:TMC-message 1:tuning info/service provider name
                #~ tmc_F=int((tmc_x>>3)&0x1) #identifies the message as a Single Group (F = 1) or Multi Group (F = 0)
                #~ Y15=int(tmc_y>>15)
                #~ try:
                    #~ ltn=self.RDS_data[PI]["AID_list"][52550]["LTN"]
                #~ except KeyError:
                    #~ ltn=1#assume germany TODO:add better error handling
                #~ if self.log:
                    #~ print("no LTN (yet) for PI:%s"%PI)
                #~ if tmc_T == 0:
                    #~ if tmc_F==1:#single group
                        
                        #~ tmc_msg=tmc_message(PI,psn,ltn,tmc_x,tmc_y,tmc_z,datetime_received,self)
                        #~ self.print_tmc_msg(tmc_msg)
                    #~ elif tmc_F==0 and Y15==1:#1st group of multigroup
                        #~ ci=int(tmc_x&0x7)
                        #~ tmc_msg=tmc_message(PI,psn,ltn,tmc_x,tmc_y,tmc_z,datetime_received,self)
                        #~ #if  self.RDS_data[PI]["internals"]["unfinished_TMC"].has_key(ci):
                            #~ #print("overwriting parital message")
                        #~ self.RDS_data[PI]["internals"]["unfinished_TMC"][ci]={"msg":tmc_msg,"time":time.time()}
                    #~ else:
                        #~ ci=int(tmc_x&0x7)
                        #~ if self.RDS_data[PI]["internals"]["unfinished_TMC"].has_key(ci):
                            #~ tmc_msg=self.RDS_data[PI]["internals"]["unfinished_TMC"][ci]["msg"]
                            #~ tmc_msg.add_group(tmc_y,tmc_z)
                            #~ age=time.time()-self.RDS_data[PI]["internals"]["unfinished_TMC"][ci]["time"]
                            #~ t=(time.time(),PI,age,ci,tmc_msg.is_complete)
                            #~ #print("%f: continuing message PI:%s,age:%f,ci:%i complete:%i"%t)
                            #~ self.RDS_data[PI]["internals"]["unfinished_TMC"][ci]["time"]=time.time()
                            #~ if tmc_msg.is_complete:
                                #~ self.print_tmc_msg(tmc_msg)#print and store message
                                #~ del self.RDS_data[PI]["internals"]["unfinished_TMC"][tmc_msg.ci]#delete finished message
                        #~ else:
                            #~ #if not ci==0:
                                #~ #print("ci %i not found, discarding"%ci)
                            #~ pass

                #~ else:#alert plus or provider info
                if tmc_T == 1:#rest done by tmc_parser
                    adr=tmc_x&0xf
                    if  4 <= adr and adr <= 9:
                        #seen variants 4569, 6 most often
                        #~ #print("TMC-info variant:%i"%adr)
                        if adr==4 or adr==5:#service provider name
                           chr1=(tmc_y >> 8) & 0xff
                           chr2=tmc_y & 0xff
                           chr3=(tmc_z >> 8) & 0xff
                           chr4=tmc_z & 0xff
                           segment=self.decode_chars(chr(chr1)+chr(chr2)+chr(chr3)+chr(chr4))
                           if self.debug:
                               print("TMC-info adr:%i (provider name), segment:%s, station:%s"%(adr,segment,self.RDS_data[PI]["PSN"]))
                           if self.RDS_data[PI]["AID_list"].has_key(52550):
                               text_list=list(self.RDS_data[PI]["AID_list"][52550]["provider name"])
                               seg_adr_start=(adr-4)*4#start of segment
                               text_list[seg_adr_start:seg_adr_start+4]=segment
                               self.RDS_data[PI]["AID_list"][52550]["provider name"]="".join(text_list)
                    
                        if adr== 7:#freq of tuned an mapped station (not seen yet)
                            freq_TN=tmc_y>>8
                            freq_ON=tmc_y&0xff#mapped frequency
                            if self.debug:
                                print("TMC-info: TN:%i, station:%s"%(freq_TN,self.RDS_data[PI]["PSN"]))
                            self.RDS_data[PI]["TMC_TN"]=freq_TN
                    else:
                        if self.log or self.debug:
                            print("alert plus on station %s (%s)"%(PI,self.RDS_data[PI]["PSN"]))#(not seen yet)

                     #~ #self.tableobj.RDS_data["D301"]["AID_list"][52550]["provider name"]="test____"
            #RadioText+ (grouptype mostly 12A):
            elif self.RDS_data[PI]["AID_list"].has_key(19415) and self.RDS_data[PI]["AID_list"][19415]["groupType"]==groupType:#RT+
                if not self.RDS_data[PI].has_key("RT+"):
                    #self.RDS_data[PI]["RT+"]={"history":{},"last_item_toggle_bit":2}
                    self.RDS_data[PI]["RT+"]={"last_item_toggle_bit":2}
                    self.RDS_data[PI]["RT+_history"]={}
                    self.RDS_data[PI]["internals"]["RT+_times"]={}
                    #self.RDS_data[PI]["RT+"]["last_item_toggle_bit"]=2
                A3_data=self.RDS_data[PI]["AID_list"][19415]["app_data"]
                template_number=A3_data&0xff
                SCB=(A3_data >> 8)&0x0f#server control bit
                CB_flag=(A3_data>>12)&0x1 #is set if template available
                rtp_message= ((array[3]&0x1f)<<32)|(array[4]<<24)|(array[5]<<16)|(array[6]<<8)|(array[7])
                item_toggle_bit=(rtp_message>>36)&0x1
                item_running_bit=(rtp_message>>35)&0x1
                tag1=(rtp_message>>17)&(2**18-1)#6+6+6
                tag2=(rtp_message)&(2**17-1)#6+6+5
                tag1_type=self.rtp_classnames[int(tag1>>12)]
                tag2_type=self.rtp_classnames[int(tag2>>11)]
                tag1_start=int((tag1>>6)&(2**6-1))
                tag1_len=int(tag1&(2**6-1))
                tag2_start=int((tag2>>5)&(2**6-1))
                tag2_len=int(tag2&(2**5-1))
                if not self.RDS_data[PI]["RT+"]["last_item_toggle_bit"] == item_toggle_bit: #new item
                    #self.RDS_data[PI]["RT+"]["history"][str(datetime.now())]=self.RDS_data[PI]["internals"]["last_rt_tooltip"]
                    t=(str(datetime.now()),PI,self.RDS_data[PI]["PSN"],"RT+",str(self.RDS_data[PI]["RT+"]))
                    if self.writeDB:
                        db.execute("INSERT INTO data (time,PI,PSN,dataType,data) VALUES (?,?,?,?,?)",t)
                    self.RDS_data[PI]["RT+_history"][str(datetime.now())]=copy.deepcopy(self.RDS_data[PI]["RT+"])#save old item
                    self.RDS_data[PI]["RT+"]["last_item_toggle_bit"] = item_toggle_bit
                    rtcol=self.colorder.index('text')
                    if self.debug:
                        print("toggle bit changed on PI:%s, cleared RT-tt"%PI)
                    self.signals.DataUpdateEvent.emit({'col':rtcol,'row':port,'PI':PI,'tooltip':""})
                if self.RDS_data[PI].has_key("RT_0"):
                    ab_flag=self.RDS_data[PI]["RT_last_ab_flag"]
                    rt=self.RDS_data[PI]["RT_"+str(ab_flag)]["RT"]
                    rt_valid=self.RDS_data[PI]["RT_"+str(ab_flag)]["RT_valid"]
                    if not tag1_type=="DUMMY_CLASS" and all(rt_valid[tag1_start:tag1_start+tag1_len+1]):
                        self.RDS_data[PI]["RT+"][tag1_type]=rt[tag1_start:tag1_start+tag1_len+1]
                        self.RDS_data[PI]["internals"]["RT+_times"][tag1_type]=time.time()
                    if not tag2_type=="DUMMY_CLASS" and all(rt_valid[tag2_start:tag2_start+tag2_len+1]):
                        self.RDS_data[PI]["RT+"][tag2_type]=rt[tag2_start:tag2_start+tag2_len+1]
                        self.RDS_data[PI]["internals"]["RT+_times"][tag2_type]=time.time()
                #check outdated tags:
                for tagtype in self.RDS_data[PI]["internals"]["RT+_times"].keys():#.keys() makes copy to avoid RuntimeError: dictionary changed size during iteration
                    age=time.time()-self.RDS_data[PI]["internals"]["RT+_times"][tagtype]
                    if age>90:#delete if older than 90 sek#TODO delete if toggle bit changes?, delete if tag changes? (title change -> delete artist)
                        del self.RDS_data[PI]["internals"]["RT+_times"][tagtype]
                        del self.RDS_data[PI]["RT+"][tagtype]


                tags="ir:%i,it:%i"%(item_running_bit,item_toggle_bit)
                rtpcol=self.colorder.index('RT+')
                self.signals.DataUpdateEvent.emit({'col':rtpcol,'row':port,'PI':PI,'string':tags})
                if(tag2_type=="ITEM.TITLE" and self.RDS_data[PI].has_key("RT_0")):#TODO remove duplicate code
                    ab_flag=self.RDS_data[PI]["RT_last_ab_flag"]
                    rt=self.RDS_data[PI]["RT_"+str(ab_flag)]["RT"]
                    rt_valid=self.RDS_data[PI]["RT_"+str(ab_flag)]["RT_valid"]
                    artist="?"
                    song="?"
                    if all(rt_valid[tag1_start:tag1_start+tag1_len+1]):
                        artist=rt[tag1_start:tag1_start+tag1_len+1]
                    if all(rt_valid[tag2_start:tag2_start+tag2_len+1]):
                        song=rt[tag2_start:tag2_start+tag2_len+1]
                    formatted_text="%s by %s"%(song,artist)
                    rtcol=self.colorder.index('text')
                    #only update tooltip if text changed -> remove flicker, still flickers :(
                    if not formatted_text == self.RDS_data[PI]["internals"]["last_rt_tooltip"]:
                        self.signals.DataUpdateEvent.emit({'col':rtcol,'row':port,'PI':PI,'tooltip':formatted_text})
                        self.RDS_data[PI]["internals"]["last_rt_tooltip"] = formatted_text
                #elif(not tag1_type=="ITEM.ARTIST" and not tag1_type=="DUMMY_CLASS"):
                #  print("%s:RT+: tag1_type:%s, tag2_type:%s"%(PI,tag1_type,tag2_type))
            elif (groupType == "14A"):#EON enhanced other networks
                    #TN = tuned network, ON=other network
                if not self.RDS_data[PI].has_key("EON"):
                    self.RDS_data[PI]["EON"]={}
                TP_ON=(array[3]>>4)&0x1
                PI_ON="%02X%02X" %(array[6],array[7])
                variant=array[3]&0xf
                self.signals.DataUpdateEvent.emit({'PI':PI_ON,'TP':TP_ON})
                if not self.RDS_data.has_key(PI_ON):
                    self.init_data_for_PI(PI_ON)
                    self.RDS_data[PI_ON]["TP"]=TP_ON
                    self.PI_dict[PI_ON]=0#initialize dict, even if no packets received
                    if self.log:
                        print("found station %s via EON on station %s"%(PI_ON,PI))
                if not self.RDS_data[PI]["EON"].has_key(PI_ON):
                    self.RDS_data[PI]["EON"][PI_ON]={}
                    self.RDS_data[PI]["EON"][PI_ON]["PSN"]="_"*8
                if variant in range(4):#variant 0..3 -> PS_ON
                    segment=self.decode_chars(chr(array[4])+chr(array[5]))
                    name_list=list(self.RDS_data[PI_ON]["PSN"])
                    #name_list=list(self.RDS_data[PI]["EON"][PI_ON]["PSN"])
                    name_list[variant*2:variant*2+2]=segment
                    if (name_list[variant*2:variant*2+2]==list(segment)):#segment already there
                        segmentcolor="purple"
                    elif(name_list[variant*2:variant*2+2]==['_']*2): #segment new
                        segmentcolor="purple"
                        name_list[variant*2:variant*2+2]=segment
                    else:#name changed (böse)
                        segmentcolor="red"
                        name_list=['_']*8 #reset name
                        name_list[variant*2:variant*2+2]=segment
                        #reset stored text:
                        self.RDS_data[PI_ON]["PSN"]="_"*8
                        self.RDS_data[PI_ON]["PSN_valid"]=[False]*8
                    self.RDS_data[PI_ON]["PSN_valid"][variant*2:variant*2+2]=[True] *2
                    PS_ON_str="".join(name_list)
                    self.RDS_data[PI_ON]["PSN"]=PS_ON_str
                    self.RDS_data[PI]["EON"][PI_ON]["PSN"]=PS_ON_str
                    #determine if text is valid
                    valid=True
                    for i in range(0,8):
                        if (not self.RDS_data[PI_ON]["PSN_valid"][i]):
                            valid = False
                    if(valid):
                        #textcolor="black"
                        textcolor=""#use default color (white if background is black)

                    else:
                        textcolor="gray"
                    formatted_text=self.color_text(self.RDS_data[PI_ON]["PSN"],variant*2,variant*2+2,textcolor,segmentcolor)
                    self.RDS_data[PI]["EON"][PI_ON]["PSN"]=PS_ON_str
                    self.RDS_data[PI_ON]["PSN"]=PS_ON_str
                    #formatted_text="<font face='Courier New' color='%s'>%s</font>"%("purple",PS_ON_str)
                    self.signals.DataUpdateEvent.emit({'PI':PI_ON,'PSN':formatted_text})
                    try:
                        t=(PI_ON,self.RDS_data[PI_ON]["PSN"],float(self.RDS_data[PI_ON]["AF"]["main"]),self.RDS_data[PI_ON]["PTY"],int(self.RDS_data[PI_ON]["TP"]))
                        if self.writeDB:
                            db.execute("INSERT OR REPLACE INTO stations (PI,PSN,freq,PTY,TP) VALUES (?,?,?,?,?)",t)
                    except KeyError:
                        #not all info present -> no db update
                        pass
                if variant==4:#AF_ON
                    if self.debug:
                        print("AF_ON method A")#TODO
                if variant in range(5,10):#variant 5..9 -> mapped freqs
                    freq_TN=self.decode_AF_freq(array[4])
                    freq_ON=self.decode_AF_freq(array[5])
                    #lock in tuned network if freq_TN matches decoder frequency
                    if(self.RDS_data[PI].has_key("tuned_freq") and freq_TN==self.RDS_data[PI]["tuned_freq"]and not self.RDS_data[PI]["AF"].has_key("main")):
                        if self.log:
                            print("main frequency found in 14A: station:%s, freq:%0.1fM"% (self.RDS_data[PI]["PSN"],freq_TN/1e6))
                        self.RDS_data[PI]["AF"]["main"]=freq_TN
                        freq_str="EON_TN:%0.1fM"% (freq_TN/1e6)
                        self.signals.DataUpdateEvent.emit({'PI':PI,'freq':freq_str})
                    #lock in ON if TN is locked in
                    if(self.RDS_data[PI]["AF"].has_key("main") and self.RDS_data[PI]["AF"]["main"]==freq_TN and not self.RDS_data[PI_ON]["AF"].has_key("main")):
                        if self.log:
                            print("mapped frequency found in 14A: station:%s, freq:%0.1fM"% (self.RDS_data[PI_ON]["PSN"],freq_ON/1e6))
                        self.RDS_data[PI_ON]["AF"]["main"]=freq_ON
                        freq_str="EON:%0.1fM"% (freq_ON/1e6)
                        self.signals.DataUpdateEvent.emit({'PI':PI_ON,'freq':freq_str})
                    #print("mapped freq in variant %i:, %i->%i"%(variant,freq_TN,freq_ON))
                if variant==13:#PTY and TA of ON
                    PTY_ON=array[4]>>3
                    TA_ON=array[5]&0x1
                    self.RDS_data[PI]["EON"][PI_ON]["TA_ON"]=TA_ON
                    self.RDS_data[PI]["EON"][PI_ON]["PTY_ON"]=PTY_ON
                    self.RDS_data[PI_ON]["TA"]=TA_ON
                    self.RDS_data[PI_ON]["PTY"]=self.pty_dict[PTY_ON]
                    self.signals.DataUpdateEvent.emit({'PI':PI_ON,'PTY':self.pty_dict[PTY_ON],'TA':TA_ON})
                    #rest is reserved
                if variant==14:#programme item number of ON
                    PIN_ON=(array[4]<<8)|(array[5])
            elif (groupType == "8A"):
                if self.debug:
                    print("8A without 3A on PI:%s"%PI)
            #else:#other group
                #print("group of type %s not decoded on station %s"% (groupType,PI))

            pr.disable() #disabled-internal-profiling
            #end of handle_msg
    def print_results(self):
        s = StringIO.StringIO()
        sortby = 'cumulative'
        ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
        ps.print_stats()
        print(s.getvalue())
    def decode_AF_freq(self,freq_raw):
        #if freq_raw in range(1,205):#1..204 BAD coding -> memory usage
        if 1<=freq_raw <=204:
            return(87500000+freq_raw*100000)#returns int
            #return(87.5e6+freq_raw*0.1e6)#returns float
        else:
            return(0)
    def ref_locs(self,loc,name_string):
        if(loc==34196):#europe
            return(name_string)
        else:
            try:
                locarray=self.lcl_dict[loc]
                aref=int(locarray[6])
                loc_name=locarray[4]
                return(self.ref_locs(aref,name_string+","+loc_name))
                #return(loc_name)
            except KeyError:
                return(name_string)

    def decode_chars(self,charstring):
        alphabet={
        0b0010:u" !\#¤%&'()*+,-./",
        0b0011:u"0123456789:;<=>?",
        0b0100:u"@ABCDEFGHIJKLMNO",
        0b0101:u"PQRSTUVWXYZ[\]―_",
        0b0110:u"‖abcdefghijklmno",
        0b0111:u"pqrstuvwxyz{|}¯ ",
        0b1000:u"áàéèíìóòúùÑÇŞßiĲ",
        0b1001:u"âäêëîïôöûüñçşǧıĳ",
        0b1010:u"ªα©‰Ǧěňőπ€£$←↑→↓",
        0b1011:u"º¹²³±İńűµ¿÷°¼½¾§",
        0b1100:u"ÁÀÉÈÍÌÓÒÚÙŘČŠŽĐĿ",
        0b1101:u"ÂÄÊËÎÏÔÖÛÜřčšžđŀ",
        0b1110:u"ÃÅÆŒŷÝÕØÞŊŔĆŚŹŦð",
        0b1111:u"ãåæœŵýõøþŋŕćśźŧ "}#0xff should not occur (not in standard) (but occured 2017-03-04-9:18 , probably transmission error)

        #charlist=list(charstring)
        return_string=""
        for i,char in enumerate(charstring):
            #split byte
            alnr=(ord(char)&0xF0 )>>4 #upper 4 bit
            index=ord(char)&0x0F #lower 4 bit
            if ord(char)<= 0b00011111:#control code
                if ord(char)==0x0D or ord(char)==0x00:#end of message SWR uses: \r\0\0\0 for last block (\0 fill 4 char segment)
                    #return_string+="\r"
                    return_string+=char
                else:
                    return_string+="{%02X}"%ord(char)#output control code
#       elif ord(char)<= 0b01111111: #real encoding slightly different from ascii
#         return_string+=char#use ascii
            else:
                try:
                    return_string+=alphabet[alnr][index]
                    #return_string+=unichr(ord(char))#TODO: properly decide for UTF8 or EBU charset
                except KeyError:
                    return_string+="?%02X?"%ord(char)#symbol not decoded
                    print("symbol not decoded: "+"?%02X?"%ord(char)+"in string:"+return_string)
                    pass
        return return_string
    def color_text(self, text, start,end,textcolor,segmentcolor):
        #formatted_text="<font face='Courier New' color='%s'>%s</font><font face='Courier New' color='%s'>%s</font><font face='Courier New' color='%s'>%s</font>"% (textcolor,text[:start],segmentcolor,text[start:end],textcolor,text[end:])
        #formatted_text="<span style='background-color: yellow;color:%s'>%s</span><span style='color:%s'>%s</span><span style='color:%s'>%s</span>"% (textcolor,text[:start],segmentcolor,text[start:end],textcolor,text[end:])
        formatted_text=("<span style='font-family:Courier New;color:%s'>%s</span>"*3)% (textcolor,text[:start],segmentcolor,text[start:end],textcolor,text[end:])
        return formatted_text
class rds_parser_table_qt_Widget(QtGui.QWidget):
    def __init__(self, signals,label,tableobj):
            #print("gui initializing")self.tableobj.RDS_data["D3A2"]
        self.signals = signals
        self.tableobj=tableobj
        self.signals.DataUpdateEvent.connect(self.display_data)
        """ Creates the QT Range widget """
        QtGui.QWidget.__init__(self)
        layout = Qt.QVBoxLayout()
        #self.label = Qt.QLabel(label)
        #layout.addWidget(self.label)#title of table disabled to save space
        #layout.addWidget(self.label)
        self.setLayout(layout)
        #self.decoder_to_PI={}
        self.PI_to_row={}
        self.table=QtGui.QTableWidget(self)
        rowcount=0
        self.table.setRowCount(rowcount)
        #self.colorder=['ID','freq','name','buttons','PTY','AF','time','text','quality']
        self.colorder=tableobj.colorder
        self.table.setColumnCount(len(self.colorder))
        self.table.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers) #disallow editing

        
 ##button.clicked.connect(self.getDetails)

        layout.addWidget(self.table)
        self.table.setHorizontalHeaderLabels(self.colorder)
        #self.table.setMaximumHeight(300)#TODO use dynamic value

        button_layout = Qt.QHBoxLayout()
        codebutton = QtGui.QPushButton("code.interact")
        codebutton.clicked.connect(self.onCLick)
        button_layout.addWidget(codebutton)
        ih_button = QtGui.QPushButton("show IH data")
        ih_button.clicked.connect(self.showIHdata)
        button_layout.addWidget(ih_button)
        save_button = QtGui.QPushButton("save")
        save_button.clicked.connect(self.saveData)
        button_layout.addWidget(save_button)
        print_button = QtGui.QPushButton("print profile")
        print_button.clicked.connect(self.printProfile)
        button_layout.addWidget(print_button)
        mode_button = QtGui.QPushButton("mode")
        mode_button.clicked.connect(self.switchMode)
        button_layout.addWidget(mode_button)
        layout.addLayout(button_layout)
        label_layout = Qt.QHBoxLayout()
        self.freq_label=QtGui.QLabel("decoder frequencies:")
        #self.freq_label.setTextFormat(QtCore.Qt.RichText)
        #self.freq_label.setTextFormat(QtCore.Qt.PlainText)
        self.count_label=QtGui.QLabel("count:")
        label_layout.addWidget(self.freq_label)
        label_layout.addWidget(self.count_label)
        layout.addLayout(label_layout)
        #TODO set different minsize if TMC is shown
        self.setMinimumSize(Qt.QSize(500,40*self.tableobj.nPorts))
        self.lastResizeTime=0
        self.clip = QtGui.QApplication.clipboard()
        #self.cb.clear(mode=cb.Clipboard )
        #self.cb.setText("Clipboard Text", mode=cb.Clipboard)
    def keyPressEvent(self, e):
        if (e.modifiers() & QtCore.Qt.ControlModifier) and len(self.table.selectedRanges())>0:
            selected = self.table.selectedRanges().pop()
            selected.leftColumn()
            selected.topRow()
            if e.key() == QtCore.Qt.Key_C: #copy
                try:
                    qs = self.table.cellWidget(selected.topRow(),selected.leftColumn()).text()#get QString from table
                    s=re.sub("<.*?>","", str(qs))#remove html tags
                    self.clip.setText(s)
                except Exception as e:
                    print(e)
                    print("no text, cant copy")
    def insert_empty_row(self):
        rowPosition = self.table.rowCount()
        self.table.insertRow(rowPosition)
        #for col in range(self.table.columnCount()-1):#all labels except in last column -> buttons
#       self.table.setCellWidget(rowPosition,col,QtGui.QLabel())
        #initialize labels everywhere:
        for col in range(self.table.columnCount()):
            self.table.setCellWidget(rowPosition,col,QtGui.QLabel())
        button_layout = Qt.QHBoxLayout()
        details_button=QtGui.QPushButton("Detail")
        details_button.clicked.connect(functools.partial(self.getDetails, row=rowPosition))
        button_layout.addWidget(details_button)
        #2017-03-17 disabled LR buttons
        #left_button=QtGui.QPushButton("L")
        #left_button.clicked.connect(functools.partial(self.setAudio, row=rowPosition,audio_channel="left"))
        #button_layout.addWidget(left_button)
        #right_button=QtGui.QPushButton("R")
        #right_button.clicked.connect(functools.partial(self.setAudio, row=rowPosition,audio_channel="right"))
        #button_layout.addWidget(right_button)

        cellWidget = QtGui.QWidget()
        cellWidget.setLayout(button_layout)
        button_col=3
        self.table.setCellWidget(rowPosition,button_col,cellWidget)
    def display_data(self, event):
            #pp.pprint(event)
        if type(event)==dict and event.has_key('group_count'):
            self.count_label.setText("count:%02i, max:%i"%(event['group_count'],event['group_count_max']))
        if type(event)==dict and event.has_key('decoder_frequencies'):
            self.freq_label.setText(event['decoder_frequencies'])
        if type(event)==dict and event.has_key('PI'):
            PI=event['PI']
            if not self.PI_to_row.has_key(PI):
                self.PI_to_row[PI]=len(self.PI_to_row)#zero for first PI seen, then count up
                self.insert_empty_row()
            row=self.PI_to_row[PI]
            PIcol=self.colorder.index('ID')
            self.table.cellWidget(row,PIcol).setText(PI)
            if event.has_key('pilot_strength'):
                col=self.colorder.index('pilot_strength')
                item=self.table.cellWidget(row,col)
                item.setText("%i dB"%event['pilot_strength'])
            if event.has_key('freq'):
                freqcol=self.colorder.index('freq')
                item=self.table.cellWidget(row,freqcol)
                item.setText(event['freq'])
            if event.has_key('wrong_block_ratio'):
                item=self.table.cellWidget(row,self.colorder.index('quality'))
                quality_string="%i%% %s"% (100-100*event['wrong_block_ratio'],event['dots'])
                item.setText(quality_string)
            if event.has_key('wrong_blocks'):
                item=self.table.cellWidget(row,self.colorder.index('quality'))
                quality_string="%i%% %s"% (100-2*event['wrong_blocks'],event['dots'])
                item.setText(quality_string)
            if event.has_key('PTY'):
                item=self.table.cellWidget(row,self.colorder.index('PTY'))
                tt=item.toolTip()
                item.setText(event['PTY'])
                item.setToolTip(tt)
            if event.has_key('flags'):
                item=self.table.cellWidget(row,self.colorder.index('PTY'))
                item.setToolTip(Qt.QString(event['flags']))
            if event.has_key('string'):
                item=self.table.cellWidget(row,event['col'])
                item.setText(event['string'])
            if event.has_key('tooltip'):
                item=self.table.cellWidget(row,event['col'])
                item.setToolTip(Qt.QString(event['tooltip']))
            if event.has_key('AF'):
                #setAF
                PIcol=self.colorder.index('AF')
                self.table.cellWidget(row,PIcol).setText(str(event['AF']['number']))
            if event.has_key('PSN'):
                #setPSN
                PSNcol=self.colorder.index('name')
                item=self.table.cellWidget(row,PSNcol)
                item.setText(event['PSN'])
        if time.time()-self.lastResizeTime > 2:#every 2 seconds
            self.table.resizeColumnsToContents()
            self.lastResizeTime=time.time()
        #end of display-data
    def printProfile(self):
        self.tableobj.print_results()
    def switchMode(self):
        #print("mode switch message sent")
        send_pmt = pmt.pmt_to_python.pmt_from_dict({"cmd":"switch mode"})
        #send_pmt = pmt.string_to_symbol("switch mode")
        self.tableobj.message_port_pub(pmt.intern('ctrl'), send_pmt)
    def saveData(self):
        filename="RDS_data_"+str(datetime.now())+".txt"
        f=open(self.tableobj.workdir+filename,"w")
        rds_data=copy.deepcopy(self.tableobj.RDS_data)
        for PI in sorted(rds_data):
            try:
                del rds_data[PI]['PSN_valid']
                del rds_data[PI]['RT_valid']
            except KeyError:
                pass
        f.write("Data:%s"%pp.pformat(rds_data))
        f.write("\n\nIn House Data:\n%s"%pp.pformat(self.tableobj.IH_data))
        f.close()
        print("data saved in file %s"%filename)
    def showIHdata(self):
        view=Qt.QDialog()
        l=QtGui.QLabel("In House Data:\n%s"%pp.pformat(self.tableobj.IH_data))
        l.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse |QtCore.Qt.TextSelectableByKeyboard)
        l.setWordWrap(True)
        #self.IH_data
        layout=Qt.QVBoxLayout()
        layout.addWidget(l)
        view.setLayout(layout)
        view.exec_()
    def setAudio(self,row,audio_channel):

        PIcol=self.colorder.index('ID')
        PI=str(self.table.cellWidget(row,PIcol).text())
        freq=int(self.tableobj.RDS_data[PI]['AF']['main'])
        #print("setaudio row:%i, chan:%s, PI:%s,freq:%i"%(row,audio_channel,PI,freq))
        send_pmt = pmt.pmt_to_python.pmt_from_dict({"cmd":"set_audio_freq","chan":audio_channel,"freq":freq})
        self.tableobj.message_port_pub(pmt.intern('ctrl'), send_pmt)
        #catch:
        #print("no freq, cant set decoder")#show notification? popup: too intrusive, log: maybe not visible, other possibility?
        #print("freq not in RX BW")#automatically shift freq-tune?
    def getDetails(self,row):
        PIcol=self.colorder.index('ID')
        PI=str(self.table.cellWidget(row,PIcol).text())
        view = chart.DialogViewer()
        if self.tableobj.PI_dict.has_key(PI) and self.tableobj.PI_dict[PI]>3:#dont print piechart if no packets received (detected via EON)
            table=chart.DataTable()
            table.addColumn('groupType')
            table.addColumn('numPackets')
            blockcounts=copy.deepcopy(self.tableobj.RDS_data[PI]['blockcounts'])
            del blockcounts['any']
            #lambda function removes last character of PI string (A or B) and sorts based on integer valure of number in front
            for key in sorted(blockcounts,key=lambda elem: int(elem[0:-1])):
                count=blockcounts[key]
                table.addRow([key+": "+str(count),count])
            mychart=chart.PieChart(table)
            view.setGraph(mychart)
        #view.resize(360, 240)
        #view.resize(380, 550)
        rds_data=copy.deepcopy(self.tableobj.RDS_data[PI])
        try:
            del rds_data['blockcounts']
            del rds_data['PSN_valid']
            del rds_data["RT_0"]['RT_valid']
            del rds_data["RT_1"]['RT_valid']
            rds_data['internals']['RT_history']=["".join(rt) for rt in rds_data['internals']['RT_history']]#combine char lists into strings (more compact)
        except KeyError:
            pass
        l=QtGui.QLabel("Data:%s"%pp.pformat(rds_data))
        l.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse |QtCore.Qt.TextSelectableByKeyboard)
        l.setWordWrap(True)
        #l=QtGui.QLabel("Data:")

        #view.layout().addWidget(l)

        scrollArea = QtGui.QScrollArea(self)
        scrollArea.setWidgetResizable(True)
        scrollArea.setWidget(l)
        view.layout().addWidget(scrollArea)
        view.setWindowTitle(self.tableobj.RDS_data[PI]["PSN"])
        view.exec_()
    def onCLick(self):
        print("button clicked")
        code.interact(local=locals())
if __name__ == "__main__":
    from PyQt4 import Qt
    import sys


    app = Qt.QApplication(sys.argv)
    mainobj= rds_parser_table_qt_Signals()
    #mainobj=None
    widget = rds_parser_table_qt_Widget(mainobj,"TestLabel")
    widget.show()
    widget.setWindowTitle("Test Qt gui")
    widget.setGeometry(200,200,600,300)
    sys.exit(app.exec_())

    widget = None
