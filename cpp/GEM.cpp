#include <vector>
#include <iostream>
#include <cstring>
#include <unistd.h>
#include <chrono>

#include "GEM.h"
#include "GEM_readout.h"
#include "GEM_reco.h"

void init()
{
    GEM_initializeReadOnly();
    GEM_setDiscardEmptyEvents(true);
    GEM_startOfRun();
}

void setReconstructionRegionX(float xmin, float xmax)
{
    GEM_setReconstructionRegionX(xmin, xmax);
}

std::vector<hit_struct> GEM_reco()
{
    struct GEM_EventCount cnt;
    struct GEM_Event evt;
    cnt = GEM_getEventCount(0);

    std::vector<GEM_Hit> hits_online;
    std::vector<GEM_Hit> hits_cog;
    std::vector<int> polarity_vec;
    std::vector<double> timestamp_vec;

    hits_online.reserve(cnt.ReadyEvents);
    hits_cog.reserve(cnt.ReadyEvents);
    polarity_vec.reserve(cnt.ReadyEvents);
    timestamp_vec.reserve(cnt.ReadyEvents);

    for (int l = cnt.ReadyEvents; l > 0; --l)
    {
        memset(&evt, 0, sizeof(evt));
        GEM_getEventData(0, &evt);

        if (evt.channel_count != 0)
        {
            hits_online.push_back(GEM_reconstructFirstOnline(0, &evt));
            hits_cog.push_back(GEM_reconstructCoG(0, &evt));
            polarity_vec.push_back((evt.flags & 0x8000)>>15);
            timestamp_vec.push_back(evt.timestamp);
        }
    }

    int size = hits_online.size();
    std::vector<hit_struct> hit_vec;
    hit_vec.reserve(size);

    for (int i = 0; i < size; ++i)  // TODO: усреднение по 0.1 сек
    {
        if (std::isfinite(hits_online[i].X) && std::isfinite(hits_online[i].Y) &&
            std::isfinite(hits_cog[i].Y) && std::isfinite(hits_cog[i].Y))
        {
            hit_vec.push_back(hit_struct{hits_online[i].X, hits_online[i].Y,
                                         hits_cog[i].X, hits_cog[i].Y,
                                         hits_cog[i].Xcharge + hits_cog[i].Ycharge,
                                         timestamp_vec[i], polarity_vec[i]});
        }
    }

    return hit_vec;
}

double start_time = 0;

void depolarize()
{
    start_time = 0;
}


std::vector<hit_struct> debug_data()
{
    std::vector<hit_struct> hit_vec;
    int points_amount = 800;

    double sec_ = std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::system_clock::now().time_since_epoch()).count() / 1000000. - 1;

    static std::default_random_engine generator(sec_);
    std::normal_distribution<float> x_distribution(-50.0, 50.0);
    points_amount += x_distribution(generator);

    hit_vec.reserve(points_amount);
    if (start_time == 0) start_time = sec_;
    for (int i = 0; i < points_amount; ++i)
    {
        auto hit_pair = get_model_hit();
        hit_vec.push_back(hit_struct{hit_pair.first + x_distribution(generator) / 500,
                                     hit_pair.second + (i % 2) * (float)polarization(0, 10, 15, sec_ - start_time),
                                     hit_pair.first + x_distribution(generator) / 500,
                                     hit_pair.second + (i % 2) * (float)polarization(0, 10, 15, sec_ - start_time) * 1.1f,
                                     1.f,
                                     sec_,
                                     i % 2});
        sec_ += 1. / points_amount;
    }
    return std::move(hit_vec);
}
