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

import numpy
from gnuradio import gr
import code,pmt,functools
from PyQt4 import Qt, QtCore, QtGui
import pprint
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
	self.RTdict={}
        self.RTvalid={}
        self.PSNdict={}
        self.PSNvalid={}
        self.AFdata={}
        self.blockcounts={}
        self.printcounter=0
    def handle_msg(self, msg, port):
	#code.interact(local=locals())
	array=pmt.to_python(msg)[1]
	groupNR=array[2]&0b11110000
	groupVar=array[2]&0b00001000
	if (groupVar == 0):
		groupType=str(groupNR >> 4)+"A"
	else:
		groupType=str(groupNR >> 4)+"B"
	#print("raw:"+str(pmt.to_python(msg))+"\n")
	PI="%02X%02X" %(array[0],array[1])
	#print("1st block:"+str(array[0])+","+str(array[1])+"= ID: %s" %PI)
	#print("2st block:"+str(array[2])+","+str(array[3])+"= type:"+groupType)
	#print("3st block:"+str(array[4])+","+str(array[5]))
	#print("4st block:"+str(array[6])+","+str(array[7]))
	if (groupType == "0A"):#AF PSN
	  adr=array[3]&0b00000011
	  segment=self.decode_chars(chr(array[6])+chr(array[7]))
	  if(not self.PSNdict.has_key(PI)):#initialize dict
	    self.PSNdict[PI]="_"*8
	    self.PSNvalid[PI]=[False]*8
	    self.AFdata[PI]={}
	  #1110 0000 = no AF
	  #1110 0001 = 1AF
	  #1111 1001 = 25AF
	  
	  if(array[5]>= 224 and array[5]<= 249):
	    print("AF1 detected")
	    self.AFdata[PI]['number']=array[5]-224
	    self.signals.DataUpdateEvent.emit({'row':port,'AF':self.AFdata[PI]})
	  if(array[6]>= 224 and array[6]<= 249):
	    print("AF2 detected")
	  
	  name_list=list(self.PSNdict[PI])
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
	    self.PSNdict[PI]="_"*8
	    self.PSNvalid[PI]=[False]*8
	  self.PSNvalid[PI][adr*2:adr*2+2]=[True] *2
	  self.PSNdict[PI]="".join(name_list)
	  #determine if text is valid
	  valid=True
	  for i in range(0,8):
	   if (not self.PSNvalid[PI][i]):
	    valid = False
	  if(valid):
	   textcolor="black"
	  else:
	   textcolor="gray"	  
	  formatted_text=self.color_text(self.PSNdict[PI],adr*2,adr*2+2,textcolor,segmentcolor)
	  self.signals.DataUpdateEvent.emit({'col':5,'row':port,'PI':PI,'PSN':formatted_text})
	elif (groupType == "2A"):#RT radiotext
	  if(not self.RTdict.has_key(PI)):#initialize dict
	    self.RTdict[PI]="_"*64
	    self.RTvalid[PI]=[False]*64
	  else:
	   adr=array[3]&0b00001111
	   segment=self.decode_chars(chr(array[4])+chr(array[5])+chr(array[6])+chr(array[7]))
	   #print("RT:adress: %d, segment:%s"%(adr,segment))
	   #self.signals.DataUpdateEvent.emit({'col':5,'row':port,'PI':PI,'groupType':groupType,'adress':adr,'segment':segment})
	   text_list=list(self.RTdict[PI])
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
	     self.RTdict[PI]="_"*64
	     self.RTvalid[PI]=[False]*64
	  
	   self.RTvalid[PI][adr*4:adr*4+4]=[True] *4
	   self.RTdict[PI]="".join(text_list)
	   
	   #determine if (new) text is valid
	   valid=True
	   for i in range(0,text_end):
	     if (not self.RTvalid[PI][i]):
	      valid = False
	   if(valid):
	     textcolor="black"
	   else:
	     textcolor="gray"
	   #formatted_text="<font face='Courier New' color='%s'>%s</font><font face='Courier New' color='%s'>%s</font><font face='Courier New' color='%s'>%s</font>"% (textcolor,self.RTdict[PI][:adr*4],segmentcolor,self.RTdict[PI][adr*4:adr*4+4],textcolor,self.RTdict[PI][adr*4+4:])
	   formatted_text=self.color_text(self.RTdict[PI],adr*4,adr*4+4,textcolor,segmentcolor)
	   #print(self.RTdict[PI]+" valid:"+str(valid)+"valarr:"+str(self.RTvalid[PI]))


	   self.signals.DataUpdateEvent.emit({'col':5,'row':port,'PI':PI,'string':formatted_text})
	   #code.interact(local=locals())
	elif (groupType == "4A"):#CT clock time
	  datecode=((array[3] & 0x03) << 15) | (array[4] <<7)|((array[5] >> 1) & 0x7f)
	  hours=((array[5] & 0x1) << 4) | ((array[6] >> 4) & 0x0f)
	  minutes=((array[6]>>6)&0x0F)|((array[7] >>6)&0x3)
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
	  datestring="%02i.%02i.%4i, %02i:%02i (%+.1fh)" % (day,month,year,hours,minutes,local_time_offset)
	  self.signals.DataUpdateEvent.emit({'col':4,'row':port,'PI':PI,'string':datestring})
	else:#other group
	  printfreq=100
	  self.printcounter+=1
	  if self.blockcounts.has_key(PI):#1st group on this station
	    if self.blockcounts[PI].has_key(groupType):#1st group of this type
	      self.blockcounts[PI][groupType] +=1 #increment
	    else:
	      self.blockcounts[PI][groupType] = 1 #initialize
	  else:
	    self.blockcounts[PI]={}#initialize dict
	  if self.printcounter == printfreq:
	    pp.pprint(self.blockcounts)
	    self.printcounter=0
	    #print("group of type %s not decoded on station %s"% (groupType,PI))
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
        self.table.setColumnCount(7)
        self.table.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers) #disallow editing
          #Data
        empty_text32='________________________________'
        empty_text64='________________________________________________________________'
        #empty_text64='\xe4'*64
        self.data = {'ID':range(1,6),
		'freq':['','','',''],
                'name':[],
                'AF':['','','',''],
                'time':[],
                'text':[],
                'buttons':[]}
        #Enter data onto Table
        horHeaders = []
        for n, key in enumerate(['ID','freq','name','AF','time','text','buttons']):
        #for n, key in enumerate(sorted(self.data.keys())):
            horHeaders.append(key)
            for m, item in enumerate(self.data[key]):
	      if type(item)==int:#convert ints to strings
		newitem = QtGui.QTableWidgetItem(str(item))
	      else:
                newitem = QtGui.QTableWidgetItem(item)
              self.table.setItem(m, n, newitem)
        for i in range(0,4):#create buttons
	  button=QtGui.QPushButton("play")
	  self.table.setCellWidget(i,self.table.columnCount()-1,button)
	  button.clicked.connect(self.onCLick)
        for i in range(0,4):#create text labels
	  label=QtGui.QLabel(empty_text64)
	  #label.setFont(QtGui.QFont("Courier New"))
	  self.table.setCellWidget(i,self.table.columnCount()-2,label)
	for i in range(0,4):#create name labels
	  label=QtGui.QLabel("_"*8)
	  #label.setFont(QtGui.QFont("Courier New"))
	  self.table.setCellWidget(i,2,label)
	for i in range(0,4):#create time labels
	  label=QtGui.QLabel()
	  #label.setFont(QtGui.QFont("Courier New"))
	  self.table.setCellWidget(i,4,label) 	
        #Add Header
        self.table.setHorizontalHeaderLabels(horHeaders)  
        layout.addWidget(self.label)
        layout.addWidget(self.table)
        self.button = QtGui.QPushButton("i am a button")
        layout.addWidget(self.button)
        
    def display_data(self, event):
	#pp.pprint(event)
	if type(event)==dict and event.has_key('row'):
	  if event.has_key('string'):
	    item=self.table.cellWidget(event['row'],event['col'])
	    item.setText(event['string'])
	  if event.has_key('PI'):
	    #setPI
	    PIcol=0
	    self.table.item(event['row'],PIcol).setText(event['PI'])
	  if event.has_key('AF'):
	    #setAF
	    PIcol=3
	    self.table.item(event['row'],PIcol).setText(event['AF']['number'])
	  if event.has_key('PSN'):
	    #setPSN
	    PSNcol=2
	    item=self.table.cellWidget(event['row'],PSNcol)
	    item.setText(event['PSN'])
	self.table.resizeColumnsToContents()
    #def reset_color(self):
      #for i in range(0,self.table.rowCount()):
	#for j in range(0,self.table.columnCount()):
	  #item = self.table.item(i,j)
	  ##code.interact(local=locals())
	  ##print(item.type())
	  #if item != '':
	    #try:
	      #item.setTextColor(QtCore.Qt.black)
	    #except:
	      #pass
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
