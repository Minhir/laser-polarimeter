#include "GEM_readout.h"
#ifndef _GEM_RECO_H_
#define _GEM_RECO_H_
#ifdef __cplusplus
  extern "C" {
#endif
    

struct GEM_Hit {
    float X;
    float Y;
    
    float Xamplitude;
    float Yamplitude;
    
    float Xcharge;
    float Ycharge;
    
    int Xchannel;
    int Ychannel;
};

/* int frame   = Xchannel /320; // should be in range [3..4] for timed events.
 * int channel = Xchannel %320;
 */

/*struct GEM_HitEx {
    float X;
    float Y;
    
    GEM_Channel evn;
    GEM_Channel odd;
    
    struct GEM_Cluster {
        float charge;
        float position;
        float frame;
        float width;
        float length
    } evnCluster, oddCluster;
    
    float Xcharge;
    float Ycharge;
};*/

struct GEM_Hit   GEM_reconstructFirstOnline(GEM_Detector det_number, struct GEM_Event*evt);
struct GEM_Hit   GEM_reconstructFirst(GEM_Detector det_number, struct GEM_Event*evt);
struct GEM_Hit   GEM_reconstructCoG(GEM_Detector det_number, struct GEM_Event*evt);
struct GEM_Hit** GEM_reconstructPack (GEM_Detector det_number, struct GEM_Event*evt);
void             GEM_setReconstructionRegionX(float xmin, float xmax);

/* Detector number from event->flags has 1st priority, after that it is looked at GEM_Detector number.
 * number=1 corresponds to 1st detector (as in event->flags & 0x0003).
 */

#ifdef __cplusplus
}
#endif
#endif/* _GEM_RECO_H_ */
