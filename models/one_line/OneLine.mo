model OneLine
  Real x(start=1.0);
equation
  der(x) = -x;
end OneLine;
