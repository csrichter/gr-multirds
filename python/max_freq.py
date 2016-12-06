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

import numpy as np
from gnuradio import gr
import code,math,pmt

class max_freq(gr.sync_block):
    """
    docstring for block max_freq
    """
    def __init__(self, fft_len=1024,num_decoders=4,center_freq=0,samp_rate=0,round_to=100e3,debug=False):
        gr.sync_block.__init__(self,
            name="max_freq",
            in_sig=[(np.float32,fft_len)],
            out_sig=None)
        self.fft_len=fft_len
        self.num_decoders=num_decoders
        self.center_freq=center_freq
        self.samp_rate=samp_rate
        self.snapto=round_to
        self.debug=debug
        self.last_station_freqs=[]
	self.message_port_register_out(pmt.intern('out'))
    def set_center_freq(self, freq=None):
		if freq is not None:
			if isinstance(freq, float) or isinstance(freq, int):
				self.center_freq=freq
			else:
				self.center_freq = int(freq)
    def work(self, input_items, output_items):
      #in0 = input_items[0]
      #ii=input_items
        carrier_width=2
        carrier=self.fft_len/2
        numbers=np.delete(input_items[0][0],range(carrier-carrier_width,carrier+carrier_width+1))#read input and disregard center (hackrf LO)
        #threshold=100# uni
        threshold=60#home
        #minimum number of consecutive maximums (in fft domain) to consider signal as station:
        #min_consec_max_threshold=1#uni
        min_consec_max_threshold=3#home
        #fuzzyness=2#uni
        fuzzyness=10#home
        
        #TODO: what if no numbers over threshold?
        #TODO auto threshold
        #max_indices=[[421, 428, 429, 430, 431, 432, 433, 434, 436, 437, 438, 831, 832, 837, 840, 841, 842, 843, 844, 845, 846, 847, 848, 849, 850, 851,852, 853, 854, 855, 856, 857]]
        max_indices=np.where(numbers>threshold)
        station_indices=[]
        try:
          last_index=max_indices[0][0]
        except IndexError:
          last_index=0
        count=1#counts number of consecutive maximums
        threshold_reached=False

#        max_indices[0].append(0)#to detect last station
        max_indices=np.append(max_indices,0)#to detect last station
        #try:
	 
         #max_indices.remove(self.fft_len/2)#suppress local oscillator of hackrf
        #except ValueError:
	  #pass
        for i in max_indices:
          if abs(i-last_index) <= fuzzyness:
            count+=i-last_index
          else:#last streak ended
            if(threshold_reached):
              station_indices.append(last_index-int(count/2))#use center of max-streak
              threshold_reached=False
              count=1
            else:#last streak didn't reach threshold -> no station
              count=1
          if count>=min_consec_max_threshold:
            threshold_reached=True
          last_index=i
        #sort station_indices by signal strength (dont bother decoding quiet stations)
        station_indices_sorted=sorted(station_indices,reverse=True,key=lambda elem:numbers[elem])
        
        #prevents back and forth switching if two station have similar signal strength
        station_indices_tune=list(station_indices_sorted)#copy list
        del station_indices_tune[self.num_decoders:]#remove non decodable incidices
        station_indices_tune.sort()
        
        station_strength=[]
        station_freqs=[]
        #index to freq:
        for index in station_indices_tune:
          startfreq=self.center_freq-self.samp_rate/2
          freq=self.samp_rate*index/self.fft_len+startfreq
          num_decimals=int(round(math.log(self.snapto,10)))
          station_freqs.append(round(freq,-num_decimals))
          station_strength.append(round(numbers[index],-2))
        for i in range(0,min(self.num_decoders,len(station_freqs))):
	  msg_string=str(i+1)+" "+str(station_freqs[i])
	  send_pmt = pmt.string_to_symbol(msg_string)
	  self.message_port_pub(pmt.intern('out'), send_pmt)
	if self.debug:
	  print(max_indices)
	  print(station_indices_sorted)
	  print(station_indices_tune)
	  print(station_strength)
	  print(station_freqs)
	  
	self.last_station_freqs=station_freqs
        return len(input_items[0])

