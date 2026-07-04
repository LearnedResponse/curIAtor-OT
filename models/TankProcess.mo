package CurIAtorTank
  model TankProcess
    parameter Real area = 38.0 "Effective tank area";
    parameter Real nominalLevel = 55.0 "Normal operating level percent";
    parameter Real valveGain = 0.86 "Inlet flow gain";
    parameter Real baseInlet = 11.5 "Base inlet flow";
    parameter Real baseOutlet = 45.0 "Base outlet flow";
    parameter Real outletLevelGain = 0.18 "Gravity/drain contribution";
    parameter Real ambientTemperature = 72.0 "Nominal ambient temperature F";

    input Real valvePct(min = 0.0, max = 100.0) = 50.0;
    input Real inletBias = 0.0;
    input Real outletBias = 0.0;
    input Real heatLoad = 0.0;
    input Real setpoint = nominalLevel;

    Real level(start = 52.0, min = 0.0, max = 95.0);
    Real temperature(start = 74.0);
    Real inletFlow;
    Real outletFlow;
    Real levelError;
    Real cavitationMargin;
    Real controlMargin;

  equation
    inletFlow = max(0.0, baseInlet + valveGain * valvePct + inletBias);
    outletFlow = max(0.0, baseOutlet + outletLevelGain * sqrt(max(level, 0.0)) + outletBias);
    der(level) = (inletFlow - outletFlow) / area;
    der(temperature) = ((ambientTemperature + heatLoad) - temperature) / 180.0;
    levelError = setpoint - level;
    cavitationMargin = 18.0 - max(0.0, outletFlow - 48.0) * 0.45 - max(0.0, temperature - 80.0) * 0.3;
    controlMargin = min(valvePct, 100.0 - valvePct);
  end TankProcess;
end CurIAtorTank;
