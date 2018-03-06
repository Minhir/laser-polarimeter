/*****
Порядок работы:
* GEM_initialize         = инициализация библиотеки
* GEM_configureDetectors = конфигурация детекторов (настройка регистров/режима работы, установка пъедесталов и порогов)
* GEM_startOfRun         = начало захода (разрешение триггера, запуск  сборщика пакетов, сброс статистики)
* GEM_endOfRun           = конец  захода (блокировка триггера, останов сборщика пакетов)
* GEM_getDebugInfo       = выдача отладочной информации, стастистики
* GEM_finalize           = деинициализация библиотеки перед выходом из программы

Выдача данных для event-builder
* GEM_getDetectorCount   = количество детекторов
* GEM_getEventCount      = количество событий в очереди детектора
* GEM_getEventData       = выдать первое событие в очереди для детектора
* GEM_getLastStatus      = статус последней команды 
*****/

#ifndef _GEM_READOUT_H_
#define _GEM_READOUT_H_
#ifdef __cplusplus
  extern "C" {
#else
  #include <stdbool.h>
#endif

#include <stdint.h>

void GEM_initialize();
void GEM_initializeReadOnly();
void GEM_configureDetectors();
void GEM_startOfRun();
void GEM_endOfRun();
const char* GEM_getDebugInfo();
void GEM_finalize();

struct GEM_Status {
    bool ok;
    const char* error_msg;
};

struct GEM_Status GEM_getLastStatus();

typedef int GEM_Detector;

struct GEM_EventCount {
    int ReadyEvents;
    int Pending;
};

struct GEM_Channel {
    int32_t number; /* encoded frame and position */
    int32_t value;  /* channel value with pedestal substracted */
};

#define GEM_MAX_CHANNEL_COUNT 256

struct GEM_Event {
    double timestamp;

    uint32_t number;
    uint32_t flags;
    uint32_t debug;
    int32_t  jitter;
    int32_t  hv;
    uint32_t channel_count;
    struct GEM_Channel channels[GEM_MAX_CHANNEL_COUNT]; /* should be of channel_count size */
    
    #ifdef __cplusplus
    inline unsigned detector_number() const { return (flags & 0x0003);    } // valid values 1,2,3
    inline unsigned cell_pointer()    const { return (debug & 0x001f);    } // pipeline cell number at the trigger
    inline unsigned period_jitter()   const { return (debug & 0xffe0)>>5; } // delay between busy unlock and trigger
    inline unsigned trigger_count()   const { return (debug >> 16);       }
    #endif
};


int  GEM_getDetectorCount();
struct GEM_EventCount GEM_getEventCount(GEM_Detector);
void GEM_getEventData(GEM_Detector, struct GEM_Event*);
void GEM_readDetectorDirectly(GEM_Detector, struct GEM_Event*);
void GEM_setDiscardEmptyEvents(bool discard);

#ifdef __cplusplus
}
#endif
#endif /* _GEM_READOUT_H_ */