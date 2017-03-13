/* -*- c++ -*- */

#define CRFA_API

%include "gnuradio.i"			// the common stuff

//load generated python docstrings
%include "crfa_swig_doc.i"

%{
#include "crfa/rds_decoder.h"
#include "crfa/diff_add_sync_decim.h"
#include "crfa/sync_decim.h"
%}

%include "crfa/rds_decoder.h"
GR_SWIG_BLOCK_MAGIC2(crfa, rds_decoder);
%include "crfa/diff_add_sync_decim.h"
GR_SWIG_BLOCK_MAGIC2(crfa, diff_add_sync_decim);
%include "crfa/sync_decim.h"
GR_SWIG_BLOCK_MAGIC2(crfa, sync_decim);
