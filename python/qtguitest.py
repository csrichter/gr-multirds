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
import code,pmt
from PyQt4 import Qt, QtCore, QtGui
import pprint
pp = pprint.PrettyPrinter()

from PyQt4.QtCore import QObject, pyqtSignal

class Signals(QObject):
    DataUpdateEvent = QtCore.pyqtSignal(dict)
    def __init__(self, parent=None):
	super(QtCore.QObject, self).__init__()   

class qtguitest(gr.sync_block):
    """
    docstring for block qtguitest
    """
    def __init__(self,signals,nPorts):
	#QObject.__init__()
        gr.sync_block.__init__(self,
            name="qtguitest",
            in_sig=None,
            out_sig=None)
	for i in range(0,nPorts):
	  self.message_port_register_in(pmt.intern('in%d'%i))
	  self.set_msg_handler(pmt.intern('in%d'%i), self.handle_msg)
	#self.message_port_register_in(pmt.intern('in1'))
	#self.set_msg_handler(pmt.intern('in1'), self.handle_msg)
	#code.interact(local=locals())
	self.signals=signals
    def handle_msg(self, msg):
	self.signals.DataUpdateEvent.emit({'string':pmt.to_python(msg)})
	print(msg)
class CRWidget(QtGui.QWidget):
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
        self.table.setColumnCount(6)
        self.table.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers) #disallow editing
          #Data
        
        data = {'ID':range(1,6),
		'freq':['97.0','101.3','104.6','107.7'], 
                'name':['foo','antenne1','bar','DieNeue'], 
                'AF':['7','8','9','5'],
                'text':['bla','bli','blu',u'blä'],
                'buttons':[]}
                 #Enter data onto Table
        horHeaders = []
        for n, key in enumerate(['ID','freq','name','AF','text','buttons']):
        #for n, key in enumerate(sorted(data.keys())):
            horHeaders.append(key)
            for m, item in enumerate(data[key]):
	      if type(item)==int:#convert ints to strings
		newitem = QtGui.QTableWidgetItem(str(item))
	      else:
                newitem = QtGui.QTableWidgetItem(item)
              self.table.setItem(m, n, newitem)
        for i in range(0,4):
	  button=QtGui.QPushButton("play")
	  self.table.setCellWidget(i,5,button)
	  button.clicked.connect(self.onCLick)
        
        #Add Header
        self.table.setHorizontalHeaderLabels(horHeaders)  
        layout.addWidget(self.label)
        layout.addWidget(self.table)
        
        self.table.setHorizontalHeaderLabels(horHeaders)  
        self.table.setMaximumHeight(250)#TODO use dynamic value
        test="""
        adkasldjkasd
        #ad
        asd
        as
        d
        asd
        asdas
        d
        as
        f
        as
        fa
        
        sfasfasfasfasofsa
        afasfasf
        """
        self.tmc_message_label=QtGui.QLabel("TMC messages:")
        #self.tmc_message_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByKeyboard|QtCore.Qt.TextSelectableByMouse)
        #self.tmc_message_label.setMaximumHeight(100)
        
        self.event_filter=QtGui.QLineEdit()#QPlainTextEdit ?
        self.location_filter=QtGui.QLineEdit()

        self.button = QtGui.QPushButton("i am a button")
        layout.addWidget(self.button)
        
        #self.filter_label=QtGui.QLabel()
        filter_layout = Qt.QHBoxLayout()
        filter_layout.addWidget(QtGui.QLabel("event filter:"))
        filter_layout.addWidget(self.event_filter)
        filter_layout.addWidget(QtGui.QLabel("location filter:"))
        filter_layout.addWidget(self.location_filter)
        #self.filter_label.setLayout(filter_layout)
        self.tmc_message_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        #self.tmc_message_label.setTextInteractionFlags(QtCore.Qt.NoTextInteraction)
        layout.addLayout(filter_layout)
        layout.addWidget(self.tmc_message_label)
        
        self.logOutput = Qt.QTextEdit(test)
        self.logOutput.setReadOnly(True)
        self.logOutput.setLineWrapMode(Qt.QTextEdit.NoWrap)
        self.logOutput.setMaximumHeight(100)
        font = self.logOutput.font()
        font.setFamily("Courier")
        font.setPointSize(10)
        layout.addWidget(self.logOutput)
        

        
    def display_data(self, event):
	#msg_type = event.data[0]
	#msg = unicode(event.data[1], errors='replace')
	#if (msg_type==0):     #program information
	#   self.label.setText(msg)
	#self.layout()
	pp.pprint(event)
	self.table.currentItem().setText(event['string'])
    def onCLick(self):
	print("button clicked")
	#pp.pprint(event)
if __name__ == "__main__":
    from PyQt4 import Qt
    import sys

 #   def valueChanged(frequency):
 #       print("Value updated - " + str(frequency))

    app = Qt.QApplication(sys.argv)
   # widget = RangeWidget(Range(0, 100, 10, 1, 100), valueChanged, "Test", "counter_slider", int)
    mainobj= Signals()
    #mainobj=None
    widget = CRWidget(mainobj,"TestLabel")
    widget.show()
    widget.setWindowTitle("Test Qt gui")
    widget.setGeometry(200,200,600,300)
    #code.interact(local=locals())
    #sys.exit(app.exec_())
    app.exec_(code.interact(local=locals()))
    widget = None
