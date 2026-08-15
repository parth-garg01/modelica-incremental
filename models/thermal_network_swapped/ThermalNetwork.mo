model ThermalNetwork
  "Same as ThermalNetwork, with room 1's constant-power heater swapped for
   a proportional thermostat: Q1 = Kp*(Tset - T1) instead of Q1 = Qheater.
   This is the post-change model used to measure ripple."
  parameter Real Camb = 1.0;
  parameter Real C1 = 2.0;
  parameter Real C2 = 2.0;
  parameter Real C3 = 2.0;
  parameter Real Genv = 0.2;
  parameter Real G12 = 0.5;
  parameter Real G23 = 0.5;
  parameter Real Tamb = 15.0;
  parameter Real Kp = 20.0;
  parameter Real Tset = 22.0;

  Real T1(start=15.0);
  Real T2(start=15.0);
  Real T3(start=15.0);
  Real Q1, Q12, Q23, Q1env, Q2env, Q3env;
equation
  Q1 = Kp*(Tset - T1);
  Q1env = Genv*(T1 - Tamb);
  Q2env = Genv*(T2 - Tamb);
  Q3env = Genv*(T3 - Tamb);
  Q12 = G12*(T1 - T2);
  Q23 = G23*(T2 - T3);

  C1*der(T1) = Q1 - Q1env - Q12;
  C2*der(T2) = Q12 - Q2env - Q23;
  C3*der(T3) = Q23 - Q3env;
end ThermalNetwork;
