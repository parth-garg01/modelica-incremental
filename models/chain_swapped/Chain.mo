model Chain
  "Same as Chain, with the ROOT equation (y1) changed: y1 = p1 -> y1 = p1*2.0.
   Under forward-reachability from y1, this predicts y2 and der(x) as
   affected too, even though neither y2's nor der(x)'s own C source
   changes -- the near-full-ripple edge case for Feature C2."
  parameter Real p1 = 2.0;
  parameter Real p2 = 3.0;
  Real y1, y2;
  Real x(start=0.0);
equation
  y1 = p1*2.0;
  y2 = y1 + p2;
  der(x) = y2;
end Chain;
