#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 
# Copyright 2017 <+YOU OR YOUR COMPANY+>.
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

import numpy
from gnuradio import gr
import pmt
from PyQt4 import Qt, QtCore, QtGui
import code,time,csv,sqlite3,atexit
from bitstring import BitArray
from crfa.tmc_classes import tmc_dict,tmc_message,language
from datetime import datetime
from datetime import timedelta

class tmc_parser(gr.sync_block):
    """
    docstring for block tmc_parser
    """
    def __init__(self, workdir,log,debug,writeDB,maxheight):
        gr.sync_block.__init__(self,
            name="tmc_parser",
            in_sig=None,
            out_sig=None)
        self.log=log
        self.debug=debug
        self.workdir=workdir
        self.writeDB=writeDB
        self.qtwidget=tmc_parser_Widget(self,maxheight)
        self.message_port_register_in(pmt.intern('in'))
        self.set_msg_handler(pmt.intern('in'), self.handle_msg)
        self.tmc_meta={}
        self.unfinished_messages={}
        self.TMC_data={}
        self.tmc_messages=tmc_dict()
        atexit.register(self.goodbye)
	self.save_data_timer=time.time()
        if self.writeDB:
            #create new DB file
            db_name=workdir+'RDS_data'+datetime.now().strftime("%Y%m%d_%H%M%S")+'_TMC.db'
            db=sqlite3.connect(db_name, check_same_thread=False)
            self.db=db
            #create tables
            try:

                #db.execute('CREATE TABLE TMC(hash text PRIMARY KEY UNIQUE,time text,PI text, F integer,event integer,location integer,DP integer,div integer,dir integer,extent integer,text text,multi text,rawmgm text)')
                db.execute('''CREATE TABLE TMC(lcn integer,updateclass integer,hash int,
                PI text,time text,ecn integer, isSingle integer,DP integer,div integer,dir integer,extent integer,
                locstr text,eventstr text,multistr text,infostr text,
                PRIMARY KEY (lcn, updateclass,hash))''')
                db.commit()

            except sqlite3.OperationalError as e:
                print("ERROR: tables already exist")
                print(e)
        reader = csv.reader(open(self.workdir+'LCL15.1.D-160122_utf8.csv'), delimiter=';', quotechar='"')
        reader.next()#skip header
        self.lcl_dict=dict((int(rows[0]),rows[1:]) for rows in reader)
        #read TMC-event list
        reader = csv.reader(open(self.workdir+'event-list_with_forecast_sort.csv'), delimiter=',', quotechar='"')
        reader.next()#skip header
        self.ecl_dict=dict((int(rows[0]),rows[1:]) for rows in reader)
        #read supplementary information code list
        reader = csv.reader(open(self.workdir+'label6-supplementary-information-codes.csv'), delimiter=',', quotechar='"')
        reader.next()#skip header, "code,english,german"
        if language=="de":
            self.label6_suppl_info=dict((int(rows[0]),rows[2]) for rows in reader)#german
        else:
            self.label6_suppl_info=dict((int(rows[0]),rows[1]) for rows in reader)#english
        #read update classes
        reader = csv.reader(open(self.workdir+'tmc_update_class_names.csv'), delimiter=',', quotechar='"')
        reader.next()#skip header, "code(C),english,german"
        if language=="de":
            self.tmc_update_class_names=dict((int(rows[0]),rows[2]) for rows in reader)#german names
        else:
            self.tmc_update_class_names=dict((int(rows[0]),rows[1]) for rows in reader)#english names  
    def goodbye(self):
        self.save_data()
        print("closing tmc display")
    def save_data(self):
        if self.writeDB:
            self.db.commit()
        f=open(self.workdir+'google_maps_markers.js', 'w')
        markerstring=self.tmc_messages.getMarkerString()
        markerstring+='\n console.log("loaded "+markers.length+" markers")'
        markerstring+='\n document.getElementById("errorid").innerHTML = "loaded "+markers.length+" markers";'
        f.write(markerstring)
        f.close()
    def print_tmc_msg(self,tmc_msg):
        if self.writeDB and tmc_msg.event.is_cancellation == False:
            try:
                t=(int(tmc_msg.location.lcn),int(tmc_msg.event.updateClass),tmc_msg.PI,tmc_msg.tmc_hash,
                tmc_msg.getTime(),int(tmc_msg.event.ecn),int(tmc_msg.is_single),
                int(tmc_msg.tmc_DP),int(tmc_msg.tmc_D),int(tmc_msg.tmc_dir),int(tmc_msg.tmc_extent),
                tmc_msg.location_text().decode("utf-8"),tmc_msg.events_string().decode("utf-8"),tmc_msg.info_str().decode("utf-8"),tmc_msg.multi_str().decode("utf-8"))
                self.db.execute("REPLACE INTO TMC (lcn,updateclass,hash,PI,time,ecn,isSingle,DP,div,dir,extent,locstr,eventstr,infostr,multistr) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",t)
            except Exception as e:
                if self.log or self.debug:
                    print("error during db insert msg:%s"%tmc_msg.log_string())
                    print(e)
                pass
        self.qtwidget.print_tmc_msg(tmc_msg)
        if self.debug:
            print("new tmc message %s"%tmc_msg)
    def initialize_data_for_PI(self,PI):
        self.unfinished_messages[PI]={}
    def handle_msg(self,msg):
	if time.time()-self.save_data_timer > 3:#every 3 seconds
	    self.save_data_timer=time.time()
	    self.save_data()
        m=pmt.to_python(msg)
        PI=m["PI"]
        if not self.unfinished_messages.has_key(PI):
            self.initialize_data_for_PI(PI)
        if m["type"]=="3A_meta":
            self.tmc_meta[PI]=m["data"]
        elif m["type"]=="alert-c":
            #self.qtwidget.updateui()
            #print(m)
            psn=m["PSN"]
            try:
                ltn=self.tmc_meta[PI]["LTN"]
            except KeyError:
                ltn=1#assume germany TODO:add better error handling
                if self.log:
                    print("no LTN (yet) for PI:%s"%PI)
            tmc_x=m["TMC_X"]
            tmc_y=m["TMC_Y"]
            tmc_z=m["TMC_Z"]
            if m["datetime_str"]=="":
                datetime_received=None
            else:
                datetime_received=datetime.strptime(m["datetime_str"],"%Y-%m-%d %H:%M:%S")
            tmc_T=tmc_x>>4 #0:TMC-message 1:tuning info/service provider name
            tmc_F=int((tmc_x>>3)&0x1) #identifies the message as a Single Group (F = 1) or Multi Group (F = 0)
            Y15=int(tmc_y>>15)
            if tmc_T == 0:
                if tmc_F==1:#single group
                    tmc_msg=tmc_message(PI,psn,ltn,tmc_x,tmc_y,tmc_z,datetime_received,self)
                    self.print_tmc_msg(tmc_msg)
                elif tmc_F==0 and Y15==1:#1st group of multigroup
                    ci=int(tmc_x&0x7)
                    tmc_msg=tmc_message(PI,psn,ltn,tmc_x,tmc_y,tmc_z,datetime_received,self)
                    #if  self.RDS_data[PI]["internals"]["unfinished_TMC"].has_key(ci):
                        #print("overwriting parital message")
                    self.unfinished_messages[PI][ci]={"msg":tmc_msg,"time":time.time()}
                else:
                    ci=int(tmc_x&0x7)
                    if self.unfinished_messages[PI].has_key(ci):
                        tmc_msg=self.unfinished_messages[PI][ci]["msg"]
                        tmc_msg.add_group(tmc_y,tmc_z)
                        age=time.time()-self.unfinished_messages[PI][ci]["time"]
                        t=(time.time(),PI,age,ci,tmc_msg.is_complete)
                        #print("%f: continuing message PI:%s,age:%f,ci:%i complete:%i"%t)
                        self.unfinished_messages[PI]["time"]=time.time()
                        if tmc_msg.is_complete:
                            self.print_tmc_msg(tmc_msg)#print and store message
                            del self.unfinished_messages[PI][tmc_msg.ci]#delete finished message
                    else:
                        #if not ci==0:
                            #print("ci %i not found, discarding"%ci)
                        pass

            else:#alert plus or provider info
                adr=tmc_x&0xf
                if  4 <= adr and adr <= 9:
                    #seen variants 4569, 6 most often
                    #print("TMC-info variant:%i"%adr)
                    if adr==4 or adr==5:#service provider name
                        chr1=(tmc_y >> 8) & 0xff
                        chr2=tmc_y & 0xff
                        chr3=(tmc_z >> 8) & 0xff
                        chr4=tmc_z & 0xff
                        segment=self.decode_chars(chr(chr1)+chr(chr2)+chr(chr3)+chr(chr4))
                        if self.log:
                            print("TMC-info adr:%i (provider name), segment:%s, station:%s"%(adr,psn))
                    if adr== 7:#freq of tuned an mapped station (not seen yet)
                        freq_TN=tmc_y>>8
                        freq_ON=tmc_y&0xff#mapped frequency
                        if self.log:
                            print("TMC-info: TN:%i, station:%s"%(freq_TN,psn))
                else:
                    if self.log:
                        print("alert plus on station %s (%s)"%(PI,psn))#(not seen yet)
            
    def getqtwidget(self):
        return self.qtwidget
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
class tmc_parser_Widget(QtGui.QWidget):
    def print_tmc_msg(self,tmc_msg):
        ef=unicode(self.event_filter.text().toUtf8(), encoding="UTF-8").lower()
        lf=unicode(self.location_filter.text().toUtf8(), encoding="UTF-8").lower()
        filters=[{"type":"location", "str":lf},{"type":"event", "str":ef}]
        if self.parser.tmc_messages.matchFilter(tmc_msg,filters):
            self.logOutput.append(Qt.QString.fromUtf8(tmc_msg.log_string()))
            self.logOutput.append(Qt.QString.fromUtf8(tmc_msg.multi_str()))
    def updateui(self):
        print("updating ui")
    def filterChanged(self):
        ef=unicode(self.event_filter.text().toUtf8(), encoding="UTF-8").lower()
        lf=unicode(self.location_filter.text().toUtf8(), encoding="UTF-8").lower()
        self.logOutput.clear()
        filters=[{"type":"location", "str":lf},{"type":"event", "str":ef}]
        self.logOutput.append(Qt.QString.fromUtf8(self.parser.tmc_messages.getLogString(filters)))
        print("filter changed")
    def __init__(self, parser,maxheight):
        QtGui.QWidget.__init__(self)
        layout = Qt.QVBoxLayout()
        self.setLayout(layout)
        self.parser=parser
        self.tmc_message_label=QtGui.QLabel("TMC messages:")
        self.event_filter=QtGui.QLineEdit()#QPlainTextEdit ?
        self.location_filter=QtGui.QLineEdit(u"Baden-Württemberg")
        self.event_filter.returnPressed.connect(self.filterChanged)
        self.location_filter.returnPressed.connect(self.filterChanged)
        
        filter_layout = Qt.QHBoxLayout()
        filter_layout.addWidget(QtGui.QLabel("event filter:"))
        filter_layout.addWidget(self.event_filter)
        filter_layout.addWidget(QtGui.QLabel("location filter:"))
        filter_layout.addWidget(self.location_filter)
        
        layout.addLayout(filter_layout)
        layout.addWidget(self.tmc_message_label)
        self.logOutput = Qt.QTextEdit()
        self.logOutput.setReadOnly(True)
        self.logOutput.setLineWrapMode(Qt.QTextEdit.NoWrap)
        if not maxheight==0:
            self.setMaximumHeight(maxheight)
        font = self.logOutput.font()
        font.setFamily("Courier")
        font.setPointSize(10)
        layout.addWidget(self.logOutput)
        self.clip = QtGui.QApplication.clipboard()
