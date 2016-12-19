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
        self.last_station_indices=[0]*self.num_decoders
	self.message_port_register_out(pmt.intern('out'))
	self.counter=0
	self.message_port_register_in(pmt.intern('ctrl'))
	self.set_msg_handler(pmt.intern('ctrl'), self.handle_ctrl_msg)
    def handle_ctrl_msg(self,msg):
      m = pmt.pmt_to_python.pmt_to_dict(msg)
      print(m)
    def set_center_freq(self, freq=None):
		if freq is not None:
			if isinstance(freq, float) or isinstance(freq, int):
				self.center_freq=freq
			else:
				self.center_freq = int(freq)
    def work(self, input_items, output_items):
      if self.counter<5:
	self.counter+=1
	return len(input_items[0])
      else:
	self.counter=0
      #in0 = input_items[0]
      #ii=input_items
        carrier_width=2
        carrier=self.fft_len/2
        numbers=np.delete(input_items[0][0],range(carrier-carrier_width,carrier+carrier_width+1))#read input and disregard center (hackrf LO)
        threshold=40# uni
        #threshold=60#home
        #minimum number of consecutive maximums (in fft domain) to consider signal as station:
        #min_consec_max_threshold=1#uni
        min_consec_max_threshold=3#home
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
        #sort station_indices by signal strength (dont bother decoding quiet stations)
        station_indices_sorted=sorted(station_indices,reverse=True,key=lambda elem:numbers[elem])
        
        #prevents back and forth switching if two station have similar signal strength
        station_indices_trunc=list(station_indices_sorted)#copy list
        del station_indices_trunc[self.num_decoders:]#remove non decodable incidices
        
        ###############################
        #comparelist=[]
        #for freq in station_indices_trunc:
	  #comparelist.append({"freq":freq,"decoder":None,"new":True})#new detected-> no assigned decoder
	#for decnum,freq in enumerate(self.last_station_indices):
	  #comparelist.append({"freq":freq,"decoder":decnum,"new":False})
	##comparelist.sort()
	#comparelist_sorted=sorted(comparelist, key=lambda k: k['freq']) 
	#print(comparelist_sorted)
	
	#differences=[]
	#station_indices_tune=[0]*4#TODO what if < 4 max freqs?
	#last_elem=None
	#same_station_threshold=2
	#new_freqs=[]
	##for elem in comparelist_sorted:
	#while len(comparelist_sorted)>0:
	  #elem=comparelist_sorted.pop(0)#get and remove first
	  #freq=elem["freq"]
	  #if not last_elem==None and not elem["freq"]==0:
	    #fdiff=abs(freq-last_elem["freq"])
	    #differences.append(fdiff)
	    #if fdiff<same_station_threshold:#freq approx same-> use old decoder
	      #if elem["new"]:#if elem is new last_elem must be old
		#decnum=last_elem["decoder"]     
		#freq=elem["freq"]#use new freq
	      #else:
		#decnum=elem["decoder"]
		#freq=last_elem["freq"]#use new freq
	      #station_indices_tune[decnum]=freq
	    #else:#stations different -> save last_elem and compare with next
	      #if last_elem["new"]:#save new 
		#new_freqs.append(last_elem["freq"])
	  #last_elem=elem
	#if last_elem["new"]:#save new 
	  #new_freqs.append(last_elem["freq"]) 
	#station_indices_tune=list(set(station_indices_tune))#remove duplicates
	#for i,freq in enumerate(station_indices_tune):
	  #if freq==0 and len(new_freqs)>0:#decoder unused
	    #station_indices_tune[i]=new_freqs.pop()#assign new freq
	      
	#print("diff %s"%differences)
	
	#print("tune:%s"%station_indices_tune)
	#print("nomatch:%s"%new_freqs)
	###############################
	#problems:
	#very slow, sometimes switches
	
	
	###############################
        #station_indices_tune.sort()
        ###############################
        #problems: swtiching
        station_indices_tune=[0]*self.num_decoders
        same_station_threshold=3
        new_stations=[]
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

        return len(input_items[0])

