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

#include <crfa/rds_decoder_redsea.h>

namespace gr {
  namespace crfa {

    class rds_decoder_redsea_impl : public rds_decoder_redsea
    {
public:
        rds_decoder_redsea_impl(bool log, bool debug);

private:
        ~rds_decoder_redsea_impl();

      // Where all the action really happens
      int work(int noutput_items,
         gr_vector_const_void_star &input_items,
         gr_vector_void_star &output_items);
        void enter_no_sync();
        void enter_sync(uint16_t);
        uint16_t calc_syndrome(uint32_t, uint8_t);
        void decode_group(uint16_t*);

        uint32_t  bit_counter;
        uint32_t  lastseen_offset_counter, reg;
        uint16_t   block_bit_counter;
        uint16_t   wrong_blocks_counter;
        uint16_t   blocks_counter;
        uint16_t   group_good_blocks_counter;
        uint16_t   group[4];
        uint8_t  offset_chars[4];  // [ABCcDEx] (x=error)
        bool           debug;
        bool           log;
        bool           presync;
        bool           good_block;
        bool           group_assembly_started;
        uint8_t  last_wrong_blocks_counter;
        uint8_t  lastseen_offset;
        uint8_t  block_number;
        std::map<std::pair<uint16_t, char>, uint32_t> kErrorLookup;
        enum { NO_SYNC, SYNC } d_state;
        //below copied from redsea
        enum eOffset {
          OFFSET_A, OFFSET_B, OFFSET_C, OFFSET_CI, OFFSET_D, OFFSET_INVALID
        } ;
        std::map<std::pair<uint16_t, char>, uint32_t> makeErrorLookupTable();
        uint32_t calcSyndrome(uint32_t vec);
        eOffset offsetForSyndrome(uint16_t syndrome);
        eOffset nextOffsetFor(eOffset o);
        uint32_t correctBurstErrors(uint32_t block, char offset);
        

    };

  } // namespace crfa
} // namespace gr

#endif /* INCLUDED_CRFA_RDS_DECODER_IMPL_H */

