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
import code,math,pmt,time

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
        self.last_station_indices=[0]*self.num_decoders
	self.message_port_register_out(pmt.intern('out'))
	self.timer=time.time()
	self.message_port_register_in(pmt.intern('ctrl'))
	self.set_msg_handler(pmt.intern('ctrl'), self.handle_ctrl_msg)
	self.searchMode=True
	self.index_fixed=[False]*self.num_decoders
    def freq_to_index(self,freq):
      startfreq=self.center_freq-self.samp_rate/2
      #freq=self.samp_rate*index/self.fft_len+startfreq
      #(freq-startfreq)*self.fft_len/self.samp_rate=index
      index=(freq-startfreq)*self.fft_len/self.samp_rate
      return index
    def index_to_freq(self,index):
      startfreq=self.center_freq-self.samp_rate/2
      freq=index*self.samp_rate/self.fft_len+startfreq
      return freq
    
    def handle_ctrl_msg(self,msg):
      m = pmt.pmt_to_python.pmt_to_dict(msg)
      if m.has_key("cmd") and m["cmd"]=="set_audio_freq":
	#print(m)
	#print(self.last_station_indices)
	freq_index=self.freq_to_index(m["freq"])
	if m["chan"]=="left" and freq_index<self.fft_len-5:
	  if self.last_station_indices[0]==freq_index:
	    self.index_fixed[0]=False
	    print("decoder 0 free")
	  else:
	    self.last_station_indices[0]=freq_index
	    self.index_fixed[0]=True
	    print("decoder 0 fixed to %i"%m["freq"])
	if m["chan"]=="right" and freq_index<self.fft_len-5:
	  if self.last_station_indices[1]==freq_index:
	    self.index_fixed[1]=False
	    print("decoder 1 free")
	  else:
	    self.last_station_indices[1]=freq_index
	    self.index_fixed[1]=True
	    print("decoder 1 fixed to %i"%m["freq"])
	#print(self.last_station_indices)
      if m.has_key("cmd") and m["cmd"]=="switch mode":
	self.searchMode=not self.searchMode
	print("searchMode: %s"%self.searchMode)
    def set_center_freq(self, freq=None):
      self.index_fixed=[False]*self.num_decoders#free all decoders (freq wouldn't match anyways)
      if freq is not None:
	      if isinstance(freq, float) or isinstance(freq, int):
		      self.center_freq=freq
	      else:
		      self.center_freq = int(freq)
    def work(self, input_items, output_items):
      if time.time()-self.timer<1:#every 1 seconds
	return len(input_items[0])
      elif self.searchMode:
      #in0 = input_items[0]
      #ii=input_items
        carrier_width=2
        carrier=self.fft_len/2
        numbers=np.delete(input_items[0][0],range(carrier-carrier_width,carrier+carrier_width+1))#read input and disregard center (hackrf LO)
        #threshold=40# uni
        #threshold=60#home
        threshold=np.mean(numbers)#2017-03-21 fft-multi-decoder
        #minimum number of consecutive maximums (in fft domain) to consider signal as station:
        #min_consec_max_threshold=1#uni
        #min_consec_max_threshold=3#home
        min_consec_max_threshold=6#2017-03-21 fft-multi-decoder
        fuzzyness=2#uni
        #fuzzyness=10#home
        
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
          
        same_station_threshold=int(100000*self.fft_len/self.samp_rate)#0.1mhz
        #group similar indices:
        lastindex=0
        group=None
        station_indices_grouped=[]
        for idx in station_indices:
          if group==None: #start new group
            group=[idx]
          elif (idx-lastindex)<same_station_threshold: #add to group
            group.append(idx)
          elif group!=None:#finish group
            group_mean=np.mean(np.array(group))
            station_indices_grouped.append(int(group_mean))
            group=[idx]#first non-member of group
          lastindex=idx
        
        
        #sort station_indices by signal strength (dont bother decoding quiet stations)
        station_indices_sorted=sorted(station_indices_grouped,reverse=True,key=lambda elem:numbers[elem])
        
        #prevents back and forth switching if two station have similar signal strength
        
        
        station_indices_trunc=list(station_indices_sorted)#copy list
        del station_indices_trunc[self.num_decoders:]#remove non decodable (too quiet) incidices
        
        station_indices_tune=[0]*self.num_decoders
        
        same_station_threshold=int(500000*self.fft_len/self.samp_rate)#0.5mhz
        #same_station_threshold=3
        new_stations=[]
        #add fixed stations:
        for i,old_freq in enumerate(self.last_station_indices):
	  if self.index_fixed[i]:
	    station_indices_tune[i]=old_freq
        #change existing/add new:
        for new_freq in station_indices_trunc:
	  added=False
	  for i,old_freq in enumerate(self.last_station_indices):
	    if abs(old_freq-new_freq)<same_station_threshold:
	      station_indices_tune[i]=new_freq
	      added=True
	  if not added:
	    new_stations.append(new_freq)
	#print("tune1:%s"%station_indices_tune)
	#print("new_1 %s"%new_stations)
	
	for i,tune_freq in enumerate(station_indices_tune):
	  if tune_freq == 0 and len(new_stations)>0:
	    station_indices_tune[i]=new_stations.pop()
	#print("tune2:%s"%station_indices_tune)
        #print("new_2 %s"%new_stations)
        
        self.last_station_indices=station_indices_tune#save current stations to compare againts next

        station_strength=[]
        station_freqs=[]
        #index to freq:
        for index in station_indices_tune:
          startfreq=self.center_freq-self.samp_rate/2
          freq=self.samp_rate*index/self.fft_len+startfreq
          freq+=30000#add 30k because detected max often too low
          num_decimals=int(round(math.log(self.snapto,10)))
          station_freqs.append(round(freq,-num_decimals))
          station_strength.append(round(numbers[index],-2))
        for i in range(0,min(self.num_decoders,len(station_freqs))):
	  msg_string=str(i+1)+" "+str(station_freqs[i])
	  send_pmt = pmt.string_to_symbol(msg_string)
	  self.message_port_pub(pmt.intern('out'), send_pmt)
	if self.debug:
	  #print(max_indices)
	  #print(np.mean(numbers))
	  #print(len(max_indices))
	  #print(station_indices)
	  #print(station_indices_grouped)
	  #print(station_indices_sorted)
	  #print(station_indices_tune)
	  #print(station_strength)
	  print(station_freqs)

        return len(input_items[0])
      else:
	return len(input_items[0])

