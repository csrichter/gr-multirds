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
import pmt,functools,csv,md5,collections,copy,sqlite3,atexit,time,re,sys
#old imports: folium
from datetime import datetime
from datetime import timedelta
import crfa.chart as chart

from PyQt4 import Qt, QtCore, QtGui
import pprint,code,pickle#for easier testing
pp = pprint.PrettyPrinter()
import cProfile, pstats, StringIO #for profiling
pr = cProfile.Profile()#disabled-internal-profiling

#from threading import Timer#to periodically save DB

from PyQt4.QtCore import QObject, pyqtSignal
from bitstring import BitArray 

language="de"#currently supported: de, en (both partially)

SUFFIXES = {1: 'st', 2: 'nd', 3: 'rd'}
def ordinal(num):
    # I'm checking for 10-20 because those are the digits that
    # don't follow the normal counting scheme. 
    if 10 <= num % 100 <= 20:
        suffix = 'th'
    else:
        # the second parameter is a default.
        suffix = SUFFIXES.get(num % 10, 'th')
    return str(num) + suffix
class tmc_event:
  def __init__(self,ecn,tableobj):
    self.tableobj=tableobj
    self.ecn=ecn
    self.text_raw="##Error##"
    self.name="##Error##"
    self.length_str=None
    self.speed_limit_str=None
    try:
      #Code,Text  CEN-English,Text (German),Text (German) kein Quantifier,Text (Quantifier = 1),Text (Quantifier >1),N,Q,T,D,U,C,R ,Comment
      event_array=self.tableobj.ecl_dict[ecn]
      self.text_noQ=event_array[2]
      if language=="de":
	self.text_raw=event_array[1]
	self.name=self.text_noQ
      else:
	self.text_raw=event_array[0]#CEN-english
	self.name=re.sub("\(([^()]+)\)","",self.text_raw)#removes everything between parentheses (assume no quantifier is used)
      self.text_singleQ=event_array[3]
      self.text_pluralQ=event_array[4]
      self.nature=event_array[5]#N:nature (blank): information, F:forecast, S:silent
      if event_array[0]=="message cancelled":
	self.is_cancellation = True
      else:
	self.is_cancellation = False
      self.quantifierType=event_array[6]#Q:quantifier type: (0..12) or blank (no quantifier)
      self.durationType=event_array[7]#T:duration type: D:dynamic, L:long lasting, in brackets or if time-of-day quantifier (no 7) is used in message -> no display, only for management
      directionality=event_array[8]#D:directionality: 1:unidirectional, 2:bidirectional, cancellation messages dont have directionality
      self.is_unidirectional=True if directionality=="1" else False
      self.is_bidirectional=True if directionality=="2" else False
      self.urgency=event_array[9]#U:urgency: blank: normal, X:extremely urgent, U:urgent
      self.updateClass=int(event_array[10])#C: update class:
      self.updateClassName=self.tableobj.tmc_update_class_names[self.updateClass]
      self.phrase_code=event_array[11]#R: phrase code
      #04789
      #if not self.quantifierType=="" and not self.quantifierType=="0" and not self.quantifierType=="4":
	#print("type: %s, C:%s"%(self.quantifierType,self.updateClassName))
      self.is_valid=True
    except KeyError:
      print("event '%i' not found"%ecn)
      self.is_valid=False
  def change_directionality(self):
    self.is_unidirectional=not self.is_unidirectional
    self.is_bidirectional=not self.is_bidirectional
  def add_length(self,data):#from label2
    self.length_str="%i km"%mgm_tag.length_to_km(data.uint)
    #self.name=self.name.replace("(L)",self.length_str)
  def add_speed_limit(self,data):#from label3
    self.speed_limit_str="%i km/h"%(data.uint*5)
  def add_quantifier(self,data,bitLength):#from label 4
    self.name=self.text_raw#default
    Q_raw=data.uint
    if Q_raw==0:#binary zero represents highest value
      Q=32
    else:
      Q=Q_raw
    quantifier_string="type:%s,raw:%i"%(self.quantifierType,Q)
    #print(str(self.ecn)+", "+quantifier_string+", "+str(bitLength)+", "+str(data)+", "+self.text_raw)
    if self.quantifierType=="":
      print("cannot add quantifier %i to event ecn:%i"%(Q_raw,self.ecn))
    elif self.quantifierType=="0":#small numbers
      if(Q <= 28):
	quantifier_string=str(Q)
      else:
	quantifier_string=str(30+(Q-29)*2)#30,32,34,36
      #print(quantifier_string)
      self.name=self.text_pluralQ.replace("(Q)",quantifier_string)
    elif self.quantifierType=="1":#numbers
      numbers=[1,2,3,4,10,20,30,40,50,60,70,80,90,100,150,200,250,300,350,400,450,500,550,600,650,700,750,800,850,900,950,1000]
      quantifier_string=str(numbers[Q-1])
    elif self.quantifierType=="2":#z.b. für sichtweiten, e.g. for visibility 
      quantifier_string="%i m"%(Q*10)#TODO meter oder metern?
      self.name=self.text_pluralQ.replace("(Q)",quantifier_string)
      #quantifier_string="%i Metern"%Q*10
      #self.name=self.text_pluralQ.replace("Q)",quantifier_string+")")
    elif self.quantifierType=="4":
      speed=Q*5#in kmh
      #quantifier_string="von bis zu %i km/h"%speed
      quantifier_string="%i km/h"%speed
    elif self.quantifierType=="7":
      hours=int((Q-1)/6)
      minutes=((Q-1)%6)*10
      quantifier_string="%i:%i"%(hours,minutes)
      #print(quantifier_string)
    elif self.quantifierType=="8":      
      if Q<=100:
	weight=Q*0.1
      else:
	weight=10+0.5*(Q-100)
      quantifier_string="%it"%weight
      self.name=self.text_pluralQ.replace("(Q)",quantifier_string)
    elif self.quantifierType=="9":
      if Q<=100:
	length=Q*0.1
      else:
	length=10+0.5*(Q-100)
      quantifier_string="%.1fm"%length
      self.name=self.text_pluralQ.replace("(Q)",quantifier_string)
    else:#other quantifier
      self.name=self.text_raw+"; Q(%s)=%s"%(self.quantifierType,quantifier_string)
  def __str__(self):
    if self.is_valid:
      retstr=self.name
      if not self.length_str == None:
	retstr=self.name.replace("(L)",self.length_str)
      if not self.speed_limit_str == None:
	if language=="de":
	  retstr+=" (geschw. begrenzt: %s)"%self.speed_limit_str
	else:
	  retstr+=" (speed limit: %s)"%self.speed_limit_str
      return retstr
    else:
      return("invalid event, ecn:%i"%self.ecn)
  def __repr__(self):
    return "ecn:%i"%self.ecn
class tmc_location:
  #def get_extent_location(self,extent,direction):
    #__recursion_get_extent_location(self,extent,direction)
  #def __recursion_get_extent_location(self,loc,extent,direction): #direction: 0:pos, 1:neg
  def get_extent_location(self,loc,extent,direction): #direction: 0:pos, 1:neg
    #print(loc.lcn)
    #print(extent)
    #print(direction)
    if extent==0 or not loc.is_valid:
      return loc
    else:
      offset=loc.positive_offset if direction==0 else loc.negative_offset
      if offset=="":
	return loc
      else:
	offset_loc=tmc_location(int(offset),self.tableobj)
	#return __recursion_get_extent_location(offset_loc,extent-1,direction)
	return offset_loc.get_extent_location(offset_loc,extent-1,direction)
  def __ref_locs(self,lcn,name_string=""):
    #if not self.is_valid: #not used, since not called from outside
    #  return ""
    if(lcn==34196):#europe
      return(name_string)
    else:
      try:
	locarray=self.tableobj.lcl_dict[lcn]
	aref=int(locarray[6])
	loc_name=locarray[4]
	return(self.__ref_locs(aref,name_string+","+loc_name))
	#return(loc_name)
      except KeyError:
	return(name_string)
  def __str__(self):
    if not self.is_valid:
      return "invalid lcn:%i"%(self.lcn)
    elif self.ltype=="P1" and self.subtype==1:#autobahnkreuz TODO:only add if name does not already contain "Kreuz"
      name="Kreuz "+self.first_name
    elif self.ltype=="P1" and self.subtype==2:#autobahndreieck TODO:only add if name does not already contain "Dreieck"
      name="Dreieck "+self.first_name
    elif not self.roadname=="":
      name="STR:"+self.roadname#TODO remove debug
    elif not self.first_name=="":
      name=self.first_name
    else:
      name="NO NAME lcn:%i"%(self.lcn)
    return "%s,%i:%s"%(self.ltype,self.subtype,name)#no geo 
  def __repr__(self):
    if not self.is_valid:
      return "invalid lcn:%i"%(self.lcn)
    #elif self.ltype[0:2] == "P1":  #junction
    elif self.first_name=="":#no first name-> use aref name
      name=self.aref
    else:
      name=self.roadname+","+self.first_name
    if self.has_koord:
      return "%s,%i:%s, geo:%s"%(self.ltype,self.subtype,name,self.koord_str)
      #return '%s,%i:%s, geo:<a href="%s">%s</a>'%(self.ltype,self.subtype,name,self.google_maps_link,self.koord_str)
    else:
      return "%s,%i:%s"%(self.ltype,self.subtype,name)
    #if self.ltype[0]=="A":#area
      #return "%s:%s"%(self.ltype,self.first_name)
    #elif self.ltype[0]=="L":#line
      #return "%s:%s"%(self.ltype,self.first_name)
    #elif self.ltype[0]=="P":#point
      #return "%s:%s"%(self.ltype,self.first_name)
  def __init__(self,lcn,tableobj):
    self.tableobj=tableobj
    self.reflocs=self.__ref_locs(lcn)
    self.lcn=lcn
    self.has_koord=False
    self.linRef=None
    self.is_valid=False
    try:
      loc_array=tableobj.lcl_dict[lcn]
      self.ltype=loc_array[0]
      try:
	self.subtype=int(loc_array[1])
      except ValueError:#should not happen, all rows have int
	self.subtype=0
	print("location subtype %s is invalid in location %i"%(loc_array[1],lcn))
      self.roadnumber=loc_array[2]
      self.roadname=loc_array[3]
      self.first_name=loc_array[4]
      self.second_name=loc_array[5]
      if not loc_array[7]=="":
	self.linRef=tmc_location(int(loc_array[7]),tableobj)
      self.negative_offset=loc_array[8]
      self.positive_offset=loc_array[9]
      try:
	#koords stored in WGS84 format with decimal degrees multiplied with 10^5
	self.xkoord=int(loc_array[27])/100000.0
	self.ykoord=int(loc_array[28])/100000.0
	self.koord_str="%f,%f"%(self.ykoord,self.xkoord)
	self.koord_str_google="{lat: %f, lng:  %f}"%(self.ykoord,self.xkoord)
	self.google_maps_link="https://www.google.de/maps/place/%f,%f"%(self.ykoord,self.xkoord)
	self.has_koord=True
      except ValueError:
	self.has_koord=False
      self.is_valid=True
      if not lcn==34196:#Europe does not have an area reference
	self.aref=tmc_location(int(loc_array[6]),tableobj)
    except KeyError:
      #print("location '%i' not found"%lcn)
      self.is_valid=False
    ##LOCATIONCODE;TYPE;SUBTYPE;ROADNUMBER;ROADNAME;FIRST_NAME;SECOND_NAME;AREA_REFERENCE;LINEAR_REFERENCE;NEGATIVE_OFFSET;POSITIVE_OFFSET;URBAN;INTERSECTIONCODE;INTERRUPTS_ROAD;IN_POSITIVE;OUT_POSITIVE;IN_NEGATIVE;OUT_NEGATIVE;PRESENT_POSITIVE;PRESENT_NEGATIVE;EXIT_NUMBER;DIVERSION_POSITIVE;DIVERSION_NEGATIVE;VERÄNDERT;TERN;NETZKNOTEN_NR;NETZKNOTEN2_NR;STATION;X_KOORD;Y_KOORD;POLDIR;ADMIN_County;ACTUALITY;ACTIVATED;TESTED;SPECIAL1;SPECIAL2;SPECIAL3;SPECIAL4;SPECIAL5;SPECIAL6;SPECIAL7;SPECIAL8;SPECIAL9;SPECIAL10

