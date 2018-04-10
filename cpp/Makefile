TARGET = GEM
CXXFLAGS = -O2 -std=c++1z

all : $(TARGET)



$(TARGET) : $(TARGET)_wrap.o $(TARGET).o model.o  libgem_readout.so libgem_reco_online.so
	g++ -shared $^ -o _$(TARGET).so  libgem_readout.so libgem_reco_online.so

$(TARGET)_wrap.o : $(TARGET)_wrap.cxx
	g++ $(CXXFLAGS) -c $^ -o $@ -I /usr/include/python3.5 -fPIC

$(TARGET)_wrap.cxx : $(TARGET).cpp $(TARGET).i
	swig -c++ -python $(TARGET).i

$(TARGET).o : $(TARGET).cpp 
	g++ $(CXXFLAGS) -c $^ -o $@ -fPIC
	
model.o : model.cpp
	g++ $(CXXFLAGS) -c $^ -o $@ -fPIC

libgem_readout.so:
	ln -sf /home/lsrp/DEUTRON/gemd_lib/$@

libgem_reco_online.so:
	ln -sf /home/lsrp/DEUTRON/gemd_lib/$@

clean :
	rm -f *.o *$(TARGET).so $(TARGET).py $(TARGET).pyc $(TARGET).py $(TARGET)_wrap.cxx
