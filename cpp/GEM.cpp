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

    for (int l = cnt.ReadyEvents; l>0; --l)
    {
        memset(&evt, 0, sizeof(evt));
        GEM_getEventData(0, &evt);

        if (evt.channel_count!=0)
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

    for (int i = 0; i < size; ++i)
    {
        hit_vec.push_back(hit_struct{hits_online[i].X, hits_online[i].Y,
                                     hits_cog[i].Y, hits_cog[i].Y,
                                     timestamp_vec[i], polarity_vec[i]});
    }

    return hit_vec;
}

std::vector<hit_struct> debug_data()
{
    std::vector<hit_struct> hit_vec;
    hit_vec.reserve(1000);
    for (int i = 0; i < 1000; ++i)
    {
        auto hit_pair = get_model_hit();
        hit_vec.push_back(hit_struct{hit_pair.first, hit_pair.second + (i % 2) * 8,
                                     hit_pair.first, hit_pair.second + (i % 2) * 8,
                                     std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::system_clock::now().time_since_epoch()).count() / 1000000.,
                                     i % 2});
    }
    return std::move(hit_vec);
}


int main()
{
    /*init();
    while (true)
    {
        usleep(1000000);
        //GEM_reco_online();
        debug_data();
    }*/
    return 0;
}
