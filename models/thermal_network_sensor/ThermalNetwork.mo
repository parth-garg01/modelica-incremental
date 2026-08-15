model ThermalNetwork
  "Same as ThermalNetwork, with a new sensor added: Qtotal, summing the
   three room-to-ambient heat losses. This is the sensor-add change."
  parameter Real Camb = 1.0;
  parameter Real C1 = 2.0;
  parameter Real C2 = 2.0;
  parameter Real C3 = 2.0;
  parameter Real Genv = 0.2;
  parameter Real G12 = 0.5;
  parameter Real G23 = 0.5;
  parameter Real Tamb = 15.0;
  parameter Real Qheater = 100.0;

  Real T1(start=15.0);
  Real T2(start=15.0);
  Real T3(start=15.0);
  Real Q1, Q12, Q23, Q1env, Q2env, Q3env;
  Real Qtotal;
equation
  Q1 = Qheater;
  Q1env = Genv*(T1 - Tamb);
  Q2env = Genv*(T2 - Tamb);
  Q3env = Genv*(T3 - Tamb);
  Q12 = G12*(T1 - T2);
  Q23 = G23*(T2 - T3);
  Qtotal = Q1env + Q2env + Q3env;

  C1*der(T1) = Q1 - Q1env - Q12;
  C2*der(T2) = Q12 - Q2env - Q23;
  C3*der(T3) = Q23 - Q3env;
end ThermalNetwork;