class tmc_dict:
  "dict of tmc messages sorted by location (LCN) and update class, automatically deletes/updates invalid(ated) items"
  marker_template="addMarker({loc},'{text}',{endloc})"
  def __init__(self):
    self.messages={}
    self.message_list=[]
  def add(self,message):
    self.message_list.append(message)
    try:
      lcn=message.location.lcn
      updateClass=message.event.updateClass
      if not self.messages.has_key(lcn):
	self.messages[lcn]={}
      if message.event.is_cancellation:
	try:
	  self.messages[lcn][updateClass].cancellation_time=message.getTime()#cancellation_time = rx time of cancellation message
	except KeyError:#no message to cancel
	  message.event.name="no message to cancel"
	  self.messages[lcn][updateClass]=message
      else:
	self.messages[lcn][updateClass]=message
      #print("added message: "+str(message))
    except AttributeError:
      print("ERROR, not adding: "+str(message))
  def matchFilter(self,msg,filters):
    if not msg.location.is_valid:
      return True#always show invalid messages
    loc_str=str(msg.location)+str(msg.location.reflocs)+str(msg.location.roadnumber)
    
    
    for f in filters:#filters is list of dicts {"type":"event","str":"Stau"}
      stringlist=f["str"].lower().split(";")
      for string in stringlist:
	if f["type"]=="event" and unicode(str(msg.event), encoding="UTF-8").lower().find(string)==-1:#if event filter does not match
	  return False
	elif f["type"]=="location" and unicode(loc_str, encoding="UTF-8").lower().find(string)==-1:#if location filter does not match
	  return False
    return True
  def getLogString(self,filters):
    retStr=""
    for message in self.message_list:
      if self.matchFilter(message,filters):
	retStr+=message.log_string()
	retStr+="\n"
	retStr+=message.multi_str()
	retStr+="\n"
    return retStr
  def getMarkerString(self):
    markerstring=""
    for lcn in self.messages:
      loc=None
      endloc=None
      map_tag='<p>'
      for updateClass in self.messages[lcn]:
	message=self.messages[lcn][updateClass]
	if message.cancellation_time==None:
	  color="black"
	else:
	  color="gray"
	if message.location.has_koord:
	  if loc==None:#first message at this location
	    map_tag+='<h3 style="padding: 0px;margin: 0px;">'
	    map_tag+=message.location_text()
	    map_tag+='</h3>'
	    if message.cancellation_time==None:
	      endloc=message.end_loc()#line displays length of 1st message (lowest class), that is not cancelled
	  loc=message.location
	  map_tag+='<div style="color: %s;">'%color
	  map_tag+=message.map_string()
	  map_tag+='<br />'
	  map_tag+='</div>'
      map_tag+='</p>'
      if not loc==None:
	if endloc==None or not endloc.is_valid:
	  endloc=loc#creates line of 0 length (dot)
	markerstring+=tmc_dict.marker_template.format(loc=loc.koord_str_google,text=map_tag,endloc=endloc.koord_str_google)
	markerstring+="\n"
    return markerstring
  
  
class tmc_message:
  #Nature                Information or Silent                                Forecast
#Duration Type         Dynamic        Longer lasting           Dynamic             Longer lasting
        #0           (none)           (none)                   (none)              (none)
        #1           for at least     for at least next        within the          within the next few
                    #next 15 min      few hours                next 15 min         hours
        #2           for at least     for the rest of the      within the          later today
                    #next 30 min      day                      next 30 min
        #3           for at least     until tomorrow           within the          tomorrow
                    #next 1 h         evening                  next 1 h
        #4           for at least     for the rest of the      within the          the day after tomorrow
                    #next 2 h         week                     next 2 h
        #5           for at least     until the end of         within the          this weekend
                    #next 3 h         next week                next 3 h
        #6           for at least     until the end of         within the          later this week
                    #next 4 h         the month                next 4 h
        #7           for the rest of  for a long period        within the of       next week
                    #the day                                   the day
  duration_dict={"Info_dyn":["","for at least next 15 min","for at least next 30 min","for at least next 1 h","for at least next 2 h","for at least next 3 h","for at least next 4 h","for the rest of the day"],
		  "Info_long":["","for at least next few hours","for the rest of the day","until tomorrow evening","for the rest of the week","until the end of next week","until the end of the month","for a long period"],
		  "Forecast_dyn":["","within the next 15 min","within the next 30 min","within the next 1 h","within the next 2 h","within the next 3 h","within the next 4 h","within the day"],
		  "Forecast_long":["","within the next few hours","later today","tomorrow","the day after tomorrow","this weekend","later this week","next week"]}
       #Nature             Information or Silent                                   Forecast
#Duration Type    Dynamic           Longer lasting      Dynamic                 Longer lasting
#0                15 min            1h                  15 min                  1h
#1                15 min            2h                  15 min                  2h
#2                30 min            until midnight      30 min                  until midnight
#3                1h                until midnight      1h                      until midnight next day
#                                   next day
#4                2h                until midnight      2h                      until midnight next day
#                                   next day
#5                3h                until midnight      3h                      until midnight next day
#                                   next day
#6                4h                until midnight      4h                      until midnight next day
#                                   next day
#7                until midnight    until midnight      until midnight          until midnight next day
#                                   next day
  persistence_dict={"dyn":[0.25,0.25,0.5,1,2,3,4,"m"],
		  "long":[1,2,"m","nm","nm","nm","nm","nm"]}
		  #m=midnight, nm=midnight nex day, same for forecast and info/silent
       #datetime.timedelta(hours=0.25)
  def getDuration(self):#returns string
    if "D" in self.event.durationType and not self.event.nature=="F":
      return ", "+tmc_message.duration_dict["Info_dyn"][self.tmc_DP]
    elif "L" in self.event.durationType and not self.event.nature=="F":
      return ", "+tmc_message.duration_dict["Info_long"][self.tmc_DP]
    elif "D" in self.event.durationType and self.event.nature=="F":
      return ", "+tmc_message.duration_dict["Forecast_dyn"][self.tmc_DP]
    elif "L" in self.event.durationType and self.event.nature=="F":
      return ", "+tmc_message.duration_dict["Forecast_long"][self.tmc_DP]
    else:
      return ""
    #self.event.durationType #D,(D),L,(L)
    #self.event.nature# "",S,F
  def getPersistance(self):#returns timedelta
    persistence_dict=tmc_message.persistence_dict
    try:
      if "D" in self.event.durationType:
	return timedelta(hours=persistence_dict["dyn"][self.tmc_DP])
      if "L" in self.event.durationType:
	return timedelta(hours=persistence_dict["long"][self.tmc_DP])
    except TypeError:
      print("ERROR: TODO line 354")
  def __copy__(self):#doesn't copy, tmc_messages dont change if complete
    return self
  def __deepcopy__(self,memo):#return self, because deep copy fails
    return self
  def __hash__(self):#unused
    if self.is_single:
      return self.tmc_hash
    else:
      return self.ci
  def multi_str(self):
    if self.is_single:
      multi="[single]"
    else:
      try:
	multi="%i:%s"%(self.length,str(self.mgm_list))
      except AttributeError:
	multi="[multi incomplete]"
    return str(multi)
  def info_str(self):
    info=""
    info+=self.getDuration()
    if not self.cancellation_time==None:
      if language=="de":
        info+=" (aufgehoben um %s)"%self.cancellation_time
      else:
        info+=" (cancelled at %s)"%self.cancellation_time
    return info
  def events_string(self):
    str_list=[str(elem) for elem in self.events]
    return str(", ".join(str_list))
  def log_string(self):
    return str(self.event.updateClass)+": "+self.getTime()+": "+self.location_text()+": "+self.events_string()+"; "+self.info_str()+"; "+self.psn
  def db_string(self):
    return str(self.location)+": "+str(self.event.updateClass)+": "+self.events_string()+"; "+self.info_str()
  def map_string(self):
    return '<span title="%s">'%self.multi_str()+str(self.event.updateClass)+": "+self.getTime()+": "+self.events_string()+self.info_str()+"; "+self.psn+"</span>"
  def end_loc(self):
    return self.location.get_extent_location(self.location,self.tmc_extent,self.tmc_dir)
  def location_text(self):
    text=str(self.location)#use __str__ of location if no location_text implemented
    #TODO add "dreieck" for P1.2 -> done in tmc_message.__str__
    if not self.location.linRef==None:#test
      #self.tmc_extent and self.tmc_dir are ints
      #offset_loc=self.location.get_extent_location(self.location,self.tmc_extent,self.tmc_dir)
      offset_loc=self.end_loc()
      if offset_loc.is_valid:
	#offset_loc_name=str(offset_loc)
	offset_loc_name=offset_loc.first_name
      else:
	print(offset_loc)
	offset_loc_name="###INVALID###"
      templates={"de_1":"{A}, {B} in Richtung {C}"#codeing handbook: zwischen {D} und {E}, sprachdurchsagen: zwischen {E} und {D}
		    ,"de_2a":", zwischen {D} und {E}"
		    ,"de_2b":", bei {D}"#extent==0
		    ,"en_1":"{A}, {B} {C}"
		    ,"en_2a":", between {D} and {E}"
		    ,"en_2b":", at {D}"}#extent==0
      text=templates[language+"_1"].format(A=self.location.linRef.roadnumber, B=self.location.linRef.second_name,C=self.location.linRef.first_name)
      if self.location.first_name==offset_loc_name:#similar to self.tmc_extent==0 (but some similar location have same same name)
	text+=templates[language+"_2b"].format(D=self.location.first_name)
      else:
	text+=templates[language+"_2a"].format(D=self.location.first_name,E=offset_loc_name)
 
      #LocCode: RefLine: RoadNr
      #A
      #LocCode:RefLine:Name2
      #B
      #LocCode:RefLine:Name1
      #C
      #LocCode:Name1
      #D
      #LocCode:Extent:OffsNeg:Name1
      #E
      #EventCode: EventText
      #F   
    return str(text)
  def __str__(self):
    return str(self.event.updateClass)+": "+self.getTime()+": "+self.events_string()+"; "+self.multi_str()
  def __repr__(self):
    #event_name=self.ecl_dict[self.tmc_event][1]
    #message_string="TMC-message,event:%s location:%i,reflocs:%s, station:%s"%(event_name,self.tmc_location,self.ref_locs(self.tmc_location,""),self.RDS_data[PI]["PSN"])
    return "single:%i,complete:%i,event:%i location:%s"%(self.is_single,self.is_complete,self.event.ecn,self.location)
  def getTime(self):#always returns string
    if self.hastime:
      return self.datetime_received.strftime("%H:%M")
    else:
      return "88:88"
  def __init__(self,PI,tmc_x,tmc_y,tmc_z,datetime_received,tableobj):#TODO handle out of sequence data
    self.psn=tableobj.RDS_data[PI]["PSN"]
    #check LTN
    try:
      msg_ltn=tableobj.RDS_data[PI]["AID_list"][52550]["LTN"]
      table_ltn=1#german table
      if msg_ltn != table_ltn  and tableobj.debug and False:#disabled, spams log
	print("msg_ltn:%i does not match expected table (1) on station: %s"%(msg_ltn,self.psn))
    except KeyError:
      if tableobj.debug:
	print("no LTN found")
    #self.time_received=time_received
    self.datetime_received=datetime_received
    if self.datetime_received==None:
      self.hastime=False
    else:
      self.hastime=True
    self.debug_data=""
    self.tableobj=tableobj
    self.PI=PI
    #self.isCancelled=False
    self.cancellation_time=None
    self.tmc_hash=hash((PI,tmc_x,tmc_y,tmc_z))
    tmc_T=tmc_x>>4 #0:TMC-message 1:tuning info/service provider name
    assert tmc_T==0, "this is tuning info and no alert_c message"
    Y15=int(tmc_y>>15)
    tmc_F=int((tmc_x>>3)&0x1) #identifies the message as a Single Group (F = 1) or Multi Group (F = 0)
    self.is_single=(tmc_F==1)
    self.is_multi=(tmc_F==0)
    if self.is_single or (self.is_multi and Y15==1):#single group or 1st group of multigroup
      if self.is_single:
	self.tmc_D=Y15 #diversion bit(Y15)
	self.tmc_DP=int(tmc_x&0x7) #duration and persistence 3 bits
	self.is_complete=True
      else:#1st group of multigroup -> no diversion bit, no duration (sent in mgm_tags)
	self.is_complete=False
	self._second_group_received=False
	self.tmc_D=0
	self.tmc_DP=0#default to duration of 0, can be changed with MGM
	self.ci=int(tmc_x&0x7) #continuity index
	self.data_arr=BitArray()
	self.mgm_list=[]
      self.location=tmc_location(tmc_z,tableobj)
      self.tmc_location=self.location#decrepated
      #self.event=int(tmc_y&0x7ff) #Y10-Y0
      self.event=tmc_event(int(tmc_y&0x7ff),self.tableobj) #Y10-Y0
      self.events=[self.event]
      #try:
	#self.event_name = self.tableobj.ecl_dict[self.event][1]
      #except KeyError:
	#self.event_name="##Error##"
      self.tmc_extent=int((tmc_y>>11)&0x7) #3 bits (Y13-Y11)
      self.tmc_dir=int((tmc_y>>14)&0x1) #+-direction bit (Y14)
      if not self.event.is_valid:
	print("invalid main event")
	print(self)
    else:#subsequent groups in multigroup -> Y0..Y11 and Z0..Z15 are special format
      raise ValueError, "subsequent groups must be added to existing tmc message"
    tableobj.tmc_messages.add(self)
  def add_group(self,tmc_y,tmc_z):
    sg=int((tmc_y>>14)&0x1)#=1 if second group Y14
    gsi=int((tmc_y>>12)&0x3)#group sequence indicator Y12..13 ,max length:5
    if sg==1 and not self._second_group_received:#if second group
      self.length=gsi
      self.count=self.length
      self._second_group_received=True #prevents duplicate second group from resetting counters 
    try:
      if self.count==gsi: #group in sequence
	data1=int(tmc_y&0xfff)#data block 1
	data2=int(tmc_z)#data block 2
	
	self.data_arr.append("0x%03X"%data1)#3 hex characters
	self.data_arr.append("0x%04X"%data2)#4 hex characters
	#print(gsi)
	
	if self.count==0:#last group
	  self.is_complete=True
	  self.debug_data=copy.deepcopy(self.data_arr)
	  last_event=self.event
	  while len(self.data_arr)>4:#decode mgm
	    label=self.data_arr[0:4].uint
	    del self.data_arr[0:4]
	    fieldlen=mgm_tag.field_lengths[label]
	    data=self.data_arr[0:fieldlen]
	    del self.data_arr[0:fieldlen]
	    if not (label==0 and data.uint ==0):#ignore trailing zeros
	      self.mgm_list.append(mgm_tag(label,data,self.tableobj))
	      if label==0:#duration/persistence
		self.tmc_DP=data.uint
	    #label==1: control codes
	      elif label==1 and data.uint==2:
		last_event.change_directionality#change directionality
	      elif label==1 and data.uint==5:
		self.tmc_D=1#set diversion bit
	      elif label==1 and data.uint==6:
		self.tmc_extent+=8#increase extent
	      elif label==1 and data.uint==7:
		self.tmc_extent+=16#increase extent
				
	      elif label==2:#length
		last_event.add_length(data)
	      elif label==3:#speed
		last_event.add_speed(data)
	      elif label==4:#5 bit quantifier
		last_event.add_quantifier(data,5)
	      elif label==5:#8 bit quantifier
		last_event.add_quantifier(data,8)
	      elif label==9:#additional event
		last_event=tmc_event(data.uint,self.tableobj)
		if not last_event.is_valid:
		  print("invalid MGM event")
		self.events.append(last_event)
		
		
	self.count-=1
    except AttributeError:
      #3rd or later group receiver before second
      #print("out of sequence")
      pass

