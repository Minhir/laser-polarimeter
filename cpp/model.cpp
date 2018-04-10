#include "model.h"
#include <chrono>

std::pair<float, float> get_model_hit()
{
    unsigned seed = std::chrono::system_clock::now().time_since_epoch().count();
    std::default_random_engine generator(seed);
    std::normal_distribution<float> x_distribution(80.0, 6.0);
    std::normal_distribution<float> y_distribution(16.0, 6.0);

    return std::pair<float, float>{x_distribution(generator), y_distribution(generator)};
}
