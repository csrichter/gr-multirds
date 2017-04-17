/* -*- c++ -*- */

#define CRFA_API

%include "gnuradio.i"			// the common stuff

//load generated python docstrings
%include "multirds_swig_doc.i"

%{
#include "multirds/rds_decoder.h"
#include "multirds/sync_decim.h"
#include "multirds/rds_decoder_redsea.h"
%}

%include "multirds/rds_decoder.h"
GR_SWIG_BLOCK_MAGIC2(multirds, rds_decoder);

%include "multirds/sync_decim.h"
GR_SWIG_BLOCK_MAGIC2(multirds, sync_decim);
%include "multirds/rds_decoder_redsea.h"
GR_SWIG_BLOCK_MAGIC2(multirds, rds_decoder_redsea);
