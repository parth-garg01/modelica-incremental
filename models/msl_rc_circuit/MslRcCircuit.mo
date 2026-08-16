model MslRcCircuit
  "Feature 5 flagship: a real MSL series RC circuit (constant voltage
   source, resistor, capacitor, ground), using genuine
   Modelica.Electrical.Analog components wired with connect() -- so it
   exercises real anonymous KCL/KVL residual equations, same generality
   gap Feature 1 was built to close -- but with a single capacitor, so a
   capacitor-only loop (the index-reduction cause found in the Cauer
   filter, see docs/findings/cauer-index-reduction.md) is not even
   topologically possible. Index-1, matched=true expected."
  Modelica.Electrical.Analog.Basic.Resistor R(R=100)
    annotation (Placement(transformation(extent={{-40,20},{-20,40}})));
  Modelica.Electrical.Analog.Basic.Capacitor C(C=0.01, v(start=0, fixed=true))
    annotation (Placement(transformation(extent={{0,-20},{20,0}})));
  Modelica.Electrical.Analog.Basic.Ground G
    annotation (Placement(transformation(extent={{-10,-60},{10,-40}})));
  Modelica.Electrical.Analog.Sources.ConstantVoltage V(V=5)
    annotation (Placement(transformation(extent={{-80,-20},{-60,0}})));
equation
  connect(V.p, R.n) annotation (Line(points={{-70,0},{-70,30},{-40,30}}, color={0,0,255}));
  connect(R.p, C.p) annotation (Line(points={{-20,30},{10,30},{10,0}}, color={0,0,255}));
  connect(C.n, G.p) annotation (Line(points={{10,-20},{10,-40},{0,-40}}, color={0,0,255}));
  connect(V.n, G.p) annotation (Line(points={{-70,-20},{-70,-40},{0,-40}}, color={0,0,255}));
end MslRcCircuit;
