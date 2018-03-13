
### Dependencies

- GNU Radio v3.7.X

- Software from your package manager. For Ubuntu systems, it's
```
sudo apt-get install cmake libboost-all-dev liblog4cpp5-dev swig
```
- the python module bitstring
```
sudo pip install bitstring
or
sudo apt-get insall python-bitstring
```

ubuntu 16.04: sudo apt-get install gnuradio cmake (3.7.9.1-2ubuntu1)

git://git.osmocom.org/rtl-sdr.git
sudo apt-get install libusb-1.0-0-dev libusb-dev swig
swig -> "python support" in osmocomsdr
http://osmocom.org/projects/sdr/wiki/rtl-sdr

apt-get install gr-osmosdr
### Installation

```
mkdir build
cd build
cmake ..
make
sudo make install
sudo ldconfig
```
if you don't see the new blocks in gnuradio companion, click the reload button

#### without root privileges
put this in your .bashrc file (replace user with your username):
```
BASE=/home/user/gnuradio-prefix
export PATH=${PATH}:${BASE}/bin
export LD_LIBRARY_PATH=${LD_LIBRARY_PATH}:${BASE}/lib64:${BASE}/lib
export PKG_CONFIG_PATH=${PKG_CONFIG_PATH}:${BASE}/lib64/pkgconfig
export PYTHONPATH=${PYTHONPATH}:${BASE}/lib64/python2.7/site-packages/
export GRC_BLOCKS_PATH=${GRC_BLOCKS_PATH}:${BASE}/share/gnuradio/grc/blocks
```
this tells gnuradio companion where to find the blocks, and your system where to find the executables

when building use the following cmake command (replace user with your username):
```
cmake -DCMAKE_INSTALL_PREFIX:PATH=/home/user/gnuradio-prefix ..
```
now make should install the module to the specified folder, without needing root privileges



### Usage

open apps/ifft-RDS-decoder_hier-block.grc flow graph in GNU Radio Companion.
Click "generate" to create the hierarchical decoder block.
Click "reload" to load the generated block
open apps/fft-multi-decoder.grc flow graph.
set the work directory of the "RDS parser Table" block as the full path (~ shortcut doesnt work) of the data directory (with trailing slash)

### Demos


### History

forked from https://github.com/bastibl/gr-rds
Continuation of gr-rds on BitBucket (originally from Dimitrios Symeonidis https://bitbucket.org/azimout/gr-rds/ and also on CGRAN https://www.cgran.org/wiki/RDS).
