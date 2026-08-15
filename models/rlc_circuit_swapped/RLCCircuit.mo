model RLCCircuit
  "Series RLC circuit driven by a sinusoidal source.
   Inductor current i and capacitor voltage v are mutually coupled through
   the loop equation, so they should land in the same recompilation unit."
  Real i(start=0.0);
  Real v(start=0.0);
  parameter Real R = 1.0;
  parameter Real L = 0.5;
  parameter Real C = 0.1;
  parameter Real Vamp = 1.0;
  parameter Real omega = 2.0;
  parameter Real alpha = 0.1;
  Real Vs;
equation
  Vs = Vamp*sin(omega*time);
  L*der(i) = Vs - R*i - alpha*i^3 - v;
  C*der(v) = i;
end RLCCircuit;
