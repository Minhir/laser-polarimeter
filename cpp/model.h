#pragma once
#include <random>


std::pair<float, float> get_model_hit();

inline double polarization(double P0, double Pmax, double tau, double t)
{
  return P0 + (Pmax-P0)*(1.0 - exp(- t/tau));
}