class mgm_tag:#mgm=multi group message
  field_lengths=[3, 3, 5, 5, 5, 8, 8, 8, 8, 11, 16, 16, 16, 16, 0, 0]
  field_names={0:"Duration (value 000 is not allowed)"
  ,1:"Control code."
  ,2:"Length of route affected."
  ,3:"Speed limit advice."
  ,4:"quantifier (5 bit field)"
  ,5:"quantifier (8 bit field)"
  ,6:"Supplementary information code."
  ,7:"Explicit start time (or time when problem was reported) for driver information only."
  ,8:"Explicit stop time for driver information and message management."
  ,9:"Additional event."
  ,10:"Detailed diversion instructions."
  ,11:"Destination."
  ,12:"Reserved for future use"
  ,13:"Cross linkage to source of problem  , on another route."
  ,14:"Content Separator."
  ,15:"Reserved for future use."}
  control_codes={0:"Default urgency increased by one level."
  ,1: "Default urgency reduced by one level."
  ,2:" Default directionality of message changed."
  ,3:" Default 'dynamic' or 'longer-lasting' provision interchanged."
  ,4:" Default spoken or unspoken duration interchanged."
  ,5:" Equivalent of diversion bit set to '1'."
  ,6:" Increase the number of steps in the problem extent by 8."
  ,7:" Increase the number of steps in the problem extent by 16."}
  control_codes_short={0:"urgency+=1"
  ,1:" urgency-=1"
  ,2:" directionality changed"
  ,3:" dynamic/longer-lasting changed"
  ,4:" spoken/unspoken duration changed"
  ,5:" diversion=1"
  ,6:" extent+=8"
  ,7:" extent+=16"}
  @staticmethod
  def decode_time_date(raw):#label7/8 raw to datestring
    if raw<=95:
      hrs=int(raw/4)#takes floor
      mns=(95%4)*15
      return "%i:%i"%(hrs,mns)
    elif raw<=200:#hour and day
      return "%i hours"%(raw-96)
    elif raw<=231:#day of month
      return "%s of month"%ordinal(raw-200)
    elif raw<=255:#months
      return "%s months"%((raw-231)/2.0)
    else:
      raise ValueError, "label7/8 time must be between 0 and 255"
  @staticmethod
  def length_to_km(raw):#label2 raw to km
    if raw==0:
      return 100
    elif raw <=10:
      return raw
    elif raw <=15:
      return 2*raw-10
    elif raw <=31:
      return 5*raw-55
    else:
      raise ValueError, "label2-length must be between 0 and 31"
	
  def __repr__(self):
    try:
      if(self.label==0):
        return "duration: %i"%self.data.uint
      elif(self.label==1):
        return "control code %i: %s"%(self.data.uint,mgm_tag.control_codes_short[self.data.uint])
      elif(self.label==2):
        return "length affected: %i km"%self.length_to_km(self.data.uint)
      elif(self.label==3):
        return "speed limit: %i km/h"%(self.data.uint*5)
      elif(self.label==4):
        return "5 bit quantifier: %i"%(self.data.uint)
      elif(self.label==5):
        return "8 bit quantifier: %i"%(self.data.uint)
      elif(self.label==6):
        return "info:%s"%self.tableobj.label6_suppl_info[self.data.uint]
      elif(self.label==7):
        return "start: %s"%self.decode_time_date(self.data.uint)
      elif(self.label==8):
        return "stop: %s"%self.decode_time_date(self.data.uint)
      elif(self.label==9):
	event=tmc_event(self.data.uint,self.tableobj)
	#event_string="event: %s"%self.tableobj.ecl_dict[self.data.uint][1]
	#return event_string
	return "event: %s"%event.name
      elif(self.label==10):
	#location_string="divert via: %s"%",".join(self.tableobj.lcl_dict[self.data.uint][3:5])#roadname(col3) and firstname (col4)
	location_string="divert via: %s"%tmc_location(self.data.uint,self.tableobj)
	return location_string
      elif(self.label==11):
	location_string="dest.: %s"%tmc_location(self.data.uint,self.tableobj)
	return location_string
      elif(self.label==13):
	location_string="crosslink: %s"%tmc_location(self.data.uint,self.tableobj)
	return location_string
      else:
        return "%i:%s"%(self.label,str(self.data))
    except KeyError:
	return "%i:%s"%(self.label,str(self.data))
      
  def __init__(self,label,data,tableobj):
    self.tableobj=tableobj
    assert 0<=label and label <16,"mgm-tag label has to be between 0 and 15"
    self.label = label
    self.data = data
  def label_string(self):
    return field_names[self.label]
class rds_parser_table_qt_Signals(QObject):
    DataUpdateEvent = QtCore.pyqtSignal(dict)
    def __init__(self, parent=None):
	super(QtCore.QObject, self).__init__()   
