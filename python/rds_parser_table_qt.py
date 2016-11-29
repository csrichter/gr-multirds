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
import pmt,functools,csv,md5
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
    def __init__(self,signals,nPorts):
	#QObject.__init__()
        gr.sync_block.__init__(self,
            name="RDS Table",
            in_sig=None,
            out_sig=None)
	for i in range(0,nPorts):
	  self.message_port_register_in(pmt.intern('in%d'%i))
	  self.set_msg_handler(pmt.intern('in%d'%i), functools.partial(self.handle_msg, port=i))

	self.signals=signals
	self.RDS_data={}
        self.printcounter=0
        self.ODA_application_names={}
        self.TMC_data={}
        self.colorder=['ID','freq','name','PTY','AF','time','text','quality','buttons']
        #workdir="/user/wire2/richter/hackrf_prototypes/"
        workdir="/media/clemens/intdaten/uni_bulk/forschungsarbeit/hackrf_prototypes/"
        reader = csv.reader(open(workdir+'RDS_ODA AIDs_names_only.csv'), delimiter=',', quotechar='"')
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
    def handle_msg(self, msg, port):
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
	  self.RDS_data[PI]={}
	  self.RDS_data[PI]["blockcounts"]={}
	  self.RDS_data[PI]["blockcounts"]["any"]=0
	  self.RDS_data[PI]["AID_list"]={}
	  self.RDS_data[PI]["PSN"]="_"*8
	  self.RDS_data[PI]["PSN_valid"]=[False]*8
	  self.RDS_data[PI]["AF"]={}
	  self.RDS_data[PI]["DI"]=[2,2,2,2]
	  print("found station %s"%PI)
	self.RDS_data[PI]["blockcounts"]["any"]+=1
	if self.RDS_data[PI]["blockcounts"]["any"]==5:
	  self.RDS_data[PI]["blockcounts"]["any"]=0
	dots="."*self.RDS_data[PI]["blockcounts"]["any"]
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
	  flag_string="TP:%i, TA:%i, MS:%i, DI:%s"%(TP,TA,MS,str(self.RDS_data[PI]["DI"]))
	  self.signals.DataUpdateEvent.emit({'row':port,'PI':PI,'flags':flag_string})
	  #1110 0000 = no AF
	  #1110 0001 = 1AF
	  #1111 1001 = 25AF
	  
	  if(array[5]>= 224 and array[5]<= 249):
	    print("AF1 detected")
	    self.RDS_data[PI]["AF"]['number']=array[5]-224
	    self.signals.DataUpdateEvent.emit({'row':port,'AF':self.RDS_data[PI]["AF"]})
	  if(array[6]>= 224 and array[6]<= 249):
	    print("AF2 detected")
	  
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
	  
	elif (groupType == "2A"):#RT radiotext
	  
	  if(not self.RDS_data[PI].has_key("RT")):#initialize variables
	    self.RDS_data[PI]["RT"]="_"*64
	    self.RDS_data[PI]["RT_valid"]=[False]*64
	    self.RDS_data[PI]["RT_all_valid"]=False
	  else:
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
	    app_name=self.ODA_application_names[AID]
	    self.RDS_data[PI]["AID_list"][AID]={}
	    self.RDS_data[PI]["AID_list"][AID]["groupType"]=app_group
	    self.RDS_data[PI]["AID_list"][AID]["app_name"]=app_name
	    self.RDS_data[PI]["AID_list"][AID]["app_data"]=app_data
	    print("new ODA: AID:%i, name:%s, app_group:%s, station:%s" %(AID,app_name,app_group,PI))
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
	elif self.RDS_data[PI]["AID_list"].has_key(52550) and self.RDS_data[PI]["AID_list"][52550]["groupType"]==groupType:
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
	        print(message_string)
	    except KeyError:
	      #print("location '%i' not found"%tmc_location)
	      pass
	    #code.interact(local=locals())
	  else:#alert plus or provider info
	    adr=tmc_x&0xf
	    if  4 <= adr and adr <= 9:
	      #print("TMC-info")
	      a=0
	    else:
	      a=0
	      #print("alert plus")
	    
	 
	#RadioText+ (grouptype mostly 12A):
	elif self.RDS_data[PI]["AID_list"].has_key(19415) and self.RDS_data[PI]["AID_list"][19415]["groupType"]==groupType:
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
	  if not self.RDS_data[PI].has_key("RT+"):
	    self.RDS_data[PI]["RT+"]={}
	  if(self.RDS_data[PI].has_key("RT") and self.RDS_data[PI]["RT_all_valid"]):#TODO better (more fine grained) detection of valid RT+ info
	    rt=self.RDS_data[PI]["RT"]
	    if not tag1_type=="DUMMY_CLASS":
	      self.RDS_data[PI]["RT+"][tag1_type]=rt[tag1_start:tag1_start+tag1_len+1]
	    if not tag2_type=="DUMMY_CLASS":
	      self.RDS_data[PI]["RT+"][tag2_type]=rt[tag2_start:tag2_start+tag2_len+1]

	  if(tag1_type=="ITEM.ARTIST"and tag2_type=="ITEM.TITLE" and self.RDS_data[PI].has_key("RT") and self.RDS_data[PI]["RT_all_valid"]):
	    rt=self.RDS_data[PI]["RT"]
	    artist=rt[tag1_start:tag1_start+tag1_len+1]
	    song=rt[tag2_start:tag2_start+tag2_len+1]
	    formatted_text="%s by %s"%(song,artist)
	    rtcol=self.colorder.index('text')
	    self.signals.DataUpdateEvent.emit({'col':rtcol,'row':port,'PI':PI,'tooltip':formatted_text})
	    #self.signals.DataUpdateEvent.emit({'col':8,'row':port,'PI':PI,'string':formatted_text})  
	  elif(not tag1_type=="ITEM.ARTIST" and not tag1_type=="DUMMY_CLASS"):
	    print("%s:RT+: tag1_type:%s, tag2_type:%s"%(PI,tag1_type,tag2_type))  
	else:#other group
	  printdelay=50
	  self.printcounter+=1
	  if self.RDS_data[PI]["blockcounts"].has_key(groupType):
	      self.RDS_data[PI]["blockcounts"][groupType] +=1 #increment
	  else:
	      self.RDS_data[PI]["blockcounts"][groupType] = 1 #initialize (1st group of this type)

	  if self.printcounter == printdelay:
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
	    charlist[i]=char
	    pass
      return "".join(charlist)
    def color_text(self, text, start,end,textcolor,segmentcolor):
      formatted_text="<font face='Courier New' color='%s'>%s</font><font face='Courier New' color='%s'>%s</font><font face='Courier New' color='%s'>%s</font>"% (textcolor,text[:start],segmentcolor,text[start:end],textcolor,text[end:])
      return formatted_text
