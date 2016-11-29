/* -*- c++ -*- */

#define CRFA_API

%include "gnuradio.i"			// the common stuff

//load generated python docstrings
%include "crfa_swig_doc.i"

%{
#include "crfa/rds_decoder.h"
%}

%include "crfa/rds_decoder.h"
GR_SWIG_BLOCK_MAGIC2(crfa, rds_decoder);
