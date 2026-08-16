model CoupledAlgebraic
  "Two mutually-dependent algebraic equations forming a genuine 2x2 coupled
   BLT block, hand-solvable: y1 = 2*y2 + 1, y2 = 3*y1 - 2
   => y1 = 6*y1 - 3 => y1 = 0.6, y2 = 3*0.6 - 2 = -0.2.
   Built specifically to exercise a non-singleton block: none of the other
   fixtures (OneLine/DecoupledPair/RLCCircuit/ThermalNetwork/Chain) have one
   after causalization -- every equation there is independently solvable,
   which is exactly why Feature 2 needs a case that genuinely is not."
  Real y1, y2;
equation
  y1 = 2*y2 + 1;
  y2 = 3*y1 - 2;
end CoupledAlgebraic;
