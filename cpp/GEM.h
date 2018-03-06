#pragma once
#include <vector>
#include "model.h"


struct hit_struct
{
    float x_online;
    float y_online;
    float x_cog;
    float y_cog;
    double timestamp;
    int polarity;
};


void init();

std::vector<hit_struct> GEM_reco();

std::vector<hit_struct> debug_data();
