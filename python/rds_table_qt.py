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

class rds_table_qt_Signals(QObject):
    DataUpdateEvent = QtCore.pyqtSignal(dict)
    def __init__(self, parent=None):
	super(QtCore.QObject, self).__init__()   

class rds_table_qt(gr.sync_block):
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
	#self.message_port_register_in(pmt.intern('in1'))
	#self.message_port_register_in(pmt.intern('in2'))
	#self.set_msg_handler(pmt.intern('in1'), functools.partial(self.handle_msg, port=1))
	#self.set_msg_handler(pmt.intern('in2'), functools.partial(self.handle_msg, port=2))
	#code.interact(local=locals())
	self.signals=signals
#/* type 0 = PI
 #* type 1 = PS
 #* type 2 = PTY
 #* type 3 = flagstring: TP, TA, MuSp, MoSt, AH, CMP, stPTY
 #* type 4 = RadioText 
 #* type 5 = ClockTime
 #* type 6 = Alternative Frequencies 
 #* type 7 = decode errors int (out  of 50), 51 == no_sync */
    def handle_msg(self, msg, port):
	t = pmt.to_long(pmt.tuple_ref(msg, 0))
	m = pmt.symbol_to_string(pmt.tuple_ref(msg, 1))
	#code.interact(local=locals())
	if(t==0):
	    self.signals.DataUpdateEvent.emit({'col':0,'row':port,'string':m})
		#self.PI=m
		#self.stations[str(port)+"PI"]=m
	elif(t==1):
	    self.signals.DataUpdateEvent.emit({'col':2,'row':port,'string':m})
		#self.PS=m
		#self.stations[str(port)+"PS"]=m
	elif(t==4):
	    self.signals.DataUpdateEvent.emit({'col':5,'row':port,'string':m})
	    #self.RT=m
	    #self.stations[str(port)+"RT"]=m
	elif(t==6):#alt freq
	    #print("################alt freqs##################")
	    #freqspmt=pmt.tuple_ref(msg, 1)
	    #print(m)
	    #pp.pprint(pmt.to_python(freqspmt)
	    self.signals.DataUpdateEvent.emit({'col':3,'row':port,'string':m})
	elif(t==5):#time
	    self.signals.DataUpdateEvent.emit({'col':4,'row':port,'string':m})

	
    #def handle_msg(self, msg):
#	self.signals.DataUpdateEvent.emit({'string':pmt.to_python(msg)})
#	print(msg)
class rds_table_qt_Widget(QtGui.QWidget):
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
        
        self.data = {'ID':range(1,6),
		'freq':['','','',''],
                'name':['','','',''],
                'AF':['','','',''],
                'time':['','','',''],
                'text':['','','',''],
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
        for i in range(0,4):
	  button=QtGui.QPushButton("play")
	  self.table.setCellWidget(i,self.table.columnCount()-1,button)
	  button.clicked.connect(self.onCLick)
        
        #Add Header
        self.table.setHorizontalHeaderLabels(horHeaders)  
        layout.addWidget(self.label)
        layout.addWidget(self.table)
        self.button = QtGui.QPushButton("i am a button")
        layout.addWidget(self.button)
        
    def display_data(self, event):
	#pp.pprint(event)
	if type(event)==dict:
	  if type(event['row']) == int and type(event['col']) == int:
	    item=self.table.item(event['row'],event['col'])
	    if event['col']==0 and event['string']!=item.text(): #clear data if PI changed
	      for col in range(1,self.table.columnCount()-1):
		self.table.item(event['row'],col).setText('')
	    if item.text()==event['string']:
	      item.setTextColor(QtCore.Qt.black)
	    else:
	      item.setTextColor(QtCore.Qt.green)
	    item.setText(event['string'])
	    item.setFont(QtGui.QFont("Courier New"))
	    #print("table updated")
	    self.table.resizeColumnsToContents()
	  else:
	    self.table.currentItem().setText(event['string'])
    def reset_color(self):
      for i in range(0,self.table.rowCount()):
	for j in range(0,self.table.columnCount()):
	  item = self.table.item(i,j)
	  #code.interact(local=locals())
	  #print(item.type())
	  if item != '':
	    try:
	      item.setTextColor(QtCore.Qt.black)
	    except:
	      pass
      #for item in self.table.items():
	#item.setTextColor(QtCore.Qt.black)
    def onCLick(self):
	print("button clicked")
	self.reset_color()
	#pp.pprint(event)
if __name__ == "__main__":
    from PyQt4 import Qt
    import sys

 #   def valueChanged(frequency):
 #       print("Value updated - " + str(frequency))

    app = Qt.QApplication(sys.argv)
   # widget = RangeWidget(Range(0, 100, 10, 1, 100), valueChanged, "Test", "counter_slider", int)
    mainobj= rds_table_qt_Signals()
    #mainobj=None
    widget = rds_table_qt_Widget(mainobj,"TestLabel")
    widget.show()
    widget.setWindowTitle("Test Qt gui")
    widget.setGeometry(200,200,600,300)
    #code.interact(local=locals())
    sys.exit(app.exec_())

    widget = None
