# Copyright 2011 Free Software Foundation, Inc.
#
# This file is part of GNU Radio
#
# GNU Radio is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
#
# GNU Radio is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GNU Radio; see the file COPYING.  If not, write to
# the Free Software Foundation, Inc., 51 Franklin Street,
# Boston, MA 02110-1301, USA.
install(FILES
    multirds_multi_rds_printer.xml
    multirds_rds_table_qt.xml
    multirds_rds_parser_table_qt.xml
    multirds_rds_decoder.xml
    multirds_max_freq.xml
    multirds_stream_selector.xml
    multirds_vector_cutter.xml
    multirds_decoder_compare.xml
    multirds_sync_decim.xml
    multirds_rds_decoder_redsea.xml
    multirds_qtgui_range.xml
    multirds_variable_setter.xml
    multirds_tmc_parser.xml
    multirds_pilot_SNR.xml
    multirds_stream_router.xml DESTINATION share/gnuradio/grc/blocks
)
