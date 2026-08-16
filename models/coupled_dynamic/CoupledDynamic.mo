model CoupledDynamic
  "A decaying state x feeding two mutually-coupled algebraic equations:
   y1 = 2*y2 + x, y2 = 3*y1 - 2*x. Still linear and hand-solvable at any
   instant (given x): y1 = 2*(3*y1-2*x) + x = 6*y1 - 3*x => -5*y1 = -3*x
   => y1 = 0.6*x, y2 = 3*(0.6*x) - 2*x = -0.2*x. Built because
   CoupledAlgebraic (this project's first coupled-block fixture) has
   ZERO states and zero time-dependence, which Rumoca's own simulate()
   cannot run at all ('did not converge at t=0') even though the
   structure is valid (Model.structure() confirms matched=true) --
   Feature 4 needs a coupled block whose ground truth CAN actually be
   run through Rumoca's simulator, not just checked by hand."
  Real x(start=1.0, fixed=true);
  Real y1, y2;
equation
  der(x) = -x;
  y1 = 2*y2 + x;
  y2 = 3*y1 - 2*x;
end CoupledDynamic;