class rds_parser_table_qt(gr.sync_block):#START
    """
    docstring for block qtguitest
    """
    def goodbye(self):
      self.clean_data_and_commit_db()
      print("quitting rds parser table, closing db")
      if self.writeDB:
	#self.db.commit()
	self.db.close()
    def __init__(self,signals,nPorts,slot,freq,log,debug,workdir,writeDB):
	#QObject.__init__()
        gr.sync_block.__init__(self,
            name="RDS Table",
            in_sig=None,
            out_sig=None)
	if nPorts==1:
	  self.message_port_register_in(pmt.intern('in'))
	  self.set_msg_handler(pmt.intern('in'), functools.partial(self.handle_msg, port=0))
	else:
	  for i in range(nPorts):
	    self.message_port_register_in(pmt.intern('in%d'%i))
	    self.set_msg_handler(pmt.intern('in%d'%i), functools.partial(self.handle_msg, port=i))
	self.nPorts=nPorts
	self.message_port_register_in(pmt.intern('freq'))
	self.set_msg_handler(pmt.intern('freq'), self.set_freq)
	self.message_port_register_out(pmt.intern('ctrl'))
	self.log=log
	self.debug=debug
	self.writeDB=writeDB
	self.signals=signals
	self.RDS_data={}
	self.change_freq_tune=slot
	self.tuning_frequency=int(freq)
        self.printcounter=0
        self.ODA_application_names={}
        self.TMC_data={}
        self.IH_data={}
        self.decoder_frequencies={}
        self.decoders=[]
        for i in range(nPorts):
          self.decoders.append({'synced':False,'freq':None})
        #self.decoder_synced={}
        #self.colorder=['ID','freq','name','PTY','AF','time','text','quality','buttons']
        self.colorder=['ID','freq','name','buttons','PTY','AF','time','text','quality','RT+']
        self.workdir=workdir
        self.PI_dict={}#contains PI:numpackets (string:integer)
	self.tmc_messages=tmc_dict()
        
        if self.writeDB:
	  #create new DB file
	  db_name=workdir+'RDS_data'+datetime.now().strftime("%Y%m%d_%H%M%S")+'.db'
	  db=sqlite3.connect(db_name, check_same_thread=False)
	  self.db=db
	  #create tables
	  try:
	    db.execute('''CREATE TABLE stations
		(PI text PRIMARY KEY UNIQUE,PSN text, freq real, PTY text,TP integer)''')
	    db.execute('''CREATE TABLE groups
		(time text,PI text,PSN text, grouptype text,content blob)''')
	    db.execute('''CREATE TABLE data
		(time text,PI text,PSN text, dataType text,data blob)''')
	    db.execute('''CREATE TABLE grouptypeCounts
		(PI text,grouptype text,count integer,unique (PI, grouptype))''')
	    db.execute('''CREATE TABLE TMC
		(hash text PRIMARY KEY UNIQUE,time text,PI text, F integer,event integer,location integer,DP integer,div integer,dir integer,extent integer,text text,multi text,rawmgm text)''')
	    db.commit()
	    
	  except sqlite3.OperationalError:
	    print("ERROR: tables already exist")
	
	#self.dbc.execute('''CREATE TABLE rtp
        #     (time text,PI text,rtp_string text)''')
	reader = csv.reader(open(self.workdir+'RDS_ODA-AIDs_names_only.csv'), delimiter=',', quotechar='"')
	reader.next()#skip header
	for row in reader:
	  self.ODA_application_names[int(row[0])]=row[1]
	#read location code list:
	reader = csv.reader(open(self.workdir+'LCL15.1.D-160122_utf8.csv'), delimiter=';', quotechar='"')
	reader.next()#skip header
	self.lcl_dict=dict((int(rows[0]),rows[1:]) for rows in reader)
	#read RT+ class name list:
	reader = csv.reader(open(self.workdir+'RTplus_classnames.csv'), delimiter=',', quotechar='"')
	reader.next()#skip header
	self.rtp_classnames=dict((int(rows[0]),rows[1]) for rows in reader)
	#read TMC-event list
	reader = csv.reader(open(self.workdir+'event-list_with_forecast_sort.csv'), delimiter=',', quotechar='"')
	reader.next()#skip header
	self.ecl_dict=dict((int(rows[0]),rows[1:]) for rows in reader)
	#Code,Text  CEN-English,Text (German),Text (German) kein Quantifier,Text (Quantifier = 1),Text (Quantifier >1),N,Q,T,D,U,C,R ,Comment
	#N:nature (blank): information, F:forecast, S:silent
	#Q:quantifier type: (0..12) or blank (no quantifier)
	#T:duration type: D:dynamic, L:long lasting, in brackets or if time-of-day quantifier (no 7) is used in message -> no display, only for management
	#D:direction: 1:unidirectional, 2:bidirectional
	#U:urgency: blank: normal, X:extremely urgent, U:urgent
	#C: update class:
	
	#read update classes
	reader = csv.reader(open(self.workdir+'tmc_update_class_names.csv'), delimiter=',', quotechar='"')
	reader.next()#skip header, "code(C),english,german"
	if language=="de":
	  self.tmc_update_class_names=dict((int(rows[0]),rows[2]) for rows in reader)#german names
	else:
	  self.tmc_update_class_names=dict((int(rows[0]),rows[1]) for rows in reader)#english names
	#read supplementary information code list
	reader = csv.reader(open(self.workdir+'label6-supplementary-information-codes.csv'), delimiter=',', quotechar='"')
	reader.next()#skip header, "code,english,german"
	if language=="de":
	  self.label6_suppl_info=dict((int(rows[0]),rows[2]) for rows in reader)#german
	else:
	  self.label6_suppl_info=dict((int(rows[0]),rows[1]) for rows in reader)#english
	#read PTY list
	f=open(self.workdir+'pty-list.csv')
	reader = csv.reader(f, delimiter=',', quotechar='"')
	reader.next()#skip header
	self.pty_dict=dict((int(rows[0]),rows[1]) for rows in reader)
	f.close()
	self.minute_count=0
	self.minute_count_max=0
	self.minute_count_timer=time.time()
	self.save_data_timer=time.time()
	
	atexit.register(self.goodbye)
	
    def clean_data_and_commit_db(self):
	for PI in self.PI_dict:
	  self.PI_dict[PI]-=1
	#print(self.PI_dict)
	if self.writeDB:
	  self.db.commit()
	f=open(self.workdir+'google_maps_markers.js', 'w')
	markerstring=self.tmc_messages.getMarkerString()
	markerstring+='\n console.log("loaded "+markers.length+" markers")'
	markerstring+='\n document.getElementById("errorid").innerHTML = "loaded "+markers.length+" markers";'
	f.write(markerstring)
	f.close()
    def update_freq(self):
        #  "&#9;" is a tab character
	message_string="decoder frequencies:"
	for num in self.decoder_frequencies:
	  freq=self.decoder_frequencies[num]
	  if self.decoders[num]['synced']:
            message_string+="<span style='color:green'>&emsp; %i:%0.1fM</span>"% (num,freq/1e6)
            #print("'color:green'>%i:%0.1fM</span>"% (num,freq/1e6))
	  else:#elif self.decoders[num]['synced']==False:
            #print("'color:red'>%i:%0.1fM</span>"% (num,freq/1e6))
            message_string+="<span style='color:red'>&emsp; %i:%0.1fM</span>"% (num,freq/1e6)
	message_string+="&emsp; tuned frequency:%0.1fM"%(self.tuning_frequency/1e6)
	self.signals.DataUpdateEvent.emit({'decoder_frequencies':message_string})
	#print(message_string)
	#self.signals.DataUpdateEvent.emit({'row':decoder_num,'freq':freq_str})
	#print("nr:%i freq:%s"%(tgtnum,freq_str))
    def set_freq_tune(self,freq):
      self.tuning_frequency=int(freq)
      self.update_freq()
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
	self.update_freq()
    def init_data_for_PI(self,PI):
	  self.RDS_data[PI]={}
	  #self.RDS_data[PI]["blockcounts"]={}# no defaults (works aswell)
	  #defaults are to keep colors in piechart  consistent between stations:
	  self.RDS_data[PI]["blockcounts"]={"0A":0,"1A":0,"2A":0,"3A":0,"4A":0,"6A":0,"8A":0,"12A":0,"14A":0}
	  self.RDS_data[PI]["blockcounts"]["any"]=0
	  self.RDS_data[PI]["AID_list"]={}
	  self.RDS_data[PI]["PSN"]="_"*8
	  self.RDS_data[PI]["PSN_valid"]=[False]*8
	  self.RDS_data[PI]["AF"]={"set":set(),"rxset":set()}
	  self.RDS_data[PI]["TP"]=-1
	  self.RDS_data[PI]["TA"]=-1
	  self.RDS_data[PI]["PTY"]=""
	  self.RDS_data[PI]["DI"]=[2,2,2,2]
	  self.RDS_data[PI]["internals"]={"last_rt_tooltip":"","unfinished_TMC":{},"last_valid_rt":"","last_valid_psn":"","RT_history":[]}
	  self.RDS_data[PI]["time"]={"timestring":"88:88","datestring":"00-00-0000","datetime":None}
    def handle_msg(self, msg, port):#port from 0 to 3
      if pmt.to_long(pmt.car(msg))==1L:
	data=pmt.to_python(pmt.cdr(msg))
	#print("port:%i, data: %s"%(port,data))
	self.decoders[port]['synced']=data
	self.update_freq()
      else: #elif pmt.to_long(pmt.car(msg))==0L
	array=pmt.to_python(msg)[1]
	
	if time.time()-self.save_data_timer > 10:#every 10 seconds
	  self.save_data_timer=time.time()
	  self.clean_data_and_commit_db()
	  
	if time.time()-self.minute_count_timer > 3:#every 3 second
	  self.minute_count_max=self.minute_count
	  self.signals.DataUpdateEvent.emit({'group_count':self.minute_count,'group_count_max':self.minute_count_max})
	  self.minute_count=0
	  self.minute_count_timer=time.time()
	#pr.enable()#disabled-internal-profiling
	self.minute_count+=1
	#self.signals.DataUpdateEvent.emit({'group_count':self.minute_count,'group_count_max':self.minute_count_max})
	if self.writeDB:
	  #db=sqlite3.connect(self.db_name)
	  db=self.db
	
	
	groupNR=array[2]&0b11110000
	groupVar=array[2]&0b00001000
	if (groupVar == 0):
		groupType=str(groupNR >> 4)+"A"
	else:
		groupType=str(groupNR >> 4)+"B"
	#if self.debug:
	  #PI=str(port)+"_%02X%02X" %(array[0],array[1])
	#else:
	  #PI="%02X%02X" %(array[0],array[1])
	PI="%02X%02X" %(array[0],array[1])
	TP=(array[2]>>2)&0x1
	block2=(array[2]<<8)|(array[3]) #block2
	PTY=(block2>>5)&0x1F
	wrong_blocks=int(array[12])
	
	try:
	  self.PI_dict[PI]+=1
	except KeyError:
	  pass
	
	if not self.RDS_data.has_key(PI):#station invalid/new
	  if not self.PI_dict.has_key(PI):#1st group
	    self.PI_dict[PI]=1
	    return#dont decode further if not yet valid
	  elif self.PI_dict[PI]>2:#count station as valid if more than 2 packets received
	    self.init_data_for_PI(PI)#initialize dict for station
	    if self.log:
	      print("found station %s"%PI)
	  else:
	    return#dont decode further if not yet valid

	if self.decoder_frequencies.has_key(port):
	  freq=self.decoder_frequencies[port]
	  freq_str="%i:%0.1fM"% (port,freq/1e6)
	  self.RDS_data[PI]["tuned_freq"]=freq
	  #self.signals.DataUpdateEvent.emit({'PI':PI,'freq':freq_str})
	if self.RDS_data[PI]["blockcounts"].has_key(groupType):
	  self.RDS_data[PI]["blockcounts"][groupType] +=1 #increment
	else:
	  self.RDS_data[PI]["blockcounts"][groupType] = 1 #initialize (1st group of this type)
	self.RDS_data[PI]["blockcounts"]["any"]+=1
	if self.RDS_data[PI]["blockcounts"]["any"]==5:
	  self.RDS_data[PI]["blockcounts"]["any"]=0
	  t=(str(PI),groupType,self.RDS_data[PI]["blockcounts"][groupType])#TODO only update DB every few seconds
	  if self.writeDB:
	    db.execute("INSERT OR REPLACE INTO grouptypeCounts (PI,grouptype,count) VALUES (?,?,?)",t)
	dots="."*self.RDS_data[PI]["blockcounts"]["any"]
	self.RDS_data[PI]["TP"]=TP
	self.RDS_data[PI]["PTY"]=self.pty_dict[PTY]
	
	self.signals.DataUpdateEvent.emit({'row':port,'PI':PI,'PTY':self.pty_dict[PTY],'TP':TP,'wrong_blocks':wrong_blocks,'dots':dots})

	
	
	#add any received groups to DB (slow)
	#content="%02X%02X%02X%02X%02X" %(array[3]&0x1f,array[4],array[5],array[6],array[7])
	#t=(str(datetime.now()),PI,self.RDS_data[PI]["PSN"],groupType,content)
	#db.execute("INSERT INTO groups  VALUES (?,?,?,?,?)",t)
	
	if (groupType == "0A"):#AF PSN
	  adr=array[3]&0b00000011
	  segment=self.decode_chars(chr(array[6])+chr(array[7]))
	  d=(array[3]>>2)&0x1
	  self.RDS_data[PI]["DI"][3-adr]=d#decoder information
	  #DI[0]=d0	0=Mono 			1=Stereo
	  #d1 		Not artificial head 	Artificial head
	  #d2		Not compressed		Compressed
	  #d3		Static PTY		Dynamic PTY
	  TA=(array[3]>>4)&0x1
	  MS=(array[3]>>3)&0x1
	  self.RDS_data[PI]["TA"]=TA
	  #style='font-family:Courier New;color:%s'
	  flag_string="<span style=''>TP:%i, TA:%i, MS:%i, DI:%s</span>"%(TP,TA,MS,str(self.RDS_data[PI]["DI"]))
	  pty_colored=self.RDS_data[PI]["PTY"]
	  if TP==1:
	    if TA==1:
	      color="red"
	    elif TA==0:
	      color="green"
	    else:
	      color="yellow"
	    pty_colored="<span style='color:%s'>%s</span>"%(color,self.RDS_data[PI]["PTY"])
	  
	  self.signals.DataUpdateEvent.emit({'row':port,'PI':PI,'flags':flag_string,'PTY':pty_colored})
	  
	  #224 1110 0000 = no AF
	  #225 1110 0001 = 1AF
	  #249 1111 1001 = 25AF
	  fillercode=205#1100 1101
	  if not self.RDS_data[PI]["AF"].has_key("main") and self.RDS_data[PI].has_key("tuned_freq"):
	  #if self.RDS_data[PI].has_key("tuned_freq"):#update main freq even if one exists -> DB problem
	    freq=self.decode_AF_freq(array[4])
	    if freq==self.RDS_data[PI]["tuned_freq"]:
	      self.RDS_data[PI]["AF"]["main"]=freq
	      if self.log:
		print("main frequency found in 0A: station:%s, freq:%0.1fM"% (self.RDS_data[PI]["PSN"],freq/1e6))
	      freq_str="0A:%0.1fM"% (freq/1e6)
	      self.signals.DataUpdateEvent.emit({'PI':PI,'freq':freq_str})
	      t=(PI,self.RDS_data[PI]["PSN"],float(freq),self.RDS_data[PI]["PTY"],int(self.RDS_data[PI]["TP"]))
	      if self.writeDB:
		db.execute("INSERT INTO stations (PI,PSN,freq,PTY,TP) VALUES (?,?,?,?,?)",t)
	    freq=self.decode_AF_freq(array[5])
	    if freq==self.RDS_data[PI]["tuned_freq"]:
	      self.RDS_data[PI]["AF"]["main"]=freq
	      if self.log:
		print("main frequency found in 0A: station:%s, freq:%0.1fM"% (self.RDS_data[PI]["PSN"],freq/1e6))
	      freq_str="0A:%0.1fM"% (freq/1e6)
	      self.signals.DataUpdateEvent.emit({'PI':PI,'freq':freq_str})
	      t=(PI,self.RDS_data[PI]["PSN"],float(freq),self.RDS_data[PI]["PTY"],int(self.RDS_data[PI]["TP"]))
	      if self.writeDB:
		db.execute("INSERT INTO stations (PI,PSN,freq,PTY,TP) VALUES (?,?,?,?,?)",t)
	  if self.RDS_data[PI].has_key("tuned_freq") :#TODO add secondary freqs
	    freq=self.decode_AF_freq(array[4])
	    diff=abs(freq-self.RDS_data[PI]["tuned_freq"])
	    if diff<100000:
	      self.RDS_data[PI]["AF"]["rxset"].add(freq)
	    freq=self.decode_AF_freq(array[5])
	    diff=abs(freq-self.RDS_data[PI]["tuned_freq"])
	    if diff<100000: 
	      self.RDS_data[PI]["AF"]["rxset"].add(freq)
	      
	  if(array[4]>= 224 and array[4]<= 249):
	    #print("AF1 detected")
	    self.RDS_data[PI]["AF"]['number']=array[4]-224
	    #self.RDS_data[PI]["AF"]['main']=self.decode_AF_freq(array[5])
	    self.signals.DataUpdateEvent.emit({'row':port,'PI':PI,'AF':self.RDS_data[PI]["AF"]})
	  if(array[5]>= 224 and array[5]<= 249):
	    print("AF2 detected (shouldn't happen) %s"%array[5])
	  
	  
	  #add frequencies to set
	  self.RDS_data[PI]["AF"]["set"].add(self.decode_AF_freq(array[4]))
	  self.RDS_data[PI]["AF"]["set"].add(self.decode_AF_freq(array[5]))
	  try:
	    self.RDS_data[PI]["AF"]["set"].remove(0)#remove control characters
	  except KeyError:
	    pass
	  
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
	   #textcolor="black"
	   textcolor=""#use default color (white if background is black)
	   if not self.RDS_data[PI]["internals"]["last_valid_psn"]==self.RDS_data[PI]["PSN"]:#ignore duplicates
	    t=(str(datetime.now()),PI,self.RDS_data[PI]["PSN"],"PSN_valid",self.RDS_data[PI]["PSN"])
	    if self.writeDB:
	      db.execute("INSERT INTO data (time,PI,PSN,dataType,data) VALUES (?,?,?,?,?)",t)
	    t=(self.RDS_data[PI]["PSN"],PI)
	    if self.writeDB:
	      db.execute("UPDATE OR IGNORE stations SET PSN=? WHERE PI IS ?",t)
	    self.RDS_data[PI]["internals"]["last_valid_psn"]=self.RDS_data[PI]["PSN"]
	  else:
	   textcolor="gray"	  
	  formatted_text=self.color_text(self.RDS_data[PI]["PSN"],adr*2,adr*2+2,textcolor,segmentcolor)
	  self.signals.DataUpdateEvent.emit({'row':port,'PI':PI,'PSN':formatted_text})
	elif (groupType == "1A"):#PIN programme item number
	  #wer nutzt 1A gruppen?
	  #antenne1: variants: 0(ECC),
	  PIN=(array[6]<<8)|(array[7])
	  SLC=(array[4]<<8)|(array[5])&0xfff#slow labeling code
	  radio_paging=array[3]&0x1f
	  LA=array[4]>>7#linkage actuator
	  variant=(array[4]>>4)&0x7
	  PIN_day=(PIN>>11)&0x1f
	  PIN_hour=(PIN>>6)&0x1f
	  PIN_minute=PIN&0x3f
	  PIN_valid= PIN_day in range(1,32) and PIN_hour in range(0,24) and PIN_minute in range(0,60)
	  if PIN_valid:
	    self.RDS_data[PI]["PIN"]=[PIN_day,PIN_hour,PIN_minute]
	    data_string="variant:%i,SLC:%04X,PIN (valid):%s "%(variant,SLC,str([PIN_day,PIN_hour,PIN_minute]))
	  else:
	    data_string="variant:%i,SLC:%04X,PIN:%04X "%(variant,SLC,PIN)
	  #%02X%02X%02X%02X%02X
	  
	  t=(str(datetime.now()),PI,self.RDS_data[PI]["PSN"],"PIN",data_string)
	  if self.writeDB:
	    db.execute("INSERT INTO data (time,PI,PSN,dataType,data) VALUES (?,?,?,?,?)",t)
	  if self.debug and not variant==0:#print if not seen before
	    print("PI:%s PSN:%s uses variant %i of 1A"%(PI,self.RDS_data[PI]["PSN"],variant))
	  if variant==0:
	    paging=array[4]&0xf
	    extended_country_code=array[5]
	    self.RDS_data[PI]["ECC"]=extended_country_code
	    if self.debug:
              print("PI:%s PSN:%s,ECC:%s"%(PI,self.RDS_data[PI]["PSN"],hex(extended_country_code)))
	  elif variant==1:
	    TMC_info=SLC
	  elif variant==2:
	    paging_info=SLC
	  elif variant==3:
	    language_codes=SLC
	    if self.debug:
	      print("PI:%s PSN:%s,language_codes:%s"%(PI,self.RDS_data[PI]["PSN"],hex(language_codes)))
	  elif variant==6:
	    #for use by broadcasters
	    if self.debug:
	      print("PI:%s PSN:%s uses variant 6 of 1A"%(PI,self.RDS_data[PI]["PSN"]))
	  elif variant==7:
	    ESW_channel_identification=SLC
	  #end of 1A decode
	elif (groupType == "2A"):#RT radiotext
	   if(not self.RDS_data[PI].has_key("RT_0")):#initialize variables
	    self.RDS_data[PI]["RT_0"]={"RT":"_"*64,"RT_valid":[False]*64,"RT_all_valid":False}
	    self.RDS_data[PI]["RT_1"]={"RT":"_"*64,"RT_valid":[False]*64,"RT_all_valid":False}
	    #self.RDS_data[PI]["RT"]="_"*64
	    #self.RDS_data[PI]["RT_valid"]=[False]*64
	    #self.RDS_data[PI]["RT_all_valid"]=False
	    self.RDS_data[PI]["RT_last_ab_flag"]=2
	   
	   adr=    array[3]&0b00001111
	   ab_flag=(array[3]&0b00010000)>>4
	   #print("PI:%s, AB:%i"%(PI,ab_flag))
	   
	   
	   #if self.RDS_data[PI]["RT_last_ab_flag"] !=ab_flag:#AB flag changed -> clear text
	   #  self.RDS_data[PI]["RT"]="_"*64
	   #  self.RDS_data[PI]["RT_valid"]=[False]*64     
	   #  self.RDS_data[PI]["RT_last_ab_flag"] =ab_flag  
	   self.RDS_data[PI]["RT_last_ab_flag"] =ab_flag
	   
	   segment=self.decode_chars(chr(array[4])+chr(array[5])+chr(array[6])+chr(array[7]))
	   #print("RT:adress: %d, segment:%s"%(adr,segment))
	   #self.signals.DataUpdateEvent.emit({'col':5,'row':port,'PI':PI,'groupType':groupType,'adress':adr,'segment':segment})
	   text_list=list(self.RDS_data[PI]["RT_"+str(ab_flag)]["RT"])
	   #determine text length:
	   try:
	     text_end=text_list.index('\r')
	   except ValueError:
	     text_end=64 #assume whole string is important
	     pass
	   predicted=False
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
	     self.RDS_data[PI]["RT_"+str(ab_flag)]["RT"]="_"*64
	     self.RDS_data[PI]["RT_"+str(ab_flag)]["RT_valid"]=[False]*64
	     #predict RT from last texts:
	     for rt in self.RDS_data[PI]["internals"]["RT_history"]:
	       if rt[adr*4:adr*4+4]==list(segment):
		 self.RDS_data[PI]["RT_"+str(ab_flag)]["RT"]="".join(rt)
		 predicted=True
	  
	   self.RDS_data[PI]["RT_"+str(ab_flag)]["RT_valid"][adr*4:adr*4+4]=[True] *4
	   if not predicted:
	    self.RDS_data[PI]["RT_"+str(ab_flag)]["RT"]="".join(text_list)
	   
	   #determine if (new) text is valid
	   self.RDS_data[PI]["RT_"+str(ab_flag)]["RT_all_valid"]=True
	   for i in range(0,text_end):
	     if (not self.RDS_data[PI]["RT_"+str(ab_flag)]["RT_valid"][i]):
	      self.RDS_data[PI]["RT_"+str(ab_flag)]["RT_all_valid"] = False
	   if(self.RDS_data[PI]["RT_"+str(ab_flag)]["RT_all_valid"]):
	     #textcolor="black"
	     textcolor=""#use default color (white if background is black)
	     l=list(self.RDS_data[PI]["RT_"+str(ab_flag)]["RT"])
	     rt="".join(l[0:text_end])#remove underscores(default symbol) after line end marker
	     if not self.RDS_data[PI]["internals"]["last_valid_rt"]==rt:#ignore duplicates #TODO add 2nd order duplicates ABAB
	      self.RDS_data[PI]["internals"]["RT_history"].append(l)
	      if len(self.RDS_data[PI]["internals"]["RT_history"])>10:#only store last 10 RTs
		self.RDS_data[PI]["internals"]["RT_history"].pop(0)
	      t=(str(datetime.now()),PI,self.RDS_data[PI]["PSN"],"RT",rt)
	      if self.writeDB:
		db.execute("INSERT INTO data (time,PI,PSN,dataType,data) VALUES (?,?,?,?,?)",t)
	      self.RDS_data[PI]["internals"]["last_valid_rt"]=rt
	      try:#save rt+ if it exist
		if self.writeDB:
		  t=(str(datetime.now()),PI,self.RDS_data[PI]["PSN"],"RT+",str(self.RDS_data[PI]["RT+"]))
		  db.execute("INSERT INTO data (time,PI,PSN,dataType,data) VALUES (?,?,?,?,?)",t)
	      except KeyError:
		pass#no rt+ -> dont save
	   else:
	     textcolor="gray"
	   formatted_text=self.color_text(self.RDS_data[PI]["RT_"+str(ab_flag)]["RT"],adr*4,adr*4+4,textcolor,segmentcolor)
	   rtcol=self.colorder.index('text')
	   self.signals.DataUpdateEvent.emit({'col':rtcol,'row':port,'PI':PI,'string':formatted_text})
	   
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
	    if AID==52550:#TMC alert-c initialize
              self.RDS_data[PI]["AID_list"][AID]["provider name"]="________"
	    if self.log:
	      print("new ODA: AID:%i, name:'%s', app_group:%s, station:%s" %(AID,app_name,app_group,PI))
	  #decode 3A group of TMC
	  if AID==52550:#TMC alert-c (continuously update)
	    variant=app_data>>14 
	    if variant==0:
	      self.RDS_data[PI]["AID_list"][AID]["LTN"]=(app_data>>6)&0x3f#location table number (6 bits)
	      self.RDS_data[PI]["AID_list"][AID]["AFI"]=(app_data>>5)&0x1#alternative frequency indicator
	      self.RDS_data[PI]["AID_list"][AID]["M"]=(app_data>>4)&0x1#transmission mode indicator
	      #Message Geographical Scope:
	      self.RDS_data[PI]["AID_list"][AID]["scope"]=""
	      if (app_data>>3)&0x1==1:
                self.RDS_data[PI]["AID_list"][AID]["scope"]+="I"#international (EUROROAD)
              if (app_data>>2)&0x1==1:
                self.RDS_data[PI]["AID_list"][AID]["scope"]+="N"#national
              if (app_data>>1)&0x1==1:
                self.RDS_data[PI]["AID_list"][AID]["scope"]+="R"#regional
              if (app_data>>0)&0x1==1:
                self.RDS_data[PI]["AID_list"][AID]["scope"]+="U"#urban
	      #self.RDS_data[PI]["AID_list"][AID]["I"]=(app_data>>3)&0x1#international (EUROROAD)
	      #self.RDS_data[PI]["AID_list"][AID]["N"]=(app_data>>2)&0x1#national
	      #self.RDS_data[PI]["AID_list"][AID]["R"]=(app_data>>1)&0x1#regional
	      #self.RDS_data[PI]["AID_list"][AID]["U"]=(app_data>>0)&0x1#urban
	    elif variant==1:
	      self.RDS_data[PI]["AID_list"][AID]["SID"]=(app_data>>6)&0x3f#service identifier
	      #timing parameters (used to switch away from TMC station without missing messages):
	      self.RDS_data[PI]["AID_list"][AID]["G"]=(app_data>>12)&0x3#gap parameter
	      self.RDS_data[PI]["AID_list"][AID]["activity_time"]=(app_data>>4)&0x3
	      self.RDS_data[PI]["AID_list"][AID]["window_time"]=(app_data>>2)&0x3
	      self.RDS_data[PI]["AID_list"][AID]["delay_time"]=(app_data>>0)&0x3
	    elif self.debug:
	      print("unknown variant %i in TMC 3A group"%variant)
	elif (groupType == "4A"):#CT clock time
	  bits=BitArray('uint:8=%i,uint:8=%i,uint:8=%i,uint:8=%i,uint:8=%i'%tuple(array[3:8]))
	  spare,datecode,hours,minutes,offsetdir,local_time_offset = bits.unpack("uint:6,uint:17,uint:5,uint:6,uint:1,uint:5")
	  local_time_offset*=0.5
	  #datecode=((array[3] & 0x03) << 15) | (array[4] <<7)|((array[5] >> 1) & 0x7f)#modified julian date
	  if datecode==0:
	    #do not update!!
	    if self.debug:
	      print("station:%s sent empty 4A group"%self.RDS_data[PI]["PSN"])
	  else:
	    #hours=((array[5] & 0x1) << 4) | ((array[6] >> 4) & 0x0f)
	    #minutes=((array[6] &0x0F)<<2)|((array[7] >>6)&0x3)
	    #offsetdir=(array[7]>>5)&0x1
	    #local_time_offset=0.5*((array[7])&0x1F)
	    if(offsetdir==1):
	      local_time_offset*=-1

	    date=datetime(1858,11,17)+timedelta(days=int(datecode))#convert from MJD (modified julian date)
	    
	    timestring="%02i:%02i (%+.1fh)" % (hours,minutes,local_time_offset)
	    datestring=date.strftime("%d.%m.%Y")
	    ctcol=self.colorder.index('time')
	    self.signals.DataUpdateEvent.emit({'col':ctcol,'row':port,'PI':PI,'string':timestring,'tooltip':datestring})
	    t=(str(datetime.now()),PI,self.RDS_data[PI]["PSN"],"CT",datestring+" "+timestring+"; datecode(MJD):"+str(datecode))
	    self.RDS_data[PI]["time"]["timestring"]=timestring
	    self.RDS_data[PI]["time"]["datestring"]=datestring
	    try:
	      self.RDS_data[PI]["time"]["datetime"]=datetime(date.year,date.month,date.day,hours,minutes)+timedelta(hours=local_time_offset)
	    except ValueError:
	      print("ERROR: could not interpret time or date:"+datestring+" "+timestring)
	    if self.writeDB:
	      db.execute("INSERT INTO data (time,PI,PSN,dataType,data) VALUES (?,?,?,?,?)",t)
	elif (groupType == "6A"):#IH inhouse data -> save for analysis
	  """In House Data:
{'130A': {'1E1077FFFF': {'count': 1,
                         'last_time': '2016-12-08 16:26:54.767596'},
          '1F23022015': {'count': 1,
                         'last_time': '2016-12-08 16:26:56.341271'}},
 'D00F': {'1E1023FFFF': {'count': 1,
                         'last_time': '2016-12-08 16:26:54.769165'},
          '1F28032008': {'count': 3,
                         'last_time': '2016-12-08 16:26:58.272420'}}}"""
	  ih_data="%02X%02X%02X%02X%02X" %(array[3]&0x1f,array[4],array[5],array[6],array[7])
	  if not self.IH_data.has_key(PI):
	    self.IH_data[PI]={}
	  if not self.IH_data[PI].has_key(ih_data):
	    self.IH_data[PI][ih_data]={}
	    self.IH_data[PI][ih_data]["count"]=0
	  self.IH_data[PI][ih_data]["count"]+=1
	  self.IH_data[PI][ih_data]["last_time"]=str(datetime.now())
	#TMC-alert-c (grouptype mostly 8A):
	elif self.RDS_data[PI]["AID_list"].has_key(52550) and self.RDS_data[PI]["AID_list"][52550]["groupType"]==groupType:#TMC alert-C
	  tmc_x=array[3]&0x1f #lower 5 bit of block2
	  tmc_y=(array[4]<<8)|(array[5]) #block3
	  tmc_z=(array[6]<<8)|(array[7])#block4
	  tmc_hash=md5.new(str([PI,tmc_x,tmc_y,tmc_z])).hexdigest()
	  tmc_T=tmc_x>>4 #0:TMC-message 1:tuning info/service provider name
	  tmc_F=int((tmc_x>>3)&0x1) #identifies the message as a Single Group (F = 1) or Multi Group (F = 0)
	  Y15=int(tmc_y>>15)
	  #timestring=self.RDS_data[PI]["time"]["timestring"]
	  datetime_received=self.RDS_data[PI]["time"]["datetime"]
	  if tmc_T == 0:
	    if tmc_F==1:#single group
	      tmc_msg=tmc_message(PI,tmc_x,tmc_y,tmc_z,datetime_received,self)
	      self.print_tmc_msg(tmc_msg)
	    elif tmc_F==0 and Y15==1:#1st group of multigroup
	      ci=int(tmc_x&0x7)
	      tmc_msg=tmc_message(PI,tmc_x,tmc_y,tmc_z,datetime_received,self)
	      #if  self.RDS_data[PI]["internals"]["unfinished_TMC"].has_key(ci):
		#print("overwriting parital message")
	      self.RDS_data[PI]["internals"]["unfinished_TMC"][ci]={"msg":tmc_msg,"time":time.time()}
	    else:
	      ci=int(tmc_x&0x7)
	      if self.RDS_data[PI]["internals"]["unfinished_TMC"].has_key(ci):
		tmc_msg=self.RDS_data[PI]["internals"]["unfinished_TMC"][ci]["msg"]
		tmc_msg.add_group(tmc_y,tmc_z)
		age=time.time()-self.RDS_data[PI]["internals"]["unfinished_TMC"][ci]["time"]
		t=(time.time(),PI,age,ci,tmc_msg.is_complete)
		#print("%f: continuing message PI:%s,age:%f,ci:%i complete:%i"%t)
		self.RDS_data[PI]["internals"]["unfinished_TMC"][ci]["time"]=time.time()
		if tmc_msg.is_complete:
		  self.print_tmc_msg(tmc_msg)#print and store message
		  del self.RDS_data[PI]["internals"]["unfinished_TMC"][tmc_msg.ci]#delete finished message
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
		segment=self.decode_chars(chr(array[4])+chr(array[5])+chr(array[6])+chr(array[7]))
		if self.debug:
		  print("TMC-info adr:%i (provider name), segment:%s, station:%s"%(adr,segment,self.RDS_data[PI]["PSN"]))
		if self.RDS_data[PI]["AID_list"].has_key(52550):
                  text_list=list(self.RDS_data[PI]["AID_list"][52550]["provider name"])
                  seg_adr_start=(adr-4)*4#start of segment
                  text_list[seg_adr_start:seg_adr_start+4]=segment
                  self.RDS_data[PI]["AID_list"][52550]["provider name"]="".join(text_list)
	      if adr== 7:#freq of tuned an mapped station (not seen yet)
		freq_TN=tmc_y>>8
		freq_ON=tmc_y&0xff#mapped frequency
		if self.debug:
		  print("TMC-info: TN:%i, station:%s"%(freq_TN,self.RDS_data[PI]["PSN"]))
		self.RDS_data[PI]["TMC_TN"]=freq_TN
	    else:
	      if self.debug:
		print("alert plus on station %s (%s)"%(PI,self.RDS_data[PI]["PSN"]))#(not seen yet)
	    
	 #self.tableobj.RDS_data["D301"]["AID_list"][52550]["provider name"]="test____"
	#RadioText+ (grouptype mostly 12A):
	elif self.RDS_data[PI]["AID_list"].has_key(19415) and self.RDS_data[PI]["AID_list"][19415]["groupType"]==groupType:#RT+
	  if not self.RDS_data[PI].has_key("RT+"):
	    #self.RDS_data[PI]["RT+"]={"history":{},"last_item_toggle_bit":2}
	    self.RDS_data[PI]["RT+"]={"last_item_toggle_bit":2}
	    self.RDS_data[PI]["RT+_history"]={}
	    self.RDS_data[PI]["internals"]["RT+_times"]={}
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
	    t=(str(datetime.now()),PI,self.RDS_data[PI]["PSN"],"RT+",str(self.RDS_data[PI]["RT+"]))
	    if self.writeDB:
	      db.execute("INSERT INTO data (time,PI,PSN,dataType,data) VALUES (?,?,?,?,?)",t)
	    self.RDS_data[PI]["RT+_history"][str(datetime.now())]=copy.deepcopy(self.RDS_data[PI]["RT+"])#save old item
	    self.RDS_data[PI]["RT+"]["last_item_toggle_bit"] = item_toggle_bit
	    rtcol=self.colorder.index('text')
	    if self.debug:
	      print("toggle bit changed on PI:%s, cleared RT-tt"%PI)
	    self.signals.DataUpdateEvent.emit({'col':rtcol,'row':port,'PI':PI,'tooltip':""})
	  if self.RDS_data[PI].has_key("RT_0"):
	    ab_flag=self.RDS_data[PI]["RT_last_ab_flag"]
	    rt=self.RDS_data[PI]["RT_"+str(ab_flag)]["RT"]
	    rt_valid=self.RDS_data[PI]["RT_"+str(ab_flag)]["RT_valid"]
	    if not tag1_type=="DUMMY_CLASS" and all(rt_valid[tag1_start:tag1_start+tag1_len+1]):
	      self.RDS_data[PI]["RT+"][tag1_type]=rt[tag1_start:tag1_start+tag1_len+1]
	      self.RDS_data[PI]["internals"]["RT+_times"][tag1_type]=time.time()
	    if not tag2_type=="DUMMY_CLASS" and all(rt_valid[tag2_start:tag2_start+tag2_len+1]):
	      self.RDS_data[PI]["RT+"][tag2_type]=rt[tag2_start:tag2_start+tag2_len+1]
	      self.RDS_data[PI]["internals"]["RT+_times"][tag2_type]=time.time()
	  #check outdated tags:
	  for tagtype in self.RDS_data[PI]["internals"]["RT+_times"].keys():#.keys() makes copy to avoid RuntimeError: dictionary changed size during iteration
	    age=time.time()-self.RDS_data[PI]["internals"]["RT+_times"][tagtype]
	    if age>90:#delete if older than 90 sek#TODO delete if toggle bit changes?, delete if tag changes? (title change -> delete artist)
	      del self.RDS_data[PI]["internals"]["RT+_times"][tagtype]
	      del self.RDS_data[PI]["RT+"][tagtype]
	  
	  
	  tags="ir:%i,it:%i"%(item_running_bit,item_toggle_bit)
	  rtpcol=self.colorder.index('RT+')
	  self.signals.DataUpdateEvent.emit({'col':rtpcol,'row':port,'PI':PI,'string':tags})
	  if(tag2_type=="ITEM.TITLE" and self.RDS_data[PI].has_key("RT_0")):#TODO remove duplicate code
	    ab_flag=self.RDS_data[PI]["RT_last_ab_flag"]
	    rt=self.RDS_data[PI]["RT_"+str(ab_flag)]["RT"]
	    rt_valid=self.RDS_data[PI]["RT_"+str(ab_flag)]["RT_valid"]
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
	      self.PI_dict[PI_ON]=0#initialize dict, even if no packets received
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
		#textcolor="black"
		textcolor=""#use default color (white if background is black)
		
	      else:
		textcolor="gray"	  
	      formatted_text=self.color_text(self.RDS_data[PI_ON]["PSN"],variant*2,variant*2+2,textcolor,segmentcolor)
	      self.RDS_data[PI]["EON"][PI_ON]["PSN"]=PS_ON_str
	      self.RDS_data[PI_ON]["PSN"]=PS_ON_str
	      #formatted_text="<font face='Courier New' color='%s'>%s</font>"%("purple",PS_ON_str)
	      self.signals.DataUpdateEvent.emit({'PI':PI_ON,'PSN':formatted_text})
	      try:
		t=(PI_ON,self.RDS_data[PI_ON]["PSN"],float(self.RDS_data[PI_ON]["AF"]["main"]),self.RDS_data[PI_ON]["PTY"],int(self.RDS_data[PI_ON]["TP"]))
		if self.writeDB:
		  db.execute("INSERT OR REPLACE INTO stations (PI,PSN,freq,PTY,TP) VALUES (?,?,?,?,?)",t)
	      except KeyError:
		#not all info present -> no db update
		pass
	    if variant==4:#AF_ON
	      if self.debug:
		print("AF_ON method A")#TODO
	    if variant in range(5,10):#variant 5..9 -> mapped freqs
	      freq_TN=self.decode_AF_freq(array[4])
	      freq_ON=self.decode_AF_freq(array[5])
	      #lock in tuned network if freq_TN matches decoder frequency
	      if(self.RDS_data[PI].has_key("tuned_freq") and freq_TN==self.RDS_data[PI]["tuned_freq"]and not self.RDS_data[PI]["AF"].has_key("main")):
		if self.log:
		  print("main frequency found in 14A: station:%s, freq:%0.1fM"% (self.RDS_data[PI]["PSN"],freq_TN/1e6))
		self.RDS_data[PI]["AF"]["main"]=freq_TN
		freq_str="EON_TN:%0.1fM"% (freq_TN/1e6)
		self.signals.DataUpdateEvent.emit({'PI':PI,'freq':freq_str})
	      #lock in ON if TN is locked in
	      if(self.RDS_data[PI]["AF"].has_key("main") and self.RDS_data[PI]["AF"]["main"]==freq_TN and not self.RDS_data[PI_ON]["AF"].has_key("main")):
		if self.log:
		  print("mapped frequency found in 14A: station:%s, freq:%0.1fM"% (self.RDS_data[PI_ON]["PSN"],freq_ON/1e6))
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
	elif (groupType == "8A"):
	  if self.debug:
	    print("8A without 3A on PI:%s"%PI)
	#else:#other group
	if 1==1:
	  #printdelay=50
	  printdelay=500
	  self.printcounter+=0#printing disabled
	  if self.printcounter == printdelay and self.debug:
	    
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
	    
	pr.disable() #disabled-internal-profiling
	#end of handle_msg
    def print_tmc_msg(self,tmc_msg):
      try:
	PI=tmc_msg.PI
	tmc_F=tmc_msg.is_single
	tmc_hash=tmc_msg.tmc_hash
	refloc_name=""
	reflocs=tmc_msg.location.reflocs
	if not self.TMC_data.has_key(tmc_hash):#if message new
	  try:
	    #message_string="TMC-message,event:%s lcn:%i,location:%s,reflocs:%s, station:%s"%(str(tmc_msg.event),tmc_msg.location.lcn,tmc_msg.location,reflocs,self.RDS_data[PI]["PSN"])
	    #message_string=tmc_msg.log_string()
	    self.TMC_data[tmc_hash]=tmc_msg
	    self.signals.DataUpdateEvent.emit({'TMC_log':tmc_msg,'multi_str':tmc_msg.multi_str()})
	    #t=(str(datetime.now()),PI,self.RDS_data[PI]["PSN"],"ALERT-C",message_string.decode("utf-8"))
	    #self.db.execute("INSERT INTO data (time,PI,PSN,dataType,data) VALUES (?,?,?,?,?)",t)
	    timestring=self.RDS_data[PI]["time"]["timestring"]
	    #message_string="%s ,locname:%s, reflocs:%s"%(str(tmc_msg.event),tmc_msg.location,reflocs)
	    message_string=tmc_msg.db_string()
	    t=(tmc_hash,timestring,PI, tmc_F,tmc_msg.event.ecn,int(tmc_msg.location.lcn),tmc_msg.tmc_DP,tmc_msg.tmc_D,tmc_msg.tmc_dir,tmc_msg.tmc_extent,message_string.decode("utf-8"),tmc_msg.multi_str().decode("utf-8"),str(tmc_msg.debug_data))
	    if self.writeDB:
	      self.db.execute("INSERT INTO TMC (hash,time,PI, F,event,location,DP,div,dir,extent,text,multi,rawmgm) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",t)
	  except Exception as e:
	    print(e)
	    raise
	    #print("line 1064")
	    
      except KeyError:
	#print("location '%i' not found"%tmc_location)
	pass
    def print_results(self):
	s = StringIO.StringIO()
	sortby = 'cumulative'
	ps = pstats.Stats(pr, stream=s).sort_stats(sortby) 
	ps.print_stats() 
	print(s.getvalue())
    def decode_AF_freq(self,freq_raw):
      #if freq_raw in range(1,205):#1..204 BAD coding -> memory usage
      if 1<=freq_raw <=204:
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
      0b1101:u"ÂÄÊËÎÏÔÖÛÜřčšžđŀ"}
      #charlist=list(charstring)
      return_string=""
      for i,char in enumerate(charstring):
      	
	if ord(char)<= 0b01111111:
	  #charlist[i]=char #use ascii
	  return_string+=char
	else:
	  #split byte
	  alnr=(ord(char)&0xF0 )>>4 #upper 4 bit
	  index=ord(char)&0x0F #lower 4 bit 
	  try:
	    #charlist[i]=alphabet[alnr][index]
	    return_string+=alphabet[alnr][index]
	  except KeyError:
	    return_string+="?%02X?"%ord(char)
            print("symbol not decoded: "+"?%02X?"%ord(char)+"in string:"+return_string)
	    #charlist[i]='?'#symbol not decoded #TODO
	    pass
      #return "".join(charlist)
      return return_string
    def color_text(self, text, start,end,textcolor,segmentcolor):
      #formatted_text="<font face='Courier New' color='%s'>%s</font><font face='Courier New' color='%s'>%s</font><font face='Courier New' color='%s'>%s</font>"% (textcolor,text[:start],segmentcolor,text[start:end],textcolor,text[end:])
      #formatted_text="<span style='background-color: yellow;color:%s'>%s</span><span style='color:%s'>%s</span><span style='color:%s'>%s</span>"% (textcolor,text[:start],segmentcolor,text[start:end],textcolor,text[end:])
      formatted_text=("<span style='font-family:Courier New;color:%s'>%s</span>"*3)% (textcolor,text[:start],segmentcolor,text[start:end],textcolor,text[end:])
      return formatted_text
