model MslThermalChain
  "Priority 3 (broadening the real-model corpus beyond electrical
   circuits): a real MSL thermal network -- Modelica.Thermal.HeatTransfer
   FixedTemperature source, two ThermalConductor links, two HeatCapacitor
   bodies in series, using genuine connect()-wired components, same
   generality gap Feature 1/Feature 5 closed for the electrical domain,
   now shown for a second, physically different domain. Index-1 by
   construction: no purely-reactive (capacitor-only) loop is even
   topologically possible in a chain topology, the same argument that
   makes MslRcCircuit safe -- see docs/findings/cauer-index-reduction.md
   for the loop pattern this deliberately avoids."
  Modelica.Thermal.HeatTransfer.Sources.FixedTemperature Tsource(T=350)
    annotation (Placement(transformation(extent={{-80,-10},{-60,10}})));
  Modelica.Thermal.HeatTransfer.Components.ThermalResistor G1(R=2)
    annotation (Placement(transformation(extent={{-40,-10},{-20,10}})));
  Modelica.Thermal.HeatTransfer.Components.HeatCapacitor C1(C=2, T(start=293.15, fixed=true))
    annotation (Placement(transformation(extent={{-10,-10},{10,10}})));
  Modelica.Thermal.HeatTransfer.Components.ThermalConductor G2(G=0.3)
    annotation (Placement(transformation(extent={{20,-10},{40,10}})));
  Modelica.Thermal.HeatTransfer.Components.HeatCapacitor C2(C=1.5, T(start=293.15, fixed=true))
    annotation (Placement(transformation(extent={{60,-10},{80,10}})));
equation
  connect(Tsource.port, G1.port_a) annotation (Line(points={{-60,0},{-40,0}}, color={191,0,0}));
  connect(G1.port_b, C1.port) annotation (Line(points={{-20,0},{0,0}}, color={191,0,0}));
  connect(C1.port, G2.port_a) annotation (Line(points={{0,0},{20,0}}, color={191,0,0}));
  connect(G2.port_b, C2.port) annotation (Line(points={{40,0},{60,0}}, color={191,0,0}));
end MslThermalChain;
