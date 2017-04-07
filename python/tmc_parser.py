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

class tmc_parser(gr.sync_block):
    """
    docstring for block tmc_parser
    """
    def __init__(self, workdir,log,debug,writeDB):
        gr.sync_block.__init__(self,
            name="tmc_parser",
            in_sig=None,
            out_sig=None)
        self.message_port_register_in(pmt.intern('in'))
        self.set_msg_handler(pmt.intern('in'), self.handle_msg)
        self.qtwidget=tmc_parser_Widget(self)
    def handle_msg(self,msg):
        m=pmt.to_python(msg)
        self.qtwidget.updateui()
        print(m)
    def getqtwidget(self):
        return self.qtwidget
class tmc_parser_Widget(QtGui.QWidget):
    def updateui(self):
        print("updating ui")
    def filterChanged(self):
        print("filter changed")
    def __init__(self, parser):
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
        self.logOutput.setMaximumHeight(150)
        font = self.logOutput.font()
        font.setFamily("Courier")
        font.setPointSize(10)
        layout.addWidget(self.logOutput)
        self.clip = QtGui.QApplication.clipboard()
