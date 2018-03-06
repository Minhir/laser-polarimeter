%module GEM
%{
#include "GEM.h"
%}
%include "GEM.h"

%include "std_vector.i"

namespace std {
   %template(VectorDataHits) vector<hit_struct>;
}



