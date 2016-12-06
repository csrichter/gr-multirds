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
import pmt,functools,csv,md5,collections,copy
from datetime import datetime
import crfa.chart as chart

from PyQt4 import Qt, QtCore, QtGui
import pprint,code#for easier testing
pp = pprint.PrettyPrinter()


from PyQt4.QtCore import QObject, pyqtSignal

class rds_parser_table_qt_Signals(QObject):
    DataUpdateEvent = QtCore.pyqtSignal(dict)
    def __init__(self, parent=None):
	super(QtCore.QObject, self).__init__()   
class rds_parser_table_qt(gr.sync_block):
    """
    docstring for block qtguitest
    """
    def __init__(self,signals,nPorts,slot,freq,log,debug):
	#QObject.__init__()
        gr.sync_block.__init__(self,
            name="RDS Table",
            in_sig=None,
            out_sig=None)
	for i in range(0,nPorts):
	  self.message_port_register_in(pmt.intern('in%d'%i))
	  self.set_msg_handler(pmt.intern('in%d'%i), functools.partial(self.handle_msg, port=i))
	self.message_port_register_in(pmt.intern('freq'))
	self.set_msg_handler(pmt.intern('freq'), self.set_freq)
	self.log=log
	self.debug=debug
	self.signals=signals
	self.RDS_data={}
	self.change_freq_tune=slot
	self.tuning_frequency=int(freq)
        self.printcounter=0
        self.ODA_application_names={}
        self.TMC_data={}
        self.decoder_frequencies={}
        self.colorder=['ID','freq','name','PTY','AF','time','text','quality','buttons']
        #workdir=""
        workdir="/user/wire2/richter/hackrf_prototypes/"
        #workdir="/media/clemens/intdaten/uni_bulk/forschungsarbeit/hackrf_prototypes/"
        reader = csv.reader(open(workdir+'RDS_ODA-AIDs_names_only.csv'), delimiter=',', quotechar='"')
        reader.next()#skip header
        for row in reader:
	  self.ODA_application_names[int(row[0])]=row[1]
	#read location code list:
	reader = csv.reader(open(workdir+'LCL15.1.D-160122_utf8.csv'), delimiter=';', quotechar='"')
	reader.next()#skip header
	self.lcl_dict=dict((int(rows[0]),rows[1:]) for rows in reader)
	#read RT+ class name list:
	reader = csv.reader(open(workdir+'RTplus_classnames.csv'), delimiter=',', quotechar='"')
	reader.next()#skip header
	self.rtp_classnames=dict((int(rows[0]),rows[1]) for rows in reader)
	#read TMC-event list
	reader = csv.reader(open(workdir+'event-list_code+de-name_sort.csv'), delimiter=',', quotechar='"')
	#no header
	self.ecl_dict=dict((int(rows[0]),rows[1]) for rows in reader)
	#read PTY list
	f=open(workdir+'pty-list.csv')
	reader = csv.reader(f, delimiter=',', quotechar='"')
	reader.next()#skip header
	self.pty_dict=dict((int(rows[0]),rows[1]) for rows in reader)
	f.close()
    def set_freq_tune(self,freq):
      self.tuning_frequency=int(freq)
      message_string="decoder frequencies:"
      for num in self.decoder_frequencies:
	freq=self.decoder_frequencies[num]
	message_string+="\t %i:%0.1fM"% (num,freq/1e6)
      message_string+="\t tuned frequency:%0.1fM"%(self.tuning_frequency/1e6)
      self.signals.DataUpdateEvent.emit({'decoder_frequencies':message_string})
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
	message_string="decoder frequencies:"
	for num in self.decoder_frequencies:
	  freq=self.decoder_frequencies[num]
	  message_string+="\t %i:%0.1fM"% (num,freq/1e6)
	message_string+="\t tuned frequency:%0.1fM"%(self.tuning_frequency/1e6)
	self.signals.DataUpdateEvent.emit({'decoder_frequencies':message_string})
	#self.signals.DataUpdateEvent.emit({'row':decoder_num,'freq':freq_str})
	#print("nr:%i freq:%s"%(tgtnum,freq_str))
    def init_data_for_PI(self,PI):
	  self.RDS_data[PI]={}
	  #self.RDS_data[PI]["blockcounts"]={}# no defaults (works aswell)
	  #defaults are to keep colors in piechart  consistent between stations:
	  self.RDS_data[PI]["blockcounts"]={"0A":0,"1A":0,"2A":0,"3A":0,"4A":0,"6A":0,"8A":0,"12A":0,"14A":0}
	  self.RDS_data[PI]["blockcounts"]["any"]=0
	  self.RDS_data[PI]["AID_list"]={}
	  self.RDS_data[PI]["PSN"]="_"*8
	  self.RDS_data[PI]["PSN_valid"]=[False]*8
	  self.RDS_data[PI]["AF"]={}
	  self.RDS_data[PI]["TP"]=-1
	  self.RDS_data[PI]["TA"]=-1
	  self.RDS_data[PI]["PTY"]=""
	  self.RDS_data[PI]["DI"]=[2,2,2,2]
	  self.RDS_data[PI]["internals"]={"last_rt_tooltip":""}      
    def handle_msg(self, msg, port):#port from 0 to 3
	#code.interact(local=locals())
	array=pmt.to_python(msg)[1]
	groupNR=array[2]&0b11110000
	groupVar=array[2]&0b00001000
	if (groupVar == 0):
		groupType=str(groupNR >> 4)+"A"
	else:
		groupType=str(groupNR >> 4)+"B"
	PI="%02X%02X" %(array[0],array[1])
	TP=(array[2]>>2)&0x1
	block2=(array[2]<<8)|(array[3]) #block2
	PTY=(block2>>5)&0x1F
	wrong_blocks=int(array[12])
	#initialize dict 1st packet from station:
	if not self.RDS_data.has_key(PI):
	  self.init_data_for_PI(PI)
	  if self.log:
	    print("found station %s"%PI)
	  
	if self.decoder_frequencies.has_key(port):
	  freq=self.decoder_frequencies[port]
	  freq_str="%i:%0.1fM"% (port,freq/1e6)
	  self.RDS_data[PI]["tuned_freq"]=freq
	  #self.signals.DataUpdateEvent.emit({'PI':PI,'freq':freq_str})
	self.RDS_data[PI]["blockcounts"]["any"]+=1
	if self.RDS_data[PI]["blockcounts"]["any"]==5:
	  self.RDS_data[PI]["blockcounts"]["any"]=0
	dots="."*self.RDS_data[PI]["blockcounts"]["any"]
	self.RDS_data[PI]["TP"]=TP
	self.RDS_data[PI]["PTY"]=self.pty_dict[PTY]
	self.signals.DataUpdateEvent.emit({'row':port,'PI':PI,'PTY':self.pty_dict[PTY],'TP':TP,'wrong_blocks':wrong_blocks,'dots':dots})
	if (groupType == "0A"):#AF PSN
	  adr=array[3]&0b00000011
	  segment=self.decode_chars(chr(array[6])+chr(array[7]))
	  d=(array[3]>>2)&0x1
	  self.RDS_data[PI]["DI"][3-adr]=d
	  #DI[0]=d0	0=Mono 			1=Stereo
	  #d1 		Not artificial head 	Artificial head
	  #d2		Not compressed		Compressed
	  #d3		Static PTY		Dynamic PTY
	  TA=(array[3]>>4)&0x1
	  MS=(array[3]>>3)&0x1
	  self.RDS_data[PI]["TA"]=TA
	  flag_string="TP:%i, TA:%i, MS:%i, DI:%s"%(TP,TA,MS,str(self.RDS_data[PI]["DI"]))
	  self.signals.DataUpdateEvent.emit({'row':port,'PI':PI,'flags':flag_string})
	  
	  #224 1110 0000 = no AF
	  #225 1110 0001 = 1AF
	  #249 1111 1001 = 25AF
	  fillercode=205#1100 1101
	  if not self.RDS_data[PI]["AF"].has_key("main") and self.RDS_data[PI].has_key("tuned_freq"):
	    freq=self.decode_AF_freq(array[4])
	    if freq==self.RDS_data[PI]["tuned_freq"]:
	      self.RDS_data[PI]["AF"]["main"]=freq
	      if self.log:
		print("main frequency found in 0A: station:%s, freq:%0.1fM"% (self.RDS_data[PI]["PSN"],freq/1e6))
	      freq_str="0A:%0.1fM"% (freq/1e6)
	      self.signals.DataUpdateEvent.emit({'PI':PI,'freq':freq_str})
	    freq=self.decode_AF_freq(array[5])
	    if freq==self.RDS_data[PI]["tuned_freq"]:
	      self.RDS_data[PI]["AF"]["main"]=freq
	      if self.log:
		print("main frequency found in 0A: station:%s, freq:%0.1fM"% (self.RDS_data[PI]["PSN"],freq/1e6))
	      freq_str="0A:%0.1fM"% (freq/1e6)
	      self.signals.DataUpdateEvent.emit({'PI':PI,'freq':freq_str})
	  if(array[4]>= 224 and array[4]<= 249):
	    #print("AF1 detected")
	    self.RDS_data[PI]["AF"]['number']=array[4]-224
	    #self.RDS_data[PI]["AF"]['main']=self.decode_AF_freq(array[5])
	    self.signals.DataUpdateEvent.emit({'row':port,'PI':PI,'AF':self.RDS_data[PI]["AF"]})
	  if(array[5]>= 224 and array[5]<= 249):
	    print("AF2 detected (shouldn't happen)")
	  
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
	   textcolor="black"
	  else:
	   textcolor="gray"	  
	  formatted_text=self.color_text(self.RDS_data[PI]["PSN"],adr*2,adr*2+2,textcolor,segmentcolor)
	  self.signals.DataUpdateEvent.emit({'row':port,'PI':PI,'PSN':formatted_text})
	elif (groupType == "1A"):#PIN programme item number
	  PIN=(array[6]<<8)|(array[7])
	  SLC=(array[4]<<8)|(array[5])&0xfff#slow labeling code
	  radio_paging=array[3]&0x1f
	  LA=array[4]>>7#linkage actuator
	  variant=(array[4]>>4)&0x7
	  if variant==0:
	    paging=array[4]&0xf
	    extended_country_code=array[5]
	  elif variant==1:
	    TMC_info=SLC
	  elif variant==2:
	    paging_info=SLC
	  elif variant==3:
	    language_codes=SLC
	  elif variant==6:
	    #for use by broadcasters
	    if self.debug:
	      print("PI:%s PSN:%s uses variant 6 of 1A"%(PI,self.RDS_data[PI]["PSN"]))
	  elif variant==7:
	    ESW_channel_identification=SLC
	  PIN_day=(PIN>>11)&0x1f
	  PIN_hour=(PIN>>6)&0x1f
	  PIN_minute=PIN&0x3f
	  PIN_valid= PIN_day in range(1,32) and PIN_hour in range(0,24) and PIN_minute in range(0,60)
	  if PIN_valid:
	    self.RDS_data[PI]["PIN"]=[PIN_day,PIN_hour,PIN_minute]
	elif (groupType == "2A"):#RT radiotext
	   if(not self.RDS_data[PI].has_key("RT")):#initialize variables
	    self.RDS_data[PI]["RT"]="_"*64
	    self.RDS_data[PI]["RT_valid"]=[False]*64
	    self.RDS_data[PI]["RT_all_valid"]=False
	   
	   adr=array[3]&0b00001111
	   segment=self.decode_chars(chr(array[4])+chr(array[5])+chr(array[6])+chr(array[7]))
	   #print("RT:adress: %d, segment:%s"%(adr,segment))
	   #self.signals.DataUpdateEvent.emit({'col':5,'row':port,'PI':PI,'groupType':groupType,'adress':adr,'segment':segment})
	   text_list=list(self.RDS_data[PI]["RT"])
	   #determine text length:
	   try:
	     text_end=text_list.index('\r')
	   except ValueError:
	     text_end=64 #assume whole string is important
	     pass

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
	     self.RDS_data[PI]["RT"]="_"*64
	     self.RDS_data[PI]["RT_valid"]=[False]*64
	  
	   self.RDS_data[PI]["RT_valid"][adr*4:adr*4+4]=[True] *4
	   self.RDS_data[PI]["RT"]="".join(text_list)
	   
	   #determine if (new) text is valid
	   self.RDS_data[PI]["RT_all_valid"]=True
	   for i in range(0,text_end):
	     if (not self.RDS_data[PI]["RT_valid"][i]):
	      self.RDS_data[PI]["RT_all_valid"] = False
	   if(self.RDS_data[PI]["RT_all_valid"]):
	     textcolor="black"
	   else:
	     textcolor="gray"
	   #formatted_text="<font face='Courier New' color='%s'>%s</font><font face='Courier New' color='%s'>%s</font><font face='Courier New' color='%s'>%s</font>"% (textcolor,self.RDS_data[PI]["RT"][:adr*4],segmentcolor,self.RDS_data[PI]["RT"][adr*4:adr*4+4],textcolor,self.RDS_data[PI]["RT"][adr*4+4:])
	   formatted_text=self.color_text(self.RDS_data[PI]["RT"],adr*4,adr*4+4,textcolor,segmentcolor)
	   #print(self.RDS_data[PI]["RT"]+" valid:"+str(valid)+"valarr:"+str(self.RDS_data[PI]["RT_valid"]))

	   rtcol=self.colorder.index('text')
	   self.signals.DataUpdateEvent.emit({'col':rtcol,'row':port,'PI':PI,'string':formatted_text})
	   #code.interact(local=locals())
	elif (groupType == "3A"):#ODA announcements (contain application ID "AID")
	  AID=(array[6]<<8)|(array[7])#combine 2 bytes into 1 block
	  app_data=(array[4]<<8)|(array[5])#content defined by ODA-app
	  app_group_raw=array[3]&0x1f #group type in which this app is sent
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
	    if self.log:
	      print("new ODA: AID:%i, name:%s, app_group:%s, station:%s" %(AID,app_name,app_group,PI))
	  #decode 3A group of TMC
	  if AID==52550:#TMC alert-c
	    variant=app_data>>14
	    if variant==0:
	      LTN=(app_data>>6)&0x3f#location table number
	      AFI=(app_data>>5)&0x1#alternative frequency indicator
	      M=(app_data>>4)&0x1#transmission mode indicator
	      I=(app_data>>3)&0x1#international (EUROROAD)
	      N=(app_data>>2)&0x1#national
	      R=(app_data>>1)&0x1#regional
	      U=(app_data>>0)&0x1#urban
	    elif variant==1:
	      SID=(app_data>>6)&0x3f#service identifier
	      G=(app_data>>12)&0x3#gap parameter
	      activity_time=(app_data>>4)&0x3
	      window_time=(app_data>>2)&0x3
	      delay_time=(app_data>>0)&0x3
	    elif self.debug:
	      print("unknown variant %i in TMC 3A group"%variant)
	elif (groupType == "4A"):#CT clock time
	  datecode=((array[3] & 0x03) << 15) | (array[4] <<7)|((array[5] >> 1) & 0x7f)
	  hours=((array[5] & 0x1) << 4) | ((array[6] >> 4) & 0x0f)
	  minutes=((array[6] &0x0F)<<2)|((array[7] >>6)&0x3)
	  offsetdir=(array[7]>>5)&0x1
	  local_time_offset=0.5*((array[7])&0x1F)
	  if(offsetdir==1):
	    local_time_offset*=-1
	  year=int((datecode - 15078.2) / 365.25)	  
	  month=int((datecode - 14956.1 - int(year * 365.25)) / 30.6001)
	  day=datecode - 14956 - int(year * 365.25) - int(month * 30.6001)
	  if(month == 14 or month == 15):#no idea why -> annex g of RDS spec
	    year += 1;
	    month -= 13
	  year+=1900
	  #month was off by one different rounding in c and python?
	  month-=1
	  #datestring="%02i.%02i.%4i, %02i:%02i (%+.1fh)" % (day,month,year,hours,minutes,local_time_offset)
	  timestring="%02i:%02i (%+.1fh)" % (hours,minutes,local_time_offset)
	  datestring="%02i.%02i.%4i" % (day,month,year)
	  ctcol=self.colorder.index('time')
	  self.signals.DataUpdateEvent.emit({'col':ctcol,'row':port,'PI':PI,'string':timestring,'tooltip':datestring})
	#TMC-alert-c (grouptype mostly 8A):
	elif self.RDS_data[PI]["AID_list"].has_key(52550) and self.RDS_data[PI]["AID_list"][52550]["groupType"]==groupType:#TMC alert-C
	  tmc_x=array[3]&0x1f #lower 5 bit of block2
	  tmc_y=(array[4]<<8)|(array[5]) #block3
	  tmc_z=(array[6]<<8)|(array[7])#block4
	  tmc_hash=md5.new(str([PI,tmc_x,tmc_y,tmc_z])).hexdigest()
	  tmc_T=tmc_x>>4 #0:TMC-message 1:tuning info/service provider name
	  if tmc_T == 0: #message
	    #print("TMC-message")
	    tmc_F=(tmc_x>>3)&0x1 #single/multiple group
	    tmc_event=int(tmc_y&0x7ff) #Y10-Y0
	    tmc_location=tmc_z
	    tmc_DP=tmc_x&0x7 #duration and persistence 3 bits
	    tmc_extent=(tmc_y>>11)&0x7 #3 bits (Y13-Y11)
	    tmc_D=tmc_y>>15 #diversion bit(Y15)
	    tmc_dir=(tmc_y>>14)&0x1 #+-direction bit (Y14)
 #LOCATIONCODE;TYPE;SUBTYPE;ROADNUMBER;ROADNAME;FIRST_NAME;SECOND_NAME;AREA_REFERENCE;LINEAR_REFERENCE;NEGATIVE_OFFSET;POSITIVE_OFFSET;URBAN;INTERSECTIONCODE;INTERRUPTS_ROAD;IN_POSITIVE;OUT_POSITIVE;IN_NEGATIVE;OUT_NEGATIVE;PRESENT_POSITIVE;PRESENT_NEGATIVE;EXIT_NUMBER;DIVERSION_POSITIVE;DIVERSION_NEGATIVE;VERÄNDERT;TERN;NETZKNOTEN_NR;NETZKNOTEN2_NR;STATION;X_KOORD;Y_KOORD;POLDIR;ADMIN_County;ACTUALITY;ACTIVATED;TESTED;SPECIAL1;SPECIAL2;SPECIAL3;SPECIAL4;SPECIAL5;SPECIAL6;SPECIAL7;SPECIAL8;SPECIAL9;SPECIAL10
	    try:
	      location=self.lcl_dict[tmc_location]
	      loc_type=location[0]
	      loc_subtype=location[1]
	      loc_roadnumber=location[2]
	      loc_roadname=location[3]
	      loc_first_name=location[4]
	      loc_second_name=location[5]
	      loc_area_ref=int(location[6])
	      event_name=self.ecl_dict[tmc_event]
	      refloc_name=""
	      try:
		refloc=self.lcl_dict[loc_area_ref]
		refloc_name=refloc[4]
	      except KeyError:
		#print("location '%i' not found"%tmc_location)
		pass
	      if not self.TMC_data.has_key(tmc_hash):#if message new
	        message_string="TMC-message,event:%s location:%i,reflocs:%s, station:%s"%(event_name,tmc_location,self.ref_locs(tmc_location,""),self.RDS_data[PI]["PSN"])
	        self.TMC_data[tmc_hash]={"PI":PI,"string":message_string}
	        self.signals.DataUpdateEvent.emit({'TMC_log':message_string})
	        #print(message_string)
	    except KeyError:
	      #print("location '%i' not found"%tmc_location)
	      pass
	    #code.interact(local=locals())
	  else:#alert plus or provider info
	    adr=tmc_x&0xf
	    if  4 <= adr and adr <= 9:
	      #seen variants 4569, 6 most often
	      #print("TMC-info variant:%i"%adr)
	      if adr== 7:#freq of tuned an mapped station (not seen yet)
		freq_TN=tmc_y>>8
		freq_ON=tmc_y&0xff#mapped frequency
		if self.debug:
		  print("TMC-info: TN:%i"%freq_TN)
		self.RDS_data[PI]["TMC_TN"]=freq_TN
	    else:
	      a=0
	      if self.debug:
		print("alert plus")#(not seen yet)
	    
	 
	#RadioText+ (grouptype mostly 12A):
	elif self.RDS_data[PI]["AID_list"].has_key(19415) and self.RDS_data[PI]["AID_list"][19415]["groupType"]==groupType:#RT+
	  if not self.RDS_data[PI].has_key("RT+"):
	    #self.RDS_data[PI]["RT+"]={"history":{},"last_item_toggle_bit":2}
	    self.RDS_data[PI]["RT+"]={"last_item_toggle_bit":2}
	    self.RDS_data[PI]["RT+_history"]={}
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
	    self.RDS_data[PI]["RT+_history"][str(datetime.now())]=copy.deepcopy(self.RDS_data[PI]["RT+"])#save old item
	    self.RDS_data[PI]["RT+"]["last_item_toggle_bit"] = item_toggle_bit
	    rtcol=self.colorder.index('text')
	    if self.debug:
	      print("toggle bit changed on PI:%s, cleared RT-tt"%PI)
	    self.signals.DataUpdateEvent.emit({'col':rtcol,'row':port,'PI':PI,'tooltip':""})
	  if self.RDS_data[PI].has_key("RT"):
	    rt=self.RDS_data[PI]["RT"]
	    rt_valid=self.RDS_data[PI]["RT_valid"]
	    if not tag1_type=="DUMMY_CLASS" and all(rt_valid[tag1_start:tag1_start+tag1_len+1]):
	      self.RDS_data[PI]["RT+"][tag1_type]=rt[tag1_start:tag1_start+tag1_len+1]
	    if not tag2_type=="DUMMY_CLASS" and all(rt_valid[tag2_start:tag2_start+tag2_len+1]):
	      self.RDS_data[PI]["RT+"][tag2_type]=rt[tag2_start:tag2_start+tag2_len+1]
	  tags="ir:%i,it:%i"%(item_running_bit,item_toggle_bit)
	  afcol=self.colorder.index('AF')
	  self.signals.DataUpdateEvent.emit({'col':afcol,'row':port,'PI':PI,'string':tags})
	  #if(tag1_type=="ITEM.ARTIST"and tag2_type=="ITEM.TITLE" and self.RDS_data[PI].has_key("RT") and self.RDS_data[PI]["RT_all_valid"]):
	  if(tag2_type=="ITEM.TITLE" and self.RDS_data[PI].has_key("RT")):#TODO remove duplicate code
	    rt=self.RDS_data[PI]["RT"]
	    rt_valid=self.RDS_data[PI]["RT_valid"]
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
		textcolor="black"
	      else:
		textcolor="gray"	  
	      formatted_text=self.color_text(self.RDS_data[PI_ON]["PSN"],variant*2,variant*2+2,textcolor,segmentcolor)
	      self.RDS_data[PI]["EON"][PI_ON]["PSN"]=PS_ON_str
	      self.RDS_data[PI_ON]["PSN"]=PS_ON_str
	      #formatted_text="<font face='Courier New' color='%s'>%s</font>"%("purple",PS_ON_str)
	      self.signals.DataUpdateEvent.emit({'PI':PI_ON,'PSN':formatted_text})
	    if variant==4:#AF_ON
	      if self.debug:
		print("AF_ON method A")#TODO
	    if variant in range(5,10):#variant 5..9 -> mapped freqs
	      freq_TN=self.decode_AF_freq(array[4])
	      freq_ON=self.decode_AF_freq(array[5])
	      #lock in tuned network if freq_TN matches decoder frequency
	      if(self.RDS_data[PI].has_key("tuned_freq") and freq_TN==self.RDS_data[PI]["tuned_freq"]and not self.RDS_data[PI]["AF"].has_key("main")):
		if self.log:
		  print("main frequency found: station:%s, freq:%0.1fM"% (self.RDS_data[PI]["PSN"],freq_TN/1e6))
		self.RDS_data[PI]["AF"]["main"]=freq_TN
	      #lock in ON if TN is locked in
	      if(self.RDS_data[PI]["AF"].has_key("main") and self.RDS_data[PI]["AF"]["main"]==freq_TN and not self.RDS_data[PI_ON]["AF"].has_key("main")):
		if self.log:
		  print("mapped frequency found: station:%s, freq:%0.1fM"% (self.RDS_data[PI_ON]["PSN"],freq_ON/1e6))
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
	#else:#other group
	if 1==1:
	  if self.RDS_data[PI]["blockcounts"].has_key(groupType):
	      self.RDS_data[PI]["blockcounts"][groupType] +=1 #increment
	  else:
	      self.RDS_data[PI]["blockcounts"][groupType] = 1 #initialize (1st group of this type)
	  
	  #printdelay=50
	  printdelay=500
	  self.printcounter+=0#printing disabled
	  if self.printcounter == printdelay and self.debug:
	    #code.interact(local=locals())
	    for key in self.RDS_data:
	      if self.RDS_data[key].has_key("PSN"):
		psn=self.RDS_data[key]["PSN"]
	      else:
		psn="?"
	      print("%s(%s):"%(psn,key),end="")
	      pp.pprint(self.RDS_data[key]["blockcounts"])
	      if self.RDS_data[key].has_key("RT+"):
	        print("RT+:",end="")
	        pp.pprint(self.RDS_data[key]["RT+"])
	    self.printcounter=0
	    #print("group of type %s not decoded on station %s"% (groupType,PI))
    def decode_AF_freq(self,freq_raw):
      if freq_raw in range(1,205):#1..204
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
      0b1000:u"áàéèíìóòúùÑÇŞßiĲ",
      0b1001:u"âäêëîïôöûüñçş??ĳ",
      0b1100:u"ÁÀÉÈÍÌÓÒÚÙŘČŠŽĐĿ",
      0b1101:u"áàéèíìóòúùřčšžđŀ"}
      charlist=list(charstring)
      for i,char in enumerate(charstring):
      	#code.interact(local=locals())
	if ord(char)<= 0b01111111:
	  charlist[i]=char #use ascii
	else:
	  #split byte
	  alnr=(ord(char)&0xF0 )>>4 #upper 4 bit
	  index=ord(char)&0x0F #lower 4 bit
	  #code.interact(local=locals())
	  try:
	    charlist[i]=alphabet[alnr][index]
	  except KeyError:
	    charlist[i]='?'#symbol not decoded #TODO
	    pass
      return "".join(charlist)
    def color_text(self, text, start,end,textcolor,segmentcolor):
      formatted_text="<font face='Courier New' color='%s'>%s</font><font face='Courier New' color='%s'>%s</font><font face='Courier New' color='%s'>%s</font>"% (textcolor,text[:start],segmentcolor,text[start:end],textcolor,text[end:])
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
        self.label = Qt.QLabel(label)
        layout.addWidget(self.label)
        self.setLayout(layout)
        #self.decoder_to_PI={}
        self.PI_to_row={}
        self.table=QtGui.QTableWidget(self)
        rowcount=2
        self.table.setRowCount(rowcount)
        self.table.setColumnCount(9)
        self.table.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers) #disallow editing
          #Data
        empty_text32='________________________________'
        empty_text64='________________________________________________________________'
        #empty_text64='\xe4'*64
        self.data = {'ID':[ QtGui.QLabel() for i in range(rowcount)],
		'freq':[ QtGui.QLabel() for i in range(rowcount)],
                'name':[ QtGui.QLabel() for i in range(rowcount)],
                'PTY':[ QtGui.QLabel() for i in range(rowcount)],
                'AF':[ QtGui.QLabel() for i in range(rowcount)],
                'time':[ QtGui.QLabel() for i in range(rowcount)],
                'text':[ QtGui.QLabel("_"*64) for i in range(rowcount)],
                'quality':[ QtGui.QLabel() for i in range(rowcount)],
                'buttons':[]}
        #Enter data onto Table
        self.colorder=['ID','freq','name','PTY','AF','time','text','quality','buttons']
        horHeaders = []
        for n, key in enumerate(self.colorder):
        #for n, key in enumerate(sorted(self.data.keys())):
            horHeaders.append(key)
            for m, item in enumerate(self.data[key]):
	      if type(item)==int:#convert ints to strings
		newitem = QtGui.QTableWidgetItem(str(item))
		self.table.setItem(m, n, newitem)
	      elif isinstance(item,QtGui.QLabel):
		self.table.setCellWidget(m,n,item)
	      else:
                newitem = QtGui.QTableWidgetItem(item)
		self.table.setItem(m, n, newitem)
        for i in range(rowcount):#create buttons
	  button=QtGui.QPushButton("getDetails")
	  self.table.setCellWidget(i,self.table.columnCount()-1,button)
	  button.clicked.connect(functools.partial(self.getDetails, row=i))
	  #button.clicked.connect(self.getDetails)
        #Add Header
        layout.addWidget(self.label)
        layout.addWidget(self.table)
        
        self.table.setHorizontalHeaderLabels(horHeaders)  
        #self.table.setMaximumHeight(300)#TODO use dynamic value

        self.tmc_message_label=QtGui.QLabel("TMC messages:")

        
        self.event_filter=QtGui.QLineEdit()#QPlainTextEdit ?
        self.location_filter=QtGui.QLineEdit(u"Baden-Württemberg")

        button = QtGui.QPushButton("code.interact")
        button.clicked.connect(self.onCLick)
        layout.addWidget(button)
        self.freq_label=QtGui.QLabel("decoder frequencies:")
        layout.addWidget(self.freq_label)
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
        self.logOutput.setMaximumHeight(150)
        font = self.logOutput.font()
        font.setFamily("Courier")
        font.setPointSize(10)
        layout.addWidget(self.logOutput)
    def insert_empty_row(self):
      rowPosition = self.table.rowCount()
      self.table.insertRow(rowPosition)
      for col in range(self.table.columnCount()-1):#all labels except in last column -> buttons
	self.table.setCellWidget(rowPosition,col,QtGui.QLabel())
      button=QtGui.QPushButton("getDetails")
      self.table.setCellWidget(rowPosition,self.table.columnCount()-1,button)
      button.clicked.connect(functools.partial(self.getDetails, row=rowPosition))
    def display_data(self, event):
	#pp.pprint(event)
	if type(event)==dict and event.has_key('decoder_frequencies'):
	  self.freq_label.setText(event['decoder_frequencies'])
	if type(event)==dict and event.has_key('TMC_log'): 
	  ef=unicode(self.event_filter.text().toUtf8(), encoding="UTF-8").lower()
	  lf=unicode(self.location_filter.text().toUtf8(), encoding="UTF-8").lower()
	  text=unicode(event['TMC_log'], encoding="UTF-8").lower()
	  if not text.find(lf)==-1 and not text.find(ef)==-1:
	    self.logOutput.append(Qt.QString.fromUtf8(event['TMC_log']))
	#if type(event)==dict and event.has_key('row'): 
	if type(event)==dict and event.has_key('PI'): 
	  #row=event['row']
	  PI=event['PI']
	  if not self.PI_to_row.has_key(PI):
	    self.PI_to_row[PI]=len(self.PI_to_row)#zero for first PI seen, then count up
	    self.insert_empty_row()
	  row=self.PI_to_row[PI]
	  PIcol=self.colorder.index('ID')
	  self.table.cellWidget(row,PIcol).setText(PI)
	  
	  if event.has_key('freq'):
	    freqcol=self.colorder.index('freq')
	    item=self.table.cellWidget(row,freqcol)
	    item.setText(event['freq'])
	  if event.has_key('wrong_blocks'):
	    item=self.table.cellWidget(row,self.colorder.index('quality'))
	    quality_string="%i%% %s"% (100-2*event['wrong_blocks'],event['dots'])
	    item.setText(quality_string)
	  if event.has_key('PTY'):
	    item=self.table.cellWidget(row,self.colorder.index('PTY'))
	    item.setText(event['PTY'])
	  if event.has_key('flags'):
	    item=self.table.cellWidget(row,self.colorder.index('PTY'))
	    item.setToolTip(Qt.QString(event['flags']))
	  if event.has_key('string'):
	    item=self.table.cellWidget(row,event['col'])
	    item.setText(event['string'])
	  if event.has_key('tooltip'):
	    item=self.table.cellWidget(row,event['col'])
	    item.setToolTip(Qt.QString(event['tooltip'])) 
	  #if event.has_key('PI'):
	    ##setPI
	    #PIcol=self.colorder.index('ID')
	    ##rtpcol=self.colorder.index('RT+')
	    #rtcol=self.colorder.index('text')
	    #if not str(self.table.item(row,PIcol).text()) == event['PI']:
	      ##self.table.cellWidget(row,rtpcol).setText("")#clear RT+ on changed PI
	      #print("PI changed on row %i, cleared RT-tt"%row)
	      #self.table.cellWidget(row,rtcol).setToolTip(Qt.QString("")) 
	    #self.table.item(row,PIcol).setText(event['PI'])
	  if event.has_key('AF'):
	    #setAF
	    PIcol=self.colorder.index('AF')
	    self.table.cellWidget(row,PIcol).setText(str(event['AF']['number']))
	  if event.has_key('PSN'):
	    #setPSN
	    PSNcol=self.colorder.index('name')
	    item=self.table.cellWidget(row,PSNcol)
	    item.setText(event['PSN'])
	self.table.resizeColumnsToContents()
    def getDetails(self,row):
	PIcol=self.colorder.index('ID')
	PI=str(self.table.cellWidget(row,PIcol).text())
	#PI=
	#print("row:%i,PI:%s"%(row,PI))
	#print(self.tableobj.RDS_data[PI])
	table=chart.DataTable()
	table.addColumn('groupType')
	table.addColumn('numPackets')
	#ordered_blockcounts=self.tableobj.RDS_data["D00F"]['blockcounts']
	blockcounts=self.tableobj.RDS_data[PI]['blockcounts'].copy()
	del blockcounts['any']
	#lambda function removes last character of PI string (A or B) and sorts based on integer valure of number in front
	for key in sorted(blockcounts,key=lambda elem: int(elem[0:-1])):
	  count=blockcounts[key]
	  table.addRow([key+": "+str(count),count])
	mychart=chart.PieChart(table)
	view = chart.DialogViewer()
	view.setGraph(mychart)
	#view.resize(360, 240)
	#view.resize(380, 550)
	rds_data=self.tableobj.RDS_data[PI].copy()
	try:
	 del rds_data['blockcounts']
	 del rds_data['PSN_valid']
	 del rds_data['RT_valid']
	except KeyError:
	 pass
	l=QtGui.QLabel("Data:%s"%pp.pformat(rds_data))
	l.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse |QtCore.Qt.TextSelectableByKeyboard)
	l.setWordWrap(True)
	#l=QtGui.QLabel("Data:")
	view.layout().addWidget(l)
	#code.interact(local=locals())
	view.exec_()
    def onCLick(self):
	print("button clicked")
	code.interact(local=locals())
	#self.logOutput.clear()
	#self.reset_color()
	#pp.pprint(event)
if __name__ == "__main__":
    from PyQt4 import Qt
    import sys

 #   def valueChanged(frequency):
 #       print("Value updated - " + str(frequency))

    app = Qt.QApplication(sys.argv)
   # widget = RangeWidget(Range(0, 100, 10, 1, 100), valueChanged, "Test", "counter_slider", int)
    mainobj= rds_parser_table_qt_Signals()
    #mainobj=None
    widget = rds_parser_table_qt_Widget(mainobj,"TestLabel")
    widget.show()
    widget.setWindowTitle("Test Qt gui")
    widget.setGeometry(200,200,600,300)
    #code.interact(local=locals())
    sys.exit(app.exec_())

    widget = None
