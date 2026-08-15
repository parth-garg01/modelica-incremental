model DecoupledPair
  "Two independent first-order decays with no coupling between them.
   Ground truth: every recompilation unit should be a singleton."
  Real x1(start=1.0);
  Real x2(start=2.0);
  parameter Real k1 = 0.5;
  parameter Real k2 = 0.3;
equation
  der(x1) = -k1*x1;
  der(x2) = -k2*x2;
end DecoupledPair;