class rds_parser_table_qt_Widget(QtGui.QWidget):
    def __init__(self, signals,label,tableobj,showTMC):
	#print("gui initializing")self.tableobj.RDS_data["D3A2"]
	self.signals = signals
	self.tableobj=tableobj
	self.showTMC=showTMC
	self.signals.DataUpdateEvent.connect(self.display_data)
        """ Creates the QT Range widget """
        QtGui.QWidget.__init__(self)
        layout = Qt.QVBoxLayout()
        #self.label = Qt.QLabel(label)
        #layout.addWidget(self.label)#title of table disabled to save space
        #layout.addWidget(self.label)
        self.setLayout(layout)
        #self.decoder_to_PI={}
        self.PI_to_row={}
        self.table=QtGui.QTableWidget(self)
        rowcount=0
        self.table.setRowCount(rowcount)
        self.table.setColumnCount(10)
        self.table.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers) #disallow editing

        #self.colorder=['ID','freq','name','buttons','PTY','AF','time','text','quality']
        self.colorder=tableobj.colorder
 ##button.clicked.connect(self.getDetails)
     
        layout.addWidget(self.table)
        self.table.setHorizontalHeaderLabels(self.colorder) 
        #self.table.setMaximumHeight(300)#TODO use dynamic value
        
        button_layout = Qt.QHBoxLayout()
        codebutton = QtGui.QPushButton("code.interact")
        codebutton.clicked.connect(self.onCLick)
        button_layout.addWidget(codebutton)
        ih_button = QtGui.QPushButton("show IH data")
        ih_button.clicked.connect(self.showIHdata)
        button_layout.addWidget(ih_button)
        save_button = QtGui.QPushButton("save")
        save_button.clicked.connect(self.saveData)
        button_layout.addWidget(save_button)
        print_button = QtGui.QPushButton("print profile")
        print_button.clicked.connect(self.printProfile)
        button_layout.addWidget(print_button)
        mode_button = QtGui.QPushButton("mode")
        mode_button.clicked.connect(self.switchMode)
        button_layout.addWidget(mode_button)
        layout.addLayout(button_layout)
        label_layout = Qt.QHBoxLayout()
        self.freq_label=QtGui.QLabel("decoder frequencies:")
        #self.freq_label.setTextFormat(QtCore.Qt.RichText)
        #self.freq_label.setTextFormat(QtCore.Qt.PlainText)
        self.count_label=QtGui.QLabel("count:")
        label_layout.addWidget(self.freq_label)  
        label_layout.addWidget(self.count_label)  
        layout.addLayout(label_layout)
        #TODO set different minsize if TMC is shown
        self.setMinimumSize(Qt.QSize(500,40*self.tableobj.nPorts))
        if self.showTMC:
	  self.tmc_message_label=QtGui.QLabel("TMC messages:")
	  self.event_filter=QtGui.QLineEdit()#QPlainTextEdit ?
	  self.location_filter=QtGui.QLineEdit(u"Baden-Württemberg")
	  #self.location_filter=QtGui.QLineEdit(u"")
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
        self.lastResizeTime=0
        self.clip = QtGui.QApplication.clipboard()
	#self.cb.clear(mode=cb.Clipboard )	
	#self.cb.setText("Clipboard Text", mode=cb.Clipboard)
    def filterChanged(self):
      print("filter changed")
      ef=unicode(self.event_filter.text().toUtf8(), encoding="UTF-8").lower()
      lf=unicode(self.location_filter.text().toUtf8(), encoding="UTF-8").lower()
      self.logOutput.clear()
      #filters=[{"type":"location", "str":u"Baden-Württemberg"}]
      filters=[{"type":"location", "str":lf},{"type":"event", "str":ef}]
      self.logOutput.append(Qt.QString.fromUtf8(self.tableobj.tmc_messages.getLogString(filters)))
      #self.logOutput.append(Qt.QString.fromUtf8(self.tableobj.tmc_messages.getLogString([])))
    def keyPressEvent(self, e):
      if (e.modifiers() & QtCore.Qt.ControlModifier) and len(self.table.selectedRanges())>0:
	  selected = self.table.selectedRanges().pop()
	  selected.leftColumn()
	  selected.topRow()
	  if e.key() == QtCore.Qt.Key_C: #copy
	    try:
	      qs = self.table.cellWidget(selected.topRow(),selected.leftColumn()).text()#get QString from table
	      s=re.sub("<.*?>","", str(qs))#remove html tags
	      self.clip.setText(s)
	    except Exception as e:
	      print(e)
	      print("no text, cant copy")
    def insert_empty_row(self):
      rowPosition = self.table.rowCount()
      self.table.insertRow(rowPosition)
      #for col in range(self.table.columnCount()-1):#all labels except in last column -> buttons
