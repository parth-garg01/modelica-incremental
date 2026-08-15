model Chain
  "Synthetic edge-case fixture for Feature C2: a linear forward-dependency
   chain (y1 -> y2 -> der(x)), with no feedback and no genuine algebraic
   loop, but where a change to the ROOT equation (y1) ripples through
   every downstream equation under forward-reachability -- exercising the
   'a change touches most of the model, even after the granularity fix'
   edge case honestly, without fabricating coupling that isn't there."
  parameter Real p1 = 2.0;
  parameter Real p2 = 3.0;
  Real y1, y2;
  Real x(start=0.0);
equation
  y1 = p1;
  y2 = y1 + p2;
  der(x) = y2;
end Chain;
