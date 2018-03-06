#include "GEM_reco.h"
#include <algorithm>
#include <set>
#include <assert.h>
#include <memory.h>
#include <math.h>
#include <stdio.h>

static const char *ped_filenames[] = {
    "/home/lsrp/DEUTRON/gemd_monitor/ped.txt",
    "/home/lsrp/DEUTRON/gemd_monitor/ped.tx2"
};


// Det1 bad channels: 48,49,67,68,83,87,123,124,125,127,128,
// Det2 bad channels: 162,194,258,328,545,549,551,552,553,555,557,558,559,561,562,563,565,566,567,569,571,573,575,577,579,581,583,585,587,589,594,596,598,600,602,
// Det2 +454 hotspot

static bool ped_loaded = false;
static std::set<int> bad_channels[2];

#define VERBOSE if (0)

static int threshold = 120;

static void GEM_InitializeReco()
{
    ped_loaded = true;

//    bad_channels[1].insert(454);
    bad_channels[1].insert(1);
    bad_channels[1].insert(161);
    bad_channels[1].insert(163);
    bad_channels[1].insert(193);
    bad_channels[1].insert(195);
    bad_channels[1].insert(255);
    bad_channels[1].insert(257);
    bad_channels[1].insert(259);
    bad_channels[1].insert(383);
    bad_channels[1].insert(218);

    for (int k=0; k<2; ++k) {
        FILE* ped = fopen(ped_filenames[k], "r");
        VERBOSE printf("Det%d bad channels: ", k+1);
        for (int i=0; i<640; ++i) {
            int value = 0;
            fscanf(ped, "%d", &value);
            if (value==0) {
                bad_channels[k].insert(i);
                VERBOSE printf("%d,", i);
            }
        }
        VERBOSE printf("\n");
        fclose(ped);
    }

}

static float limit_xmin=0.0;
static float limit_xmax=160.0;

void GEM_setReconstructionRegionX(float xmin, float xmax) {
    limit_xmin=xmin;
    limit_xmax=xmax;
}

inline float channel_to_mm(int Xchannel) { return 160.0 - (Xchannel%320)*0.5; }

inline void guessDetectorNumber(GEM_Detector &det_number, struct GEM_Event*evt) {
    if ((evt->flags & 0x03)>0)
        det_number = (evt->flags & 0x03)-1;
    else if (det_number>0 && det_number<=3)
        det_number--;
    else
        det_number = -1; // Detector number is not recognized, bad channels wont be deleted.
}



struct GEM_Hit GEM_reconstructFirstOnline(GEM_Detector det_number, struct GEM_Event*evt)
{
    if (!ped_loaded)
        GEM_InitializeReco();

    GEM_Hit result;
    memset(&result, 0, sizeof(result));

    guessDetectorNumber(det_number, evt);

    GEM_Channel best_evn = { -3, 0 };
    GEM_Channel best_odd = { -3, 0 };
    for (int i=0; i<evt->channel_count; ++i) {
        GEM_Channel entry = evt->channels[i];
        int frame   = entry.number / 640;
        int channel = entry.number % 640;
        float Xchannel_mm = channel_to_mm(channel/2);

        if (det_number!=-1)
            if (bad_channels[det_number].count(channel)) {
                VERBOSE printf("skipping %d\n", channel);
                continue;
            }

        if (limit_xmin<=Xchannel_mm && Xchannel_mm<=limit_xmax) {
            if (channel%2==0) {
                if ((entry.value > best_evn.value))
                    best_evn = entry;
            } else {
                if ((entry.value > best_odd.value))
                    best_odd = entry;
            }
        }
    }


    result.Xchannel = best_evn.number/2;
    result.Ychannel = best_odd.number/2;
    result.Xamplitude = best_evn.value;
    result.Yamplitude = best_odd.value;

    if (result.Xchannel>=0 && result.Xamplitude>=threshold)
        result.X = 160.0 - (result.Xchannel%320)*0.5; // 0.5mm
    else
        result.X = NAN;

    if (result.Ychannel>=0 && result.Xchannel>=0 && result.Yamplitude>=threshold)
        result.Y = (result.Xchannel%320)-(result.Ychannel%320); // 1mm
    else
        result.Y = NAN;

    /*if (result.Xchannel<0 || result.Xamplitude<threshold) result.X = NAN;
    if (result.Ychannel<0 || result.Yamplitude<threshold) result.Y = NAN;*/

    return result;
}

GEM_Hit GEM_reconstructCoG(GEM_Detector det_number, struct GEM_Event*evt) {
    guessDetectorNumber(det_number, evt);
    
    double evn_sum=0;
    double odd_sum=0;
    double evn_value_sum=0;
    double odd_value_sum=0;
    
    for (int i=0; i<evt->channel_count; ++i) {
        GEM_Channel entry = evt->channels[i];
        int frame   = entry.number / 640;
        int channel = entry.number % 640;
        
        if (det_number!=-1)
            if (bad_channels[det_number].count(channel)) {
                VERBOSE printf("skipping %d\n", channel);
                continue;
            }
        
        if (channel%2==0) {
            if(entry.value>100)
            {
				evn_sum += (channel/2)*entry.value;
				evn_value_sum += entry.value;
			}
        } else {
            if(entry.value>100)
            {
				odd_sum += (channel/2)*entry.value;
				odd_value_sum += entry.value;
			}
        }
    }
    
    if( odd_value_sum > 0 && odd_value_sum > 0)
    {
		GEM_Hit ghit;
		ghit.X = 160-0.5*evn_sum/evn_value_sum;
		ghit.Xcharge = evn_value_sum;
		ghit.Y = evn_sum/evn_value_sum - odd_sum/odd_value_sum;
		ghit.Ycharge = odd_value_sum;
		return ghit;
	}
	else
	{
        return GEM_Hit();
	}
}