#	self.table.setCellWidget(rowPosition,col,QtGui.QLabel())
      #initialize labels everywhere:
      for col in range(self.table.columnCount()):
	self.table.setCellWidget(rowPosition,col,QtGui.QLabel())
      button_layout = Qt.QHBoxLayout()
      details_button=QtGui.QPushButton("Detail")
      details_button.clicked.connect(functools.partial(self.getDetails, row=rowPosition))
      button_layout.addWidget(details_button)
      left_button=QtGui.QPushButton("L")
      left_button.clicked.connect(functools.partial(self.setAudio, row=rowPosition,audio_channel="left"))
      button_layout.addWidget(left_button)
      right_button=QtGui.QPushButton("R")
      right_button.clicked.connect(functools.partial(self.setAudio, row=rowPosition,audio_channel="right"))
      button_layout.addWidget(right_button)
      #self.table.setCellWidget(rowPosition,self.table.columnCount()-1,button_layout)
      cellWidget = QtGui.QWidget()
      cellWidget.setLayout(button_layout)
      #button_col=self.table.columnCount()-1
      button_col=3
      self.table.setCellWidget(rowPosition,button_col,cellWidget)
    def display_data(self, event):
	#pp.pprint(event)
	if type(event)==dict and event.has_key('group_count'):
	  self.count_label.setText("count:%02i, max:%i"%(event['group_count'],event['group_count_max']))
	if type(event)==dict and event.has_key('decoder_frequencies'):
	  self.freq_label.setText(event['decoder_frequencies'])
	if type(event)==dict and event.has_key('TMC_log') and self.showTMC:
	  tmc_msg=event['TMC_log']
	  ef=unicode(self.event_filter.text().toUtf8(), encoding="UTF-8").lower()
	  lf=unicode(self.location_filter.text().toUtf8(), encoding="UTF-8").lower()
	  filters=[{"type":"location", "str":lf},{"type":"event", "str":ef}]
	  if self.tableobj.tmc_messages.matchFilter(tmc_msg,filters):
	    self.logOutput.append(Qt.QString.fromUtf8(tmc_msg.log_string()))
	    self.logOutput.append(Qt.QString.fromUtf8(tmc_msg.multi_str()))
	if type(event)==dict and event.has_key('TMC_log_str')and self.showTMC:
	  ef=unicode(self.event_filter.text().toUtf8(), encoding="UTF-8").lower()
	  lf=unicode(self.location_filter.text().toUtf8(), encoding="UTF-8").lower()
	  text=unicode(event['TMC_log_str'], encoding="UTF-8").lower()
	  if not text.find(lf)==-1 and not text.find(ef)==-1:
	    self.logOutput.append(Qt.QString.fromUtf8(event['TMC_log_str']))
	if type(event)==dict and event.has_key('PI'): 
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
	  if event.has_key('AF'):
	    #setAF
	    PIcol=self.colorder.index('AF')
	    self.table.cellWidget(row,PIcol).setText(str(event['AF']['number']))
	  if event.has_key('PSN'):
	    #setPSN
	    PSNcol=self.colorder.index('name')
	    item=self.table.cellWidget(row,PSNcol)
	    item.setText(event['PSN'])
	if time.time()-self.lastResizeTime > 2:#every 2 seconds
		self.table.resizeColumnsToContents()
		self.lastResizeTime=time.time()
	#end of display-data
    def printProfile(self):
      self.tableobj.print_results()
    def switchMode(self):
      #print("mode switch message sent")
      send_pmt = pmt.pmt_to_python.pmt_from_dict({"cmd":"switch mode"})
      #send_pmt = pmt.string_to_symbol("switch mode")
      self.tableobj.message_port_pub(pmt.intern('ctrl'), send_pmt)
    def saveData(self):
	filename="RDS_data_"+str(datetime.now())+".txt"
	f=open(self.tableobj.workdir+filename,"w")
	rds_data=copy.deepcopy(self.tableobj.RDS_data)
	for PI in sorted(rds_data):
	  try:
	    del rds_data[PI]['PSN_valid']
	    del rds_data[PI]['RT_valid']
	  except KeyError:
	    pass
	f.write("Data:%s"%pp.pformat(rds_data))
	f.write("\n\nIn House Data:\n%s"%pp.pformat(self.tableobj.IH_data))
	f.close()
	print("data saved in file %s"%filename)
    def showIHdata(self):
	view=Qt.QDialog()
	l=QtGui.QLabel("In House Data:\n%s"%pp.pformat(self.tableobj.IH_data))
	l.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse |QtCore.Qt.TextSelectableByKeyboard)
	l.setWordWrap(True)
	#self.IH_data
	layout=Qt.QVBoxLayout()
	layout.addWidget(l)
	view.setLayout(layout)
	view.exec_()
    def setAudio(self,row,audio_channel):
	
	PIcol=self.colorder.index('ID')
	PI=str(self.table.cellWidget(row,PIcol).text()) 
	freq=int(self.tableobj.RDS_data[PI]['AF']['main'])
	#print("setaudio row:%i, chan:%s, PI:%s,freq:%i"%(row,audio_channel,PI,freq))
	send_pmt = pmt.pmt_to_python.pmt_from_dict({"cmd":"set_audio_freq","chan":audio_channel,"freq":freq})
	self.tableobj.message_port_pub(pmt.intern('ctrl'), send_pmt)	
	#catch:
	#print("no freq, cant set decoder")#show notification? popup: too intrusive, log: maybe not visible, other possibility?
	#print("freq not in RX BW")#automatically shift freq-tune?
    def getDetails(self,row):
	PIcol=self.colorder.index('ID')
	PI=str(self.table.cellWidget(row,PIcol).text())
	view = chart.DialogViewer()
	if self.tableobj.PI_dict.has_key(PI) and self.tableobj.PI_dict[PI]>3:#dont print piechart if no packets received (detected via EON)
	  table=chart.DataTable()
	  table.addColumn('groupType')
	  table.addColumn('numPackets')
	  blockcounts=copy.deepcopy(self.tableobj.RDS_data[PI]['blockcounts'])
	  del blockcounts['any']
	  #lambda function removes last character of PI string (A or B) and sorts based on integer valure of number in front
	  for key in sorted(blockcounts,key=lambda elem: int(elem[0:-1])):
	    count=blockcounts[key]
	    table.addRow([key+": "+str(count),count])
	  mychart=chart.PieChart(table)
	  view.setGraph(mychart)
	#view.resize(360, 240)
	#view.resize(380, 550)
	rds_data=copy.deepcopy(self.tableobj.RDS_data[PI])
	try:
	  del rds_data['blockcounts']
	  del rds_data['PSN_valid']
	  del rds_data["RT_0"]['RT_valid']
	  del rds_data["RT_1"]['RT_valid']	  
	  rds_data['internals']['RT_history']=["".join(rt) for rt in rds_data['internals']['RT_history']]#combine char lists into strings (more compact)
	except KeyError:
	  pass
	l=QtGui.QLabel("Data:%s"%pp.pformat(rds_data))
	l.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse |QtCore.Qt.TextSelectableByKeyboard)
	l.setWordWrap(True)
	#l=QtGui.QLabel("Data:")
	
	#view.layout().addWidget(l)
	
	scrollArea = QtGui.QScrollArea(self)
        scrollArea.setWidgetResizable(True)
        scrollArea.setWidget(l)
	view.layout().addWidget(scrollArea)
	view.setWindowTitle(self.tableobj.RDS_data[PI]["PSN"])
	view.exec_()
    def onCLick(self):
	print("button clicked")	
	code.interact(local=locals())
if __name__ == "__main__":
    from PyQt4 import Qt
    import sys


    app = Qt.QApplication(sys.argv)
    mainobj= rds_parser_table_qt_Signals()
    #mainobj=None
    widget = rds_parser_table_qt_Widget(mainobj,"TestLabel")
    widget.show()
    widget.setWindowTitle("Test Qt gui")
    widget.setGeometry(200,200,600,300)
    sys.exit(app.exec_())

    widget = None


