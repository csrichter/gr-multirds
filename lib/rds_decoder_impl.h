/* -*- c++ -*- */
/* 
 * Copyright 2016 <+YOU OR YOUR COMPANY+>.
 * 
 * This is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 3, or (at your option)
 * any later version.
 * 
 * This software is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 * 
 * You should have received a copy of the GNU General Public License
 * along with this software; see the file COPYING.  If not, write to
 * the Free Software Foundation, Inc., 51 Franklin Street,
 * Boston, MA 02110-1301, USA.
 */

#ifndef INCLUDED_CRFA_RDS_DECODER_IMPL_H
#define INCLUDED_CRFA_RDS_DECODER_IMPL_H

#include <crfa/rds_decoder.h>

namespace gr {
  namespace crfa {

    class rds_decoder_impl : public rds_decoder
    {
public:
	rds_decoder_impl(bool log, bool debug);

private:
	~rds_decoder_impl();

      // Where all the action really happens
      int work(int noutput_items,
         gr_vector_const_void_star &input_items,
         gr_vector_void_star &output_items);
	void enter_no_sync();
	void enter_sync(unsigned int);
	unsigned int calc_syndrome(unsigned long, unsigned char);
	void decode_group(unsigned int*);

	unsigned long  bit_counter;
	unsigned long  lastseen_offset_counter, reg;
	unsigned int   block_bit_counter;
	unsigned int   wrong_blocks_counter;
	unsigned int   blocks_counter;
	unsigned int   group_good_blocks_counter;
	unsigned int   group[4];
	unsigned char  offset_chars[4];  // [ABCcDEx] (x=error)
	bool           debug;
	bool           log;
	bool           presync;
	bool           good_block;
	bool           group_assembly_started;
	unsigned char  last_wrong_blocks_counter;
	unsigned char  lastseen_offset;
	unsigned char  block_number;
	enum { NO_SYNC, SYNC } d_state;

    };

  } // namespace crfa
} // namespace gr

#endif /* INCLUDED_CRFA_RDS_DECODER_IMPL_H */