class rds_parser_table_qt_Widget(QtGui.QWidget):
    def __init__(self, signals,label):
	print("gui initializing")
	self.signals = signals
	self.signals.DataUpdateEvent.connect(self.display_data)
        """ Creates the QT Range widget """
        QtGui.QWidget.__init__(self)
        layout = Qt.QVBoxLayout()
        self.label = Qt.QLabel(label)
        layout.addWidget(self.label)
        self.setLayout(layout)
        self.table=QtGui.QTableWidget(self)
        self.table.setRowCount(5)
        self.table.setColumnCount(9)
        self.table.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers) #disallow editing
          #Data
        empty_text32='________________________________'
        empty_text64='________________________________________________________________'
        #empty_text64='\xe4'*64
        self.data = {'ID':range(1,6),
		'freq':['','','',''],
                'name':[ QtGui.QLabel() for i in range(4)],
                'PTY':[ QtGui.QLabel() for i in range(4)],
                #'flags':[ QtGui.QLabel() for i in range(4)],
                'AF':['','','',''],
                'time':[ QtGui.QLabel() for i in range(4)],
                'text':[ QtGui.QLabel("_"*64) for i in range(4)],
                #'RT+':[ QtGui.QLabel() for i in range(4)],
                'quality':[ QtGui.QLabel() for i in range(4)],
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
        for i in range(0,4):#create buttons
	  button=QtGui.QPushButton("play")
	  self.table.setCellWidget(i,self.table.columnCount()-1,button)
	  button.clicked.connect(self.onCLick)
        #Add Header
        self.table.setHorizontalHeaderLabels(horHeaders)  
        self.tmc_message_label=QtGui.QLabel("TMC messages:")
        self.event_filter=QtGui.QLineEdit()#QPlainTextEdit ?
        self.location_filter=QtGui.QLineEdit()
        layout.addWidget(self.label)
        layout.addWidget(self.table)
        self.button = QtGui.QPushButton("i am a button")
        layout.addWidget(self.button)
        layout.addWidget(self.tmc_message_label)
        layout.addWidget(self.event_filter)
        layout.addWidget(self.location_filter)
        
    def display_data(self, event):
	#pp.pprint(event)
	if type(event)==dict and event.has_key('row'): 
	  if event.has_key('wrong_blocks'):
	    item=self.table.cellWidget(event['row'],self.colorder.index('quality'))
	    quality_string="%i%% %s"% (100-2*event['wrong_blocks'],event['dots'])
	    item.setText(quality_string)
	  if event.has_key('PTY'):
	    item=self.table.cellWidget(event['row'],self.colorder.index('PTY'))
	    item.setText(event['PTY'])
	  if event.has_key('flags'):
	    item=self.table.cellWidget(event['row'],self.colorder.index('PTY'))
	    item.setToolTip(Qt.QString(event['flags']))
	  if event.has_key('string'):
	    item=self.table.cellWidget(event['row'],event['col'])
	    item.setText(event['string'])
	  if event.has_key('tooltip'):
	    item=self.table.cellWidget(event['row'],event['col'])
	    item.setToolTip(Qt.QString(event['tooltip'])) 
	  if event.has_key('PI'):
	    #setPI
	    PIcol=self.colorder.index('ID')
	    #rtpcol=self.colorder.index('RT+')
	    rtcol=self.colorder.index('text')
	    if not self.table.item(event['row'],PIcol).text() == event['PI']:
	      #self.table.cellWidget(event['row'],rtpcol).setText("")#clear RT+ on changed PI
	      self.table.cellWidget(event['row'],rtcol).setToolTip(Qt.QString("")) 
	    self.table.item(event['row'],PIcol).setText(event['PI'])
	  if event.has_key('AF'):
	    #setAF
	    PIcol=self.colorder.index('AF')
	    self.table.item(event['row'],PIcol).setText(event['AF']['number'])
	  if event.has_key('PSN'):
	    #setPSN
	    PSNcol=self.colorder.index('name')
	    item=self.table.cellWidget(event['row'],PSNcol)
	    item.setText(event['PSN'])
	self.table.resizeColumnsToContents()
    def onCLick(self):
	print("button clicked")
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
