model ThermalNetwork
  "Same as ThermalNetwork, with room 3 removed entirely: no T3, no Q23,
   no Q3env, and room 2 loses the Q23 term from its own derivative
   equation. This is the component-removal change."
  parameter Real Camb = 1.0;
  parameter Real C1 = 2.0;
  parameter Real C2 = 2.0;
  parameter Real C3 = 2.0;
  parameter Real Genv = 0.2;
  parameter Real G12 = 0.5;
  parameter Real Tamb = 15.0;
  parameter Real Qheater = 100.0;

  Real T1(start=15.0);
  Real T2(start=15.0);
  Real Q1, Q12, Q1env, Q2env;
equation
  Q1 = Qheater;
  Q1env = Genv*(T1 - Tamb);
  Q2env = Genv*(T2 - Tamb);
  Q12 = G12*(T1 - T2);

  C1*der(T1) = Q1 - Q1env - Q12;
  C2*der(T2) = Q12 - Q2env;
end ThermalNetwork;
