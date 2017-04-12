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

#references to tableobj:
#~ label6_suppl_info
#~ ecl_dict
#~ tmc_update_class_names
#~ lcl_dict
#~ debug
#~ tmc_messages

#rename to common.py?
from bitstring import BitArray 
import copy,code

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
    self.is_cancellation = False
    self.updateClass=999#invalid
    self.is_valid=False
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
        if  self.messages[lcn].has_key(updateClass) and self.messages[lcn][updateClass].tmc_hash ==message.tmc_hash:#if same message -> add confirmation
            self.messages[lcn][updateClass].add_confirmation(message)
	else:#(over)write message
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
    try:
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
    except UnicodeDecodeError as e:
      print(e)
      code.interact(local=locals())
      pass
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
    if not self.event.is_valid:
      return ""
    elif "D" in self.event.durationType and not self.event.nature=="F":
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
    retstr=""
    try:
      retstr=str(self.event.updateClass)+": "+self.getTime()+": "+self.location_text()+": "+self.events_string()+"; "+self.info_str()+"; "+self.psn
    except UnicodeDecodeError as e:
      print e
      code.interact(local=locals())
      
    return retstr    
    #2017-03-16 fix:self.psn.encode("utf-8"),  utf8 decoding happens later
    #2017-04-10 undid "fix":UnicodeDecodeError: 'ascii' codec can't decode byte 0xc3 in position 0: ordinal not in range(128)
  #def db_string(self):
  #  return str(self.location)+": "+str(self.event.updateClass)+": "+self.events_string()+"; "+self.info_str()
  def map_string(self):
      retstr='<span title="%s">'%self.getDate()+str(self.event.updateClass)+": "+self.getTime()+'</span>'
      retstr+='<span title="%s">'%self.multi_str()+": "+self.events_string()+self.info_str()+"; "+"</span>"
      retstr+='<span title="%i">'%self.confirmations+str(list(self.psns)).replace("'", '"')+"</span>"
      return retstr
           
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
      templates={"de_1":"{A}, {B} in Richtung {C}"#coding handbook: zwischen {D} und {E}, sprachdurchsagen(manchmal): zwischen {E} und {D} TODO: swap D and E if offset-dir negative
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
    #return unicode(text,encoding="utf-8")
    return text
  def __str__(self):
    return str(self.event.updateClass)+": "+self.getTime()+": "+self.events_string()+"; "+self.multi_str()
  def __repr__(self):
    #event_name=self.ecl_dict[self.tmc_event][1]
    #message_string="TMC-message,event:%s location:%i,reflocs:%s, station:%s"%(event_name,self.tmc_location,self.ref_locs(self.tmc_location,""),self.RDS_data[PI]["PSN"])
    return "single:%i,complete:%i,event:%i location:%s"%(self.is_single,self.is_complete,self.event.ecn,self.location)
  def getDate(self):
    if self.hastime:
      return self.datetime_received.strftime("%Y-%m-%d")
    else:
      return "no valid date"
  def getTime(self):#always returns string
    if self.hastime:
      return self.datetime_received.strftime("%H:%M")
    else:
      return "88:88"
  def add_confirmation(self,tmc_msg):
      self.PIs.add(tmc_msg.PI)
      self.psns.add(tmc_msg.psn)
      self.confirmations+=1
  def __init__(self,PI,psn,ltn,tmc_x,tmc_y,tmc_z,datetime_received,tableobj):#TODO handle out of sequence data
    #self.psn=tableobj.RDS_data[PI]["PSN"]
    self.psn=psn
    self.psns=set([psn])
    self.PI=PI
    self.PIs=set([PI])
    self.confirmations=1
    self.debug_data=""
    self.tableobj=tableobj
    #self.isCancelled=False
    self.cancellation_time=None
    self.tmc_hash=hash((tmc_x,tmc_y,tmc_z))
    tmc_T=tmc_x>>4 #0:TMC-message 1:tuning info/service provider name
    assert tmc_T==0, "this is tuning info and no alert_c message"
    Y15=int(tmc_y>>15)
    tmc_F=int((tmc_x>>3)&0x1) #identifies the message as a Single Group (F = 1) or Multi Group (F = 0)
    self.is_single=(tmc_F==1)
    self.is_multi=(tmc_F==0)
    #check LTN
    try:
      msg_ltn=ltn#tableobj.RDS_data[PI]["AID_list"][52550]["LTN"]
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
