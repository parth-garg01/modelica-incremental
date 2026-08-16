model MslResistorNetwork
  "Second real-MSL-component model for Feature 7: a voltage divider with
   R1 in series from the source to node A, and R2/R3 in parallel from
   node A to ground. Real Modelica.Electrical.Analog.Basic/Sources
   components, connect()-wired. Index-1: no capacitor/inductor at all,
   so no reactive-only loop/cutset is even possible."
  Modelica.Electrical.Analog.Basic.Resistor R1(R=100)
    annotation (Placement(transformation(extent={{-60,20},{-40,40}})));
  Modelica.Electrical.Analog.Basic.Resistor R2(R=200)
    annotation (Placement(transformation(extent={{-10,20},{10,40}})));
  Modelica.Electrical.Analog.Basic.Resistor R3(R=300)
    annotation (Placement(transformation(extent={{-10,-20},{10,0}})));
  Modelica.Electrical.Analog.Basic.Ground G
    annotation (Placement(transformation(extent={{-10,-60},{10,-40}})));
  Modelica.Electrical.Analog.Sources.ConstantVoltage V(V=10)
    annotation (Placement(transformation(extent={{-100,-20},{-80,0}})));
equation
  connect(V.p, R1.n) annotation (Line(points={{-90,0},{-90,30},{-60,30}}, color={0,0,255}));
  connect(R1.p, R2.n) annotation (Line(points={{-40,30},{-10,30}}, color={0,0,255}));
  connect(R1.p, R3.n) annotation (Line(points={{-40,30},{-10,30},{-10,-10}}, color={0,0,255}));
  connect(R2.p, G.p) annotation (Line(points={{10,30},{20,30},{20,-40},{0,-40}}, color={0,0,255}));
  connect(R3.p, G.p) annotation (Line(points={{10,-10},{20,-10},{20,-40},{0,-40}}, color={0,0,255}));
  connect(V.n, G.p) annotation (Line(points={{-90,-20},{-90,-40},{0,-40}}, color={0,0,255}));
end MslResistorNetwork;
