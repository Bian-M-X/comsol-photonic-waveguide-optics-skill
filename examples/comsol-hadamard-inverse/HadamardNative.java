import com.comsol.model.*;
import com.comsol.model.util.ModelUtil;
import java.util.*;

/** Original COMSOL 6.4 adjoint example. A 2D material-index surrogate, not a 220 nm SOI EIM. */
public class HadamardNative {
  static final String C="comp1", G="geom1", P="ewfd";
  static final double HALF=.65;
  static double XMAX=3.15, YMAX=3.15, WINDOW=1.5;
  static String cwd;
  static String restart="__RESTART_MODEL__";
  static final String TARGET="(comp1.ewfd.S31-i*comp1.ewfd.S41)";
  static final String ERROR="(comp1.ewfd.S31+i*comp1.ewfd.S41)";
  // eta - gate_weight * orthogonal power for input 1; fixes phase as well as power.
  static final String COHERENT_OBJECTIVE="(realdot("+TARGET+","+TARGET+")-(gate_weight-1)*realdot("+ERROR+","+ERROR+"))/2";
  // Under the imposed mirror T=[[a,b],[b,a]], its minimum state throughput is
  // eta-2*abs(real(conj(a)*b)). The smoothed absolute value is conservative.
  static final String STATE_FLOOR_OBJECTIVE=COHERENT_OBJECTIVE+"-sqrt(4*realdot(comp1.ewfd.S31,comp1.ewfd.S41)^2+1e-8)";
  static String OBJECTIVE=COHERENT_OBJECTIVE;
  static Properties cfg=new Properties();
  static boolean pml() { return cfg.getProperty("boundary_model","exterior_modal").equals("slit_pml"); }
  static String profileObjective(String expression) {
    return pml()?expression.replace("comp1.ewfd.S31","comp1.modal_a3").replace("comp1.ewfd.S41","comp1.modal_a4"):expression;
  }
  static double number(String k,double d) { return Double.parseDouble(cfg.getProperty(k,""+d)); }
  static void require(boolean b,String s) { if(!b) throw new IllegalStateException(s); }
  static String dom(String s) { return "geom1_"+s+"_dom"; }
  static String sel(String s) { return "geom1_"+s; }
  static String unusedSolution(Model m,String prefix) {
    Set<String> names=new HashSet<String>(Arrays.asList(m.sol().tags()));
    int i=1;while(names.contains(prefix+i))i++;return prefix+i;
  }
  static void ensureFlux(Model m) {
    Set<String> tags=new HashSet<String>(Arrays.asList(m.component(C).cpl().tags()));
    for(String surface:new String[]{"p1","p2","p3","p4","open"}) {
      if(!tags.contains("flux_"+surface))m.component(C).cpl().create("flux_"+surface,"Integration");
      m.component(C).cpl("flux_"+surface).selection().geom(G,1);
      m.component(C).cpl("flux_"+surface).selection().named(sel(pml()?"flux_"+surface:surface));
    }
  }
  static void verifyExterior(Model m) {
    if(pml()) {
      Set<Integer> expected=new HashSet<Integer>(),used=new HashSet<Integer>();
      // Geometry-derived boundary of the independent source-free control volume.
      if(!Arrays.asList(m.component(C).selection().tags()).contains("fluxVolumeBoundary"))
        m.component(C).selection().create("fluxVolumeBoundary","Adjacent");
      m.component(C).selection("fluxVolumeBoundary").set("entitydim",2);
      m.component(C).selection("fluxVolumeBoundary").set("outputdim",1);
      m.component(C).selection("fluxVolumeBoundary").set("input",new String[]{dom("fluxvol")});
      m.component(C).selection("fluxVolumeBoundary").set("interior",false);
      m.component(C).selection("fluxVolumeBoundary").set("exterior",true);
      for(int id:m.component(C).selection("fluxVolumeBoundary").entities(1))expected.add(id);
      for(String surface:new String[]{"p1","p2","p3","p4","open"}) {
        int[] ids=m.component(C).selection(sel("flux_"+surface)).entities(1);
        require(ids.length>0,"Empty flux contour segment: "+surface);
        for(int id:ids)require(used.add(id),"Overlapping flux contour at "+id);
        System.out.println("FLUX_BOUNDARIES_"+surface+"="+Arrays.toString(ids));
      }
      require(expected.size()>0&&used.equals(expected),"Closed control-volume boundary partition mismatch");
      System.out.println("INTERIOR_FLUX_PARTITION_VERIFIED=true");
      System.out.println("RADIATION_TERMINATION=domain_backed_slit_ports,Cartesian_PML");
      return;
    }
    if(!Arrays.asList(m.component(C).selection().tags()).contains("exteriorAudit"))
      m.component(C).selection().create("exteriorAudit","Explicit");
    m.component(C).selection("exteriorAudit").geom(G,2,1,new String[]{"exterior"});
    m.component(C).selection("exteriorAudit").all();
    Set<Integer> exterior=new HashSet<Integer>(), used=new HashSet<Integer>();
    for(int id:m.component(C).selection("exteriorAudit").entities(1))exterior.add(id);
    require(exterior.size()>0,"Empty finalized exterior");
    for(String tag:new String[]{"p1","p2","p3","p4","open"}) {
      int[] ids=m.component(C).selection(sel(tag)).entities(1);
      require(ids.length>0,"Empty boundary selection: "+tag);
      for(int id:ids) require(used.add(id),"Overlapping exterior partition at boundary "+id);
      System.out.println("BOUNDARIES_"+tag+"="+Arrays.toString(ids));
    }
    require(used.equals(exterior),"Port/open selections do not equal the entire finalized exterior");
    System.out.println("EXTERIOR_BOUNDARY_PARTITION_VERIFIED=true");
  }
  static void removeValidation(Model m) {
    for(String s:m.sol().tags()) if(!s.equals("sol1")&&m.sol(s).feature().tags().length>0) {
      for(String d:m.result().dataset().tags()) if("Solution".equals(m.result().dataset(d).getType())&&s.equals(m.result().dataset(d).getString("solution"))) m.result().dataset().remove(d);
      m.sol().remove(s);
    }
    for(String s:m.study().tags()) if(!s.equals("std1"))m.study().remove(s);
  }
  static void verifyRestartGeometry(Model m) {
    double actualOuter=m.param().evaluate("outer_half")*1e6;
    double actualWindow=m.param().evaluate("port_half")*1e6;
    require(Math.abs(actualOuter-XMAX)<1e-12,"Restart outer domain mismatch");
    require(Math.abs(actualWindow-WINDOW)<1e-12,"Restart port window mismatch");
    int ports=0;
    for(String tag:m.component(C).physics(P).feature().tags())if("Port".equals(m.component(C).physics(P).feature(tag).getType()))ports++;
    require(ports==4*(int)number("guided_modes",1),"Restart guided-mode termination mismatch");
    require(m.component(C).physics(P).feature("port1").getBoolean("PortSlit")==pml(),"Restart boundary model mismatch");
    if(pml()) {
      require(Math.abs(m.param().evaluate("pml_thickness")-number("pml_thickness_um",.8)*1e-6)<1e-15,"Restart PML thickness mismatch");
      require(Math.abs(m.param().evaluate("pml_scale")-number("pml_scale",1))<1e-12,"Restart PML scaling mismatch");
      require(Math.abs(m.param().evaluate("pml_curvature")-number("pml_curvature",3))<1e-12,"Restart PML curvature mismatch");
      require(Math.abs(m.param().evaluate("projection_offset")-number("projection_offset_um",.2)*1e-6)<1e-15,"Restart projection reference mismatch");
    }
  }
  static void verifyPML(Model m) {
    if(!pml())return;
    require("Cartesian".equals(m.component(C).coordSystem("pml1").getString("ScalingType")),"PML geometry type mismatch");
    require("polynomial".equals(m.component(C).coordSystem("pml1").getString("stretchingType")),"PML stretching mismatch");
    require("userDefined".equals(m.component(C).coordSystem("pml1").getString("wavelengthSourceType")),"PML wavelength must be spatially uniform");
    require("c_const/freq/sqrt(eps_clad)".equals(m.component(C).coordSystem("pml1").getString("typicalWavelength")),"PML wavelength expression mismatch");
    require("pml_scale".equals(m.component(C).coordSystem("pml1").getString("PMLfactor"))&&"pml_curvature".equals(m.component(C).coordSystem("pml1").getString("PMLgamma")),"PML scaling readback failed");
    Set<Integer> exterior=new HashSet<Integer>(),terminated=new HashSet<Integer>();
    for(int id:m.component(C).selection("outerTermination").entities(1))exterior.add(id);
    for(int id:m.component(C).physics(P).feature("outerPEC").selection().entities(1))terminated.add(id);
    require(exterior.size()>0&&exterior.equals(terminated),"Outermost PML termination partition mismatch");
    require(m.component(C).coordSystem("pml1").selection().entities(2).length>0,"Empty PML domain selection");
    require(Arrays.equals(m.component(C).coordSystem("pml1").selection().entities(2),m.component(C).selection(dom("pml")).entities(2)),"PML domain selection mismatch");
    System.out.println("PML_CONFIGURATION_VERIFIED=true");
    for(int i=1;i<=4*(int)number("guided_modes",1);i++) {
      String tag="port"+i;int physical=(i-1)%4+1;
      require(m.component(C).physics(P).feature(tag).getBoolean("PortSlit")&&"DomainBacked".equals(m.component(C).physics(P).feature(tag).getString("SlitType")),"Port is not transparent domain-backed slit: "+tag);
      require((physical<=2?"ForwardPort":"ReversePort").equals(m.component(C).physics(P).feature(tag).getString("PortOrientation")),"Slit orientation mismatch: "+tag);
      require((""+i).equals(m.component(C).physics(P).feature(tag).getString("PortName")),"Slit channel name mismatch");
      int[] ids=m.component(C).physics(P).feature(tag).selection().entities(1);
      require(ids.length>0,"Empty slit selection");
      for(int id:ids)require(!exterior.contains(id),"Slit port placed on exterior boundary");
    }
    System.out.println("SLIT_PORTS_VERIFIED=true");
  }
  static void configureOptimizer(SolverFeature optimizer) {
    optimizer.set("optmethod",cfg.getProperty("optimizer","mma"));
    optimizer.set("gradientmma","adjoint");
    optimizer.set("mmaminmax","on");optimizer.set("mmamaxiteractive","on");
    optimizer.set("movelimitactive","on");optimizer.set("movelimit",number("move_limit",.05));
    optimizer.set("nsolvemax",(int)number("evaluation_limit",1000));
  }
  static void verifyOptimizerControls(Model m) {
    SolverFeature optimizer=m.sol("sol1").feature("o1");
    String method=cfg.getProperty("optimizer","mma");
    double move=number("move_limit",.05);int evaluations=(int)number("evaluation_limit",1000);
    require(method.equals(optimizer.getString("optmethod")),"Optimizer method readback failed");
    require("adjoint".equals(optimizer.getString("gradientmma")),"Optimizer gradient readback failed");
    require("on".equals(optimizer.getString("mmamaxiteractive")),"Optimizer iteration limit disabled");
    require("on".equals(optimizer.getString("movelimitactive"))&&Math.abs(optimizer.getDouble("movelimit")-move)<1e-12,"Optimizer move limit readback failed");
    require(optimizer.getInt("nsolvemax")==evaluations,"Optimizer evaluation limit readback failed");
    System.out.println("OPTIMIZER_CONTROLS_VERIFIED="+method+","+move+","+evaluations);
  }
  static void verifyOptimization(Model m) {
    String aggregation=cfg.getProperty("training_band","single").equals("single")?"auto":"min";
    String[][] studyObjective=m.study("std1").feature("topo").getStringMatrix("optobj");
    System.out.println("STUDY_OBJECTIVE_READBACK="+Arrays.deepToString(studyObjective));
    require(studyObjective.length==1&&studyObjective[0][0].equals(OBJECTIVE),"Checkpoint study objective mismatch");
    require(aggregation.equals(m.study("std1").feature("topo").getString("objectivesolution")),"Checkpoint study aggregation mismatch");
    // In generated COMSOL 6.4 solvers this is a scalar reference to the study
    // contribution, not the editable StringArray documented for manual objectives.
    SolverFeature optimizer=m.sol("sol1").feature("o1");
    String solverObjective=optimizer.getString("optobj");
    System.out.println("SOLVER_OBJECTIVE_READBACK="+solverObjective);
    require("all_obj_contrib".equals(solverObjective)&&"all".equals(optimizer.getString("objcontrib"))&&"topo".equals(optimizer.getString("control")),"Generated optimizer is not controlled by the verified study objective");
    require(aggregation.equals(m.sol("sol1").feature("o1").getString("objectivesolution")),"Generated optimization aggregation mismatch");
    require("on".equals(optimizer.getString("mmaminmax")),"MMA minimax-to-constraints transformation disabled");
    require("maximization".equals(m.study("std1").feature("topo").getString("objectivetype")),"Optimization direction mismatch");
    System.out.println("OPTIMIZATION_OBJECTIVE_VERIFIED="+aggregation+","+OBJECTIVE);
  }
  static Model resume() throws Exception {
    Model m=ModelUtil.load("Hadamard",restart);m.modelPath(cwd);
    require(m.component(C).geom(G).getSDim()==2,"Restart requires this 2D fixture");
    verifyRestartGeometry(m);
    require(m.component(C).common("cvf1").getString("name").equals("theta_c"),"Restart control field mismatch");
    boolean reconfigure=Boolean.parseBoolean(cfg.getProperty("reconfigure_restart","false"));
    if(!reconfigure) verifyOptimization(m);
    else {
      String oldObjective=m.study("std1").feature("topo").getStringMatrix("optobj")[0][0];
      require(oldObjective.equals(profileObjective(COHERENT_OBJECTIVE))||oldObjective.equals(profileObjective(STATE_FLOOR_OBJECTIVE)),"Unrecognized checkpoint objective");
      require("maximization".equals(m.study("std1").feature("topo").getString("objectivetype")),"Checkpoint objective direction mismatch");
      System.out.println("RECONFIGURED_RESTART_OLD_OBJECTIVE="+oldObjective);
      System.out.println("RECONFIGURED_RESTART_OLD_FREQUENCIES="+m.study("std1").feature("freq").getString("plist"));
    }
    String seed=unusedSolution(m,"restartSeed");m.sol("sol1").copySolution(seed);
    removeValidation(m);
    ensureFlux(m);
    verifyExterior(m);
    verifyPML(m);
    m.component(C).common("cvf1").set("initialValue","withsol('"+seed+"',comp1.theta_c)");
    m.param().set("beta",""+number("beta",2));
    m.param().set("gate_weight",""+number("fidelity_weight",1));
    m.param().set("meshsize",number("mesh_um",.045)+"[um]");
    m.component(C).mesh("mesh1").feature("bgsize").set("hmax",number("cladding_mesh_um",.22)+"[um]");
    if(!reconfigure) require(m.study("std1").feature("freq").getString("plist").equals(trainingFrequencies()),"Restart training-frequency set mismatch");
    // Material, frequency and physical filter length must stay fixed for a restart.
    require(Math.abs(m.param().evaluate("lambda0")-number("wavelength_nm",1550)*1e-9)<1e-15,"Restart wavelength mismatch");
    require(Math.abs(m.param().evaluate("rf")-number("rf_um",.05)*1e-6)<1e-15,"Restart filter mismatch");
    require(Math.abs(m.param().evaluate("eps_core")-number("eps_core",12.1))<1e-12,"Restart core material mismatch");
    require(Math.abs(m.param().evaluate("eps_clad")-number("eps_clad",2.1))<1e-12,"Restart cladding material mismatch");
    if(reconfigure) {
      // Reuse only the saved control field, not the old electromagnetic state,
      // frequency list or generated optimization solver.
      for(String d:m.result().dataset().tags())
        if("Solution".equals(m.result().dataset(d).getType())&&"sol1".equals(m.result().dataset(d).getString("solution")))m.result().dataset().remove(d);
      m.sol().remove("sol1");
      m.study("std1").feature("freq").set("plist",trainingFrequencies());
      m.study("std1").feature("topo").set("optobj",new String[]{OBJECTIVE});
      m.study("std1").feature("topo").set("objectivesolution",cfg.getProperty("training_band","single").equals("single")?"auto":"min");
      m.study("std1").feature("topo").set("mmamaxiter",(int)number("iterations",3));
      for(int mode=0;mode<(int)number("guided_modes",1);mode++) {
        m.component(C).variable("portdispersion").set("nmode"+mode,dispersionExpression(0,mode==1));
        m.component(C).variable("portdispersion").set("hmode"+mode,dispersionExpression(1,mode==1));
        m.component(C).variable("portdispersion").set("qmode"+mode,dispersionExpression(2,mode==1));
      }
      m.study("std1").createAutoSequences("sol");
      require(Arrays.asList(m.sol().tags()).contains("sol1"),"Regenerated active solver missing");
      for(String f:m.sol("sol1").feature().tags()) {
        SolverFeature feature=m.sol("sol1").feature(f);
        if("StudyStep".equals(feature.getType()))feature.set("splitcomplex",true);
        if("Optimization".equals(feature.getType())) {
          configureOptimizer(feature);
        }
      }
      verifyOptimization(m);
    }
    m.component(C).mesh("mesh1").run();
    for(int i=1;i<=4*(int)number("guided_modes",1);i++)m.component(C).physics(P).feature("port"+i).set("PortExcitation",i==1?"on":"off");
    m.sol("sol1").feature("o1").set("mmamaxiter",(int)number("iterations",3));
    // A restart may intentionally change optimizer tuning, never the checked
    // physical model or objective. Apply it also without solver regeneration.
    configureOptimizer(m.sol("sol1").feature("o1"));
    verifyOptimizerControls(m);
    for(String f:m.sol("sol1").feature().tags()) configureDirect(m.sol("sol1").feature(f),"sol1/"+f);
    m.sol("sol1").clearSolutionData();
    System.out.println("RESTART_SEED="+seed+",beta="+m.param().get("beta"));
    return m;
  }
  static void configureDirect(SolverFeature feature,String path) {
    System.out.println("SOLVER_TREE="+path+":"+feature.getType());
    if("Direct".equals(feature.getType())) {
      feature.set("linsolver","mumps");
      System.out.println("DIRECT_SOLVER="+path+"=mumps");
    }
    if("FullyCoupled".equals(feature.getType())) {
      // For fixed controls the filter is linear and independent of E. Maxwell
      // is linear once that filtered field is fixed. Full Newton with a fresh
      // Jacobian exploits this triangular dependency; automatic damping can
      // stall after a sharp projection update. A residual-only early exit can
      // reuse a Jacobian whose E/filter coupling still contains the old field,
      // even though the triangular primal solve already has a tiny residual.
      // Require a small solution correction so the reused sensitivity Jacobian
      // is assembled at the converged field. No tolerance is relaxed.
      feature.set("dtech","const");feature.set("damp",1);
      feature.set("jtech","onevery");feature.set("ntermconst","tol");
      feature.set("termonres","off");
      require("const".equals(feature.getString("dtech"))&&"onevery".equals(feature.getString("jtech"))&&feature.getDouble("damp")==1&&"tol".equals(feature.getString("ntermconst"))&&"off".equals(feature.getString("termonres")),"State Newton readback failed");
      System.out.println("STATE_NEWTON="+path+",full_step,fresh_jacobian,solution_tolerance_termination");
    }
    for(String child:feature.feature().tags()) configureDirect(feature.feature(child),path+"/"+child);
  }
  static double[] slabMode(boolean odd,double wavelength) {
    double a=.2e-6, k0=2*Math.PI/(wavelength*1e-9);
    double ec=number("eps_core",12.1), eb=number("eps_clad",2.1);
    double v=k0*a*Math.sqrt(ec-eb), lo=(odd?Math.PI/2:0)+1e-13, hi=Math.min(v,odd?Math.PI:Math.PI/2)-1e-13;
    if(odd) require(v<Math.PI,"The two-mode fixture does not cover an additional propagating slab branch");
    require(hi>lo,"Requested slab mode is below cutoff");
    for(int i=0;i<100;i++) {
      double u=(lo+hi)/2, w=Math.sqrt(Math.max(0,v*v-u*u));
      double residual=odd?-u*Math.cos(u)-(ec/eb)*w*Math.sin(u):u*Math.sin(u)-(ec/eb)*w*Math.cos(u);
      if(residual<0) lo=u;else hi=u;
    }
    double u=(lo+hi)/2, w=Math.sqrt(v*v-u*u);
    return new double[]{Math.sqrt(ec-Math.pow(u/(k0*a),2)),u/a,w/a};
  }
  static String trainingFrequencies() {
    if(cfg.getProperty("training_band","single").equals("five"))return "c_const/1580[nm] c_const/1565[nm] c_const/1550[nm] c_const/1536.61[nm] c_const/1520[nm]";
    return cfg.getProperty("training_band","single").equals("three")?"c_const/1580[nm] c_const/1550[nm] c_const/1520[nm]":"freq0";
  }
  static double[] trainingWavelengths() {
    if(cfg.getProperty("training_band","single").equals("five"))return new double[]{1520,1536.61,1550,1565,1580};
    return new double[]{1520,1550,1580};
  }
  static String dispersionExpression(int component,boolean odd) {
    double center=number("wavelength_nm",1550);
    String unit=component==0?"":"[1/m]";
    String expression=""+slabMode(odd,center)[component]+unit;
    // Exact analytic roots at each trained frequency. Rebuild binary models for other wavelengths.
    if(!cfg.getProperty("training_band","single").equals("single"))
      for(double wavelength:trainingWavelengths())
        expression="if(abs(freq-c_const/"+wavelength+"[nm])<1[Hz],"+slabMode(odd,wavelength)[component]+unit+","+expression+")";
    return expression;
  }
  static void rect(GeomSequence g,String t,double x,double y,double w,double h,String contribution) {
    g.create(t,"Rectangle"); g.feature(t).set("pos",new double[]{x,y});
    g.feature(t).set("size",new double[]{w,h}); g.feature(t).set("selresult","on");
    if(contribution!=null) g.feature(t).set("contributeto",contribution);
  }
  static void maskPolygon(GeomSequence g,String tag,double[][] vertices,String contribution) {
    g.create(tag,"Polygon");g.feature(tag).set("source","table");
    g.feature(tag).set("table",vertices);g.feature(tag).set("type","solid");
    g.feature(tag).set("selresult","on");
    if(contribution!=null)g.feature(tag).set("contributeto",contribution);
  }
  static void box(GeomSequence g,String t,int dim,double x0,double x1,double y0,double y1) {
    g.create(t,"BoxSelection"); g.feature(t).set("entitydim",dim);
    g.feature(t).set("xmin",x0); g.feature(t).set("xmax",x1);
    g.feature(t).set("ymin",y0); g.feature(t).set("ymax",y1);
    g.feature(t).set("condition","inside"); g.feature(t).set("selkeep","on");
  }
  static void material(Model m,String tag,String selection,String eps) {
    m.component(C).material().create(tag,"Common");
    if(selection==null) m.component(C).material(tag).selection().all();
    else m.component(C).material(tag).selection().named(selection);
    m.component(C).material(tag).propertyGroup("def").set("relpermittivity",new String[]{eps,"0","0","0",eps,"0","0","0",eps});
    m.component(C).material(tag).propertyGroup("def").set("relpermeability",new String[]{"1","0","0","0","1","0","0","0","1"});
    m.component(C).material(tag).propertyGroup("def").set("electricconductivity",new String[]{"0","0","0","0","0","0","0","0","0"});
  }
  static void configureInPlane(Model m) {
    // Verified by a fresh COMSOL 6.4 API inspector and driven slab benchmark.
    m.component(C).physics(P).prop("components").set("components","inplane");
    require("inplane".equals(m.component(C).physics(P).prop("components").getString("components")),"In-plane E readback failed");
    System.out.println("POLARIZATION_VERIFIED=components/components=inplane");
  }
  static String modeProfile(String transverse,boolean odd) {
    if(odd)return "if(abs("+transverse+")<=0.2[um],sin(hmode1*"+transverse+"),sin(hmode1*0.2[um])*exp(-qmode1*(abs("+transverse+")-0.2[um]))*sign("+transverse+"))";
    return "if(abs("+transverse+")<=0.2[um],cos(hmode0*"+transverse+"),cos(hmode0*0.2[um])*exp(-qmode0*(abs("+transverse+")-0.2[um])))";
  }
  static void modalProjection(Model m) {
    m.component(C).variable().create("modalprojection");
    for(int i=1;i<=4*(int)number("guided_modes",1);i++) {
      int physical=(i-1)%4+1,mode=(i-1)/4;
      String transverse=physical==1||physical==4?"y":"x";
      String h="("+modeProfile(transverse,mode==1)+")*1[A/m]";
      String z="(nmode"+mode+"/(c_const*epsilon0_const*if(abs("+transverse+")<=0.2[um],eps_core,eps_clad)))";
      String integral="flux_p"+physical;
      String normalized="("+h+")*sqrt(2[W/m]/"+integral+"(("+z+")*("+h+")^2))";
      String et=physical==1?"-ewfd.Ey":physical==2?"ewfd.Ex":physical==3?"-ewfd.Ex":"ewfd.Ey";
      String phase="2*pi*nmode"+mode+"*freq/c_const*projection_offset";
      m.component(C).variable("modalprojection").set("modal_a"+i,integral+"(("+normalized+")*(("+et+")+("+z+")*ewfd.Hz))/(4[W/m])*exp(-i*("+phase+"))");
      m.component(C).variable("modalprojection").set("modal_b"+i,"-"+integral+"(("+normalized+")*(("+z+")*ewfd.Hz-("+et+")))/(4[W/m])*exp(i*("+phase+"))");
    }
  }
  static Model build(boolean optimize) throws Exception {
    boolean canary=cfg.getProperty("mode","baseline").equals("gradient");
    boolean binary=cfg.getProperty("mode","baseline").equals("binary");
    Model m=ModelUtil.create("Hadamard"); m.modelPath(cwd);
    m.label("2D in-plane E material-index surrogate; 1.69 um2 design; access excluded");
    m.param().set("lambda0",number("wavelength_nm",1550)+"[nm]");
    m.param().set("freq0","c_const/lambda0");
    m.param().set("eps_core",""+number("eps_core",12.1));
    m.param().set("eps_clad",""+number("eps_clad",2.1));
    m.param().set("rf",number("rf_um",.05)+"[um]");
    m.param().set("beta",""+number("beta",2));
    m.param().set("meshsize",number("mesh_um",.045)+"[um]");
    m.param().set("alpha","0");
    m.param().set("gate_weight",""+number("fidelity_weight",1));
    m.param().set("outer_half",XMAX+"[um]");
    m.param().set("port_half",WINDOW+"[um]");
    double[] modal=slabMode(false,number("wavelength_nm",1550));
    m.param().set("neff0",""+modal[0]);
    m.param().set("mode_h",modal[1]+"[1/m]");
    m.param().set("mode_q",modal[2]+"[1/m]");
    System.out.println("ANALYTIC_TM0_NEFF="+modal[0]);
    if(number("guided_modes",1)==2) {
      double[] odd=slabMode(true,number("wavelength_nm",1550));
      m.param().set("neff1",""+odd[0]);m.param().set("mode_h1",odd[1]+"[1/m]");m.param().set("mode_q1",odd[2]+"[1/m]");
      System.out.println("ANALYTIC_TM1_NEFF="+odd[0]);
    }
    m.component().create(C,true); m.component(C).geom().create(G,2);
    m.component(C).variable().create("portdispersion");
    for(int mode=0;mode<(int)number("guided_modes",1);mode++) {
      m.component(C).variable("portdispersion").set("nmode"+mode,dispersionExpression(0,mode==1));
      m.component(C).variable("portdispersion").set("hmode"+mode,dispersionExpression(1,mode==1));
      m.component(C).variable("portdispersion").set("qmode"+mode,dispersionExpression(2,mode==1));
    }
    GeomSequence g=m.component(C).geom(G); g.lengthUnit("um");
    g.selection().create("access","CumulativeSelection");
    g.selection().create("design","CumulativeSelection");
    g.selection().create("binary","CumulativeSelection");
    double pmlStart=XMAX+.25,far=pml()?pmlStart+number("pml_thickness_um",.8):XMAX;
    double fluxHalf=XMAX-number("projection_offset_um",.2);
    double[] cuts=pml()?new double[]{-far,-pmlStart,-XMAX,-fluxHalf,-WINDOW,WINDOW,fluxHalf,XMAX,pmlStart,far}:new double[]{-XMAX,-WINDOW,WINDOW,XMAX};
    if(pml()) {
      g.selection().create("pml","CumulativeSelection");
      g.selection().create("fluxvol","CumulativeSelection");
      m.param().set("pml_thickness",number("pml_thickness_um",.8)+"[um]");
      m.param().set("pml_scale",""+number("pml_scale",1));
      m.param().set("pml_curvature",""+number("pml_curvature",3));
      m.param().set("flux_half",fluxHalf+"[um]");
      m.param().set("projection_offset",number("projection_offset_um",.2)+"[um]");
    }
    for(int i=0;i<cuts.length-1;i++) for(int j=0;j<cuts.length-1;j++) {
      boolean absorbing=pml()&&(i==0||j==0||i==cuts.length-2||j==cuts.length-2);
      boolean inside=pml()&&cuts[i]>=-fluxHalf&&cuts[i+1]<=fluxHalf&&cuts[j]>=-fluxHalf&&cuts[j+1]<=fluxHalf;
      rect(g,"bg"+i+j,cuts[i],cuts[j],cuts[i+1]-cuts[i],cuts[j+1]-cuts[j],absorbing?"pml":inside?"fluxvol":null);
    }
    g.create("dtop","Polygon");
    g.feature("dtop").set("source","table");
    g.feature("dtop").set("table",new double[][]{{-HALF,-HALF},{-HALF,HALF},{HALF,HALF}});
    g.feature("dtop").set("type","solid");
    g.feature("dtop").set("selresult","on");
    g.feature("dtop").set("contributeto","design");
    g.create("dbottom","Polygon");
    g.feature("dbottom").set("source","table");
    g.feature("dbottom").set("table",new double[][]{{-HALF,-HALF},{HALF,-HALF},{HALF,HALF}});
    g.feature("dbottom").set("type","solid");
    g.feature("dbottom").set("selresult","on");
    g.feature("dbottom").set("contributeto","design");
    rect(g,"left",-far,-.2,far-HALF,.4,"access");
    rect(g,"bottomarm",-.2,-far,.4,far-HALF,"access");
    rect(g,"toparm",-.2,HALF,.4,far-HALF,"access");
    rect(g,"right",HALF,-.2,far-HALF,.4,"access");
    // __MASK_GEOMETRY__
    g.run("fin");
    double tol=1e-5;
    box(g,"p1",1,-XMAX-tol,-XMAX+tol,-WINDOW-tol,WINDOW+tol);
    box(g,"p2",1,-WINDOW-tol,WINDOW+tol,-YMAX-tol,-YMAX+tol);
    box(g,"p3",1,-WINDOW-tol,WINDOW+tol,YMAX-tol,YMAX+tol);
    box(g,"p4",1,XMAX-tol,XMAX+tol,-WINDOW-tol,WINDOW+tol);
    String[] openings=new String[8]; int opening=0;
    for(int axis=0;axis<2;axis++) for(int sign:new int[]{-1,1}) for(int side:new int[]{-1,1}) {
      String tag="open"+opening; openings[opening++]=tag;
      double low=side<0?-XMAX-tol:WINDOW-tol, high=side<0?-WINDOW+tol:XMAX+tol;
      if(axis==0) box(g,tag,1,sign*XMAX-tol,sign*XMAX+tol,low,high);
      else box(g,tag,1,low,high,sign*YMAX-tol,sign*YMAX+tol);
    }
    g.create("open","UnionSelection"); g.feature("open").set("entitydim",1);
    g.feature("open").set("input",openings);
    if(pml()) {
      box(g,"flux_p1",1,-fluxHalf-tol,-fluxHalf+tol,-WINDOW-tol,WINDOW+tol);
      box(g,"flux_p2",1,-WINDOW-tol,WINDOW+tol,-fluxHalf-tol,-fluxHalf+tol);
      box(g,"flux_p3",1,-WINDOW-tol,WINDOW+tol,fluxHalf-tol,fluxHalf+tol);
      box(g,"flux_p4",1,fluxHalf-tol,fluxHalf+tol,-WINDOW-tol,WINDOW+tol);
      String[] segments=new String[8];int k=0;
      for(int axis=0;axis<2;axis++)for(int sign:new int[]{-1,1})for(int side:new int[]{-1,1}) {
        String tag="flux_open"+k;segments[k++]=tag;
        double low=side<0?-fluxHalf-tol:WINDOW-tol,high=side<0?-WINDOW+tol:fluxHalf+tol;
        if(axis==0)box(g,tag,1,sign*fluxHalf-tol,sign*fluxHalf+tol,low,high);
        else box(g,tag,1,low,high,sign*fluxHalf-tol,sign*fluxHalf+tol);
      }
      g.create("flux_open","UnionSelection");g.feature("flux_open").set("entitydim",1);g.feature("flux_open").set("input",segments);
    }
    g.run();
    verifyExterior(m);
    System.out.println("DESIGN_UPPER_DOMAINS="+Arrays.toString(m.component(C).selection(dom("dtop")).entities(2)));
    ensureFlux(m);
    if(!binary) {
    m.component(C).common().create("cvf1","ControlVariableField");
    m.component(C).common("cvf1").selection().geom(G,2);
    m.component(C).common("cvf1").selection().named(dom("dtop"));
    m.component(C).common("cvf1").set("name","theta_c");
    m.component(C).common("cvf1").set("initialValue","0.5");
    m.component(C).common("cvf1").set("useBounds",true);
    m.component(C).common("cvf1").set("lbound","0");
    m.component(C).common("cvf1").set("ubound","1");
    m.component(C).common("cvf1").set("shapeFunctionType","shdisc");
    m.component(C).common("cvf1").set("order","0");
    m.component(C).physics().create("filter","CoefficientFormPDE",G);
    m.component(C).physics("filter").selection().named(dom("dtop"));
    m.component(C).physics("filter").field("dimensionless").field("theta_f");
    m.component(C).physics("filter").field("dimensionless").component(new String[]{"theta_f"});
    m.component(C).physics("filter").prop("ShapeProperty").set("order",1);
    m.component(C).physics("filter").prop("ShapeProperty").set("valueType","real");
    m.component(C).physics("filter").prop("Units").set("SourceTermQuantity","dimensionless");
    // Row scaling preserves the Helmholtz equation while balancing micron-scale
    // domain integrals against the Maxwell residual in the transposed system.
    m.component(C).physics("filter").feature("cfeq1").set("c","1e12*rf^2");
    m.component(C).physics("filter").feature("cfeq1").set("a","1e12");
    String direction=number("direction",0)==0?"cos(2*pi*x/1.3[um])*sin(pi*y/1.3[um])":"0.7*cos(pi*(x+y)/1.3[um])+0.3*sin(3*pi*x/1.3[um])";
    m.component(C).physics("filter").feature("cfeq1").set("f","1e12*(theta_c+alpha*("+direction+"))");
    m.component(C).physics("filter").feature("cfeq1").set("da","0");
    // Default zero flux is retained on all filter boundaries, including symmetry line.
    m.component(C).cpl().create("mirror","GeneralExtrusion");
    m.component(C).cpl("mirror").selection().geom(G,2);
    m.component(C).cpl("mirror").selection().named(dom("dtop"));
    m.component(C).cpl("mirror").set("dstmap",new String[]{"min(x,y)","max(x,y)"});
    m.component(C).variable().create("density");
    m.component(C).variable("density").selection().named(dom("design"));
    m.component(C).variable("density").set("rho","(tanh(beta*0.5)+tanh(beta*(mirror(theta_f)-0.5)))/(2*tanh(beta*0.5))");
    }
    material(m,"clad",null,"eps_clad");
    material(m,"access",dom("access"),"eps_core");
    material(m,"design",dom("design"),binary?"eps_clad":"eps_clad+(eps_core-eps_clad)*rho");
    if(binary&&m.component(C).selection(dom("binary")).entities(2).length>0)
      material(m,"binary",dom("binary"),"eps_core");
    m.component(C).physics().create(P,"ElectromagneticWavesFrequencyDomain",G);
    configureInPlane(m);
    if(pml()) {
      m.component(C).selection().create("outerTermination","Explicit");
      m.component(C).selection("outerTermination").geom(G,2,1,new String[]{"exterior"});
      m.component(C).selection("outerTermination").all();
      m.component(C).physics(P).create("outerPEC","PerfectElectricConductor",1);
      m.component(C).physics(P).feature("outerPEC").selection().named("outerTermination");
      m.component(C).coordSystem().create("pml1",G,"PML");
      m.component(C).coordSystem("pml1").selection().named(dom("pml"));
      m.component(C).coordSystem("pml1").set("ScalingType","Cartesian");
      m.component(C).coordSystem("pml1").set("stretchingType","polynomial");
      // One coordinate stretch across core and cladding. A material-dependent
      // wavelength changes the transformation at the transverse interface.
      m.component(C).coordSystem("pml1").set("wavelengthSourceType","userDefined");
      m.component(C).coordSystem("pml1").set("typicalWavelength","c_const/freq/sqrt(eps_clad)");
      m.component(C).coordSystem("pml1").set("PMLfactor","pml_scale");
      m.component(C).coordSystem("pml1").set("PMLgamma","pml_curvature");
    } else {
      m.component(C).physics(P).create("sbc","Scattering",1);
      m.component(C).physics(P).feature("sbc").selection().named(sel("open"));
    }
    for(int i=1;i<=4*(int)number("guided_modes",1);i++) {
      int physical=(i-1)%4+1;boolean odd=i>4;
      String tag="port"+i;
      m.component(C).physics(P).create(tag,"Port",1);
      m.component(C).physics(P).feature(tag).selection().named(sel("p"+physical));
      m.component(C).physics(P).feature(tag).set("PortType","UserDefined");
      m.component(C).physics(P).feature(tag).set("InputType","H");
      String transverse=physical==1||physical==4?"y":"x";
      String hz="if(abs("+transverse+")<=0.2[um],cos(hmode0*"+transverse+"),cos(hmode0*0.2[um])*exp(-qmode0*(abs("+transverse+")-0.2[um])))";
      if(odd)hz="if(abs("+transverse+")<=0.2[um],sin(hmode1*"+transverse+"),sin(hmode1*0.2[um])*exp(-qmode1*(abs("+transverse+")-0.2[um]))*sign("+transverse+"))";
      m.component(C).physics(P).feature(tag).set("H0",new String[]{"0","0",hz});
      m.component(C).physics(P).feature(tag).set("beta",odd?"2*pi*nmode1*freq/c_const":"2*pi*nmode0*freq/c_const");
      System.out.println("PORT_H0_"+i+"="+Arrays.toString(m.component(C).physics(P).feature(tag).getStringArray("H0")));
      m.component(C).physics(P).feature(tag).set("PortName",""+i);
      m.component(C).physics(P).feature(tag).set("PortExcitation",(optimize||canary)&&i!=1?"off":"on");
      m.component(C).physics(P).feature(tag).set("PortOrientation","ForwardPort");
      if(pml()) {
        m.component(C).physics(P).feature(tag).set("PortSlit",true);
        m.component(C).physics(P).feature(tag).set("SlitType","DomainBacked");
        m.component(C).physics(P).feature(tag).set("PortOrientation",physical<=2?"ForwardPort":"ReversePort");
      }
      m.component(C).physics(P).feature(tag).set("Thetap","0");
      m.component(C).physics(P).feature(tag).set("Pin","1[W/m]");
    }
    if(pml()) {modalProjection(m);verifyPML(m);}
    m.component(C).mesh().create("mesh1");
    m.component(C).mesh("mesh1").create("bgsize","Size");
    m.component(C).mesh("mesh1").feature("bgsize").set("custom",true);
    m.component(C).mesh("mesh1").feature("bgsize").set("hmax",number("cladding_mesh_um",.22)+"[um]");
    m.component(C).mesh("mesh1").feature("bgsize").set("hmin","meshsize/3");
    for(String s:new String[]{"access","design"}) {
      String tag="size_"+s; m.component(C).mesh("mesh1").create(tag,"Size");
      m.component(C).mesh("mesh1").feature(tag).selection().named(dom(s));
      m.component(C).mesh("mesh1").feature(tag).set("custom",true);
      m.component(C).mesh("mesh1").feature(tag).set("hmax","meshsize");
      m.component(C).mesh("mesh1").feature(tag).set("hmin","meshsize/3");
    }
    if(pml()) {
      m.component(C).mesh("mesh1").create("pmlmap","Map");
      m.component(C).mesh("mesh1").feature("pmlmap").selection().named(dom("pml"));
    }
    m.component(C).mesh("mesh1").create("ftri1","FreeTri");
    m.component(C).mesh("mesh1").run();
    m.study().create("std1");
    m.study("std1").create("freq",optimize||canary?"Frequency":"FrequencyDomainSourceSweep");
    m.study("std1").feature("freq").set("plist",optimize||canary?trainingFrequencies():"freq0");
    m.study("std1").feature("freq").set("useparam","off");
    if(optimize) {
      m.study("std1").create("topo","TopologyOptimization");
      m.study("std1").feature("topo").set("mmamaxiter",(int)number("iterations",3));
      m.study("std1").feature("topo").set("optobj",new String[]{OBJECTIVE});
      m.study("std1").feature("topo").set("objectivetype","maximization");
      m.study("std1").feature("topo").set("objectivesolution",cfg.getProperty("training_band","single").equals("single")?"auto":"min");
      m.study("std1").feature("topo").set("probesel","none");
    }
    if(canary) {
      m.study("std1").create("sens","Sensitivity");
      m.study("std1").feature("sens").set("pname",new String[]{"alpha"});
      m.study("std1").feature("sens").set("initval",new String[]{"0"});
      m.study("std1").feature("sens").set("scale",new String[]{"1"});
      m.study("std1").feature("sens").set("valuetype",new String[]{"real"});
      m.study("std1").feature("sens").set("controlVariableActive",new String[]{"off"});
      m.study("std1").feature("sens").set("optobj",new String[]{OBJECTIVE});
      m.study("std1").feature("sens").set("gradientMethod","adjoint");
    }
    m.study("std1").createAutoSequences("sol");
    for(String sol:m.sol().tags()) {
      System.out.println("SOLVER="+sol+" FEATURES="+Arrays.toString(m.sol(sol).feature().tags()));
      for(String f:m.sol(sol).feature().tags()) {
        System.out.println("SOLVER_FEATURE="+sol+"/"+f+" TYPE="+m.sol(sol).feature(f).getType());
        if((optimize||canary)&&"StudyStep".equals(m.sol(sol).feature(f).getType()))
          m.sol(sol).feature(f).set("splitcomplex",true);
        if("Optimization".equals(m.sol(sol).feature(f).getType())) {
          configureOptimizer(m.sol(sol).feature(f));
          m.sol(sol).feature(f).set("mmamaxiter",(int)number("iterations",3));
          System.out.println("OPTIMIZATION_CHILDREN="+Arrays.toString(m.sol(sol).feature(f).feature().tags()));
        }
        configureDirect(m.sol(sol).feature(f),sol+"/"+f);
      }
    }
    m.save(cwd+"/configured.mph");
    if(optimize) {verifyOptimization(m);verifyOptimizerControls(m);}
    return m;
  }
  static double[] flatten(double[][] x) {
    int n=0; if(x!=null) for(double[] r:x) if(r!=null)n+=r.length;
    double[] z=new double[n]; int k=0;
    if(x!=null)for(double[] r:x)if(r!=null)for(double v:r)z[k++]=v; return z;
  }
  static double[][] series(Model m,String dataset,String expression) {
    String t="series"; m.result().numerical().create(t,"Global");
    try {
      m.result().numerical(t).set("data",dataset); m.result().numerical(t).set("expr",new String[]{expression});
      double[][][] a=m.result().numerical(t).getData(), b=m.result().numerical(t).getImagData();
      double[] re=flatten(a[0]), im=b==null?new double[re.length]:flatten(b[0]);
      require(re.length==im.length,"Complex output length mismatch"); return new double[][]{re,im};
    } finally {m.result().numerical().remove(t);}
  }
  static String drivenDataset(Model m) {
    for(String d:m.result().dataset().tags()) {
      System.out.println("DATASET="+d+" TYPE="+m.result().dataset(d).getType());
      if("Solution".equals(m.result().dataset(d).getType())) {
        String solution=m.result().dataset(d).getString("solution");
        System.out.println("DATASET_SOLUTION="+d+"="+solution);
      }
    }
    // createAutoSequences standard first solution dataset; missing/invalid data throws at export.
    return "dset1";
  }
  static String datasetFor(Model m,String sol) {
    for(String d:m.result().dataset().tags())
      if("Solution".equals(m.result().dataset(d).getType())&&sol.equals(m.result().dataset(d).getString("solution"))) return d;
    throw new IllegalStateException("No dataset for "+sol);
  }
  static void trainingObservations(Model m,String active,int stage) {
    String d=datasetFor(m,active);
    double[] wavelength=series(m,d,"c_const/freq/1[nm]")[0];
    double[] objective=series(m,d,OBJECTIVE)[0];
    double[][] a=series(m,d,pml()?"comp1.modal_a3":"comp1.ewfd.S31");
    double[][] b=series(m,d,pml()?"comp1.modal_a4":"comp1.ewfd.S41");
    require(wavelength.length==objective.length,"Training objective/frequency mapping mismatch");
    require(a[0].length==objective.length&&a[1].length==objective.length&&b[0].length==objective.length&&b[1].length==objective.length,"Training modal/frequency mapping mismatch");
    double lowest=Double.POSITIVE_INFINITY, activeWavelength=Double.NaN;
    for(int i=0;i<objective.length;i++) {
      require(Double.isFinite(objective[i]),"Nonfinite training objective");
      require(Double.isFinite(a[0][i])&&Double.isFinite(a[1][i])&&Double.isFinite(b[0][i])&&Double.isFinite(b[1][i]),"Nonfinite training modal response");
      System.out.println("TRAINING_POINT="+stage+","+wavelength[i]+","+objective[i]);
      System.out.println("TRAINING_MODAL="+stage+","+wavelength[i]+","+a[0][i]+","+a[1][i]+","+b[0][i]+","+b[1][i]);
      if(objective[i]<lowest) {lowest=objective[i];activeWavelength=wavelength[i];}
    }
    System.out.println("TRAINING_MINIMUM="+stage+","+activeWavelength+","+lowest);
  }
  static String frozenValidation(Model m,String active) throws Exception {
    String frozen=unusedSolution(m,"frozenDesign");
    m.sol(active).copySolution(frozen);
    m.component(C).common("cvf1").set("initialValue","withsol('"+frozen+"',comp1.theta_c)");
    for(int i=1;i<=4*(int)number("guided_modes",1);i++) m.component(C).physics(P).feature("port"+i).set("PortExcitation","on");
    m.study().create("validation");
    m.study("validation").create("freq","FrequencyDomainSourceSweep");
    m.study("validation").feature("freq").set("plist","freq0");
    m.study("validation").feature("freq").set("useparam","off");
    m.study("validation").createAutoSequences("sol");
    String val=null;
    for(String s:m.sol().tags()) if(!s.equals(active)&&m.sol(s).feature().tags().length>0) val=s;
    require(val!=null,"No validation solver");
    for(String f:m.sol(val).feature().tags()) configureDirect(m.sol(val).feature(f),val+"/"+f);
    m.sol(val).runAll();
    return datasetFor(m,val);
  }
  static void metrics(Model m,String dataset,boolean optimize) throws Exception {
    int channels=4*(int)number("guided_modes",1), sources=optimize?1:channels;
    if(!optimize) {
      double[][] sourceIds=series(m,dataset,"PortName");
      require(sourceIds[0].length==channels,"Unexpected source sweep cardinality");
      for(int i=0;i<channels;i++) require(Math.abs(sourceIds[0][i]-(i+1))<1e-12,"Source solution order mismatch");
      System.out.println("SOURCE_ORDER_VERIFIED="+Arrays.toString(sourceIds[0]));
    }
    {
      System.out.println("HADAMARD_CSV_HEADER=source,row,source_solution_index,real,imag,power,left_bottom_power,top_right_power,model_level");
      for(int source=1;source<=sources;source++) {
        double[][] vals=new double[channels][2]; double r=0,t=0;
        for(int row=1;row<=channels;row++) {
          double[][] v=series(m,dataset,pml()?"comp1.modal_a"+row:"comp1.ewfd.S"+row+source);
          int index=optimize?v[0].length-1:source-1;
          require(v[0].length>=sources,"Missing source solutions for S"+row+source);
          vals[row-1][0]=v[0][index]; vals[row-1][1]=v[1][index];
          require(Double.isFinite(vals[row-1][0])&&Double.isFinite(vals[row-1][1]),"Nonfinite S"+row+source+" at solution "+index);
          double power=vals[row-1][0]*vals[row-1][0]+vals[row-1][1]*vals[row-1][1];
          if(row<=2)r+=power;else if(row<=4)t+=power;
        }
        for(int row=1;row<=channels;row++) {
          double re=vals[row-1][0],im=vals[row-1][1];
          System.out.printf(Locale.US,"HADAMARD_CSV=%d,%d,%d,%.17g,%.17g,%.17g,%.17g,%.17g,2D_material_index_surrogate%n",source,row,source,re,im,re*re+im*im,r,t);
        }
      }
    }
    if(pml()) {
      for(int row=1;row<=channels;row++) {
        double[][] incoming=series(m,dataset,"comp1.modal_b"+row);
        for(int source=1;source<=sources;source++) {
          double re=incoming[0][source-1],im=incoming[1][source-1];
          System.out.println("MODAL_INCOMING="+source+","+row+","+re+","+im);
        }
      }
    }
    System.out.println("HADAMARD_POWER_HEADER=source,net_p1,net_p2,net_p3,net_p4,open_outward,closed_surface_residual");
    double[][][] flux=new double[5][][];
    String[] surfaces={"p1","p2","p3","p4","open"};
    for(int j=0;j<5;j++) {
      // PML model: use explicit outward normals on a source-free interior contour,
      // avoiding ambiguous interior boundary normals and the slit field jump.
      String nx=pml()?"if(abs(abs(x)-flux_half)<1e-10[m],sign(x),0)":"nx";
      String ny=pml()?"if(abs(abs(y)-flux_half)<1e-10[m],sign(y),0)":"ny";
      flux[j]=series(m,dataset,"comp1.flux_"+surfaces[j]+"((comp1.ewfd.Poavx*("+nx+")+comp1.ewfd.Poavy*("+ny+"))/(1[W/m]))");
    }
    for(int i=0;i<sources;i++) {
      System.out.print("HADAMARD_POWER="+(i+1));double sum=0;
      for(int j=0;j<5;j++) {double value=flux[j][0][i];sum+=value;System.out.print(","+value);}
      System.out.println(","+sum);
    }
  }
  static void density(Model m,String dataset) {
    String tag="densitymesh";
    m.result().numerical().create(tag,"Eval");
    m.result().numerical(tag).set("data",dataset);
    m.result().numerical(tag).selection().geom(G,2);
    m.result().numerical(tag).selection().set(m.component(C).selection(dom("design")).entities(2));
    m.result().numerical(tag).set("expr",new String[]{"x/1[um]","y/1[um]","comp1.mirror(comp1.theta_c)","comp1.mirror(comp1.theta_f)","comp1.rho"});
    m.result().numerical(tag).set("pattern","lagrange");
    m.result().numerical(tag).set("refine",1);
    m.result().numerical(tag).set("smooth","none");
    double[][][] values=m.result().numerical(tag).getData();
    int solution=values[0].length-1;
    System.out.println("HADAMARD_DENSITY_HEADER=x_um,y_um,theta_c,theta_f,rho");
    for(int i=0;i<values[0][solution].length;i++) {
      System.out.print("HADAMARD_DENSITY=");
      for(int j=0;j<values.length;j++) System.out.print((j==0?"":",")+values[j][solution][i]);
      System.out.println();
    }
    m.result().numerical().remove(tag);
  }
  static void gradientCheck(Model m,String active) throws Exception {
    double objective=series(m,"dset1",OBJECTIVE)[0][0];
    require(Double.isFinite(objective),"Nonfinite gradient base objective");
    System.out.println("GRADIENT_BASE_OBJECTIVE="+objective);
    double gradient=series(m,"dset1","fsens(alpha)")[0][0];
    System.out.println("GRADIENT_ADJOINT="+gradient);
    require(Double.isFinite(gradient),"Nonfinite adjoint gradient");
    m.save(cwd+"/gradient.mph");
    m.study().create("fd");
    m.study("fd").create("freq","Frequency");
    m.study("fd").feature("freq").set("plist","freq0");
    m.study("fd").createAutoSequences("sol");
    String fdsol=null,fdds=null;
    for(String s:m.sol().tags()) if(!s.equals(active)&&m.sol(s).feature().tags().length>0) fdsol=s;
    require(fdsol!=null,"No finite-difference solution");
    for(String d:m.result().dataset().tags()) if("Solution".equals(m.result().dataset(d).getType())&&fdsol.equals(m.result().dataset(d).getString("solution"))) fdds=d;
    require(fdds!=null,"No finite-difference dataset");
    for(String f:m.sol(fdsol).feature().tags()) {
      if("StudyStep".equals(m.sol(fdsol).feature(f).getType()))m.sol(fdsol).feature(f).set("splitcomplex",true);
      configureDirect(m.sol(fdsol).feature(f),fdsol+"/"+f);
    }
    int passed=0;
    for(double step:new double[]{.001,.0005}) {
      double[] values=new double[2];int index=0;
      for(int sign:new int[]{-1,1}) {
        m.param().set("alpha",""+(sign*step));
        m.sol(fdsol).clearSolutionData();m.sol(fdsol).runAll();
        values[index++]=series(m,fdds,OBJECTIVE)[0][0];
      }
      double fd=(values[1]-values[0])/(2*step), absolute=Math.abs(fd-gradient);
      System.out.printf(Locale.US,"GRADIENT_FD_POINT=%.17g,%.17g,%.17g%n",step,values[0],values[1]);
      double relative=absolute/Math.max(1e-8,Math.max(Math.abs(fd),Math.abs(gradient)));
      if(absolute<1e-6||relative<.002) passed++;
      System.out.printf(Locale.US,"GRADIENT_CHECK=%.17g,%.17g,%.17g,%.17g,%.17g%n",step,gradient,fd,absolute,relative);
    }
    require(passed==2,"Directional adjoint check failed");
    System.out.println("HADAMARD_GRADIENT_CHECK_COMPLETE");
  }
  static void field(Model m,String dataset) {
    String tag="fieldmesh";m.result().numerical().create(tag,"Eval");
    m.result().numerical(tag).set("data",dataset);
    m.result().numerical(tag).selection().geom(G,2);
    m.result().numerical(tag).selection().all();
    m.result().numerical(tag).set("expr",new String[]{"x/1[um]","y/1[um]","realdot(comp1.ewfd.Hz,comp1.ewfd.Hz)"});
    m.result().numerical(tag).set("pattern","lagrange");
    m.result().numerical(tag).set("refine",1);
    m.result().numerical(tag).set("smooth","none");
    double[][][] values=m.result().numerical(tag).getData();
    System.out.println("HADAMARD_FIELD_HEADER=x_um,y_um,Hz_abs_squared_source1");
    for(int i=0;i<values[0][0].length;i++) {
      System.out.print("HADAMARD_FIELD=");
      for(int j=0;j<values.length;j++) System.out.print((j==0?"":",")+values[j][0][i]);
      System.out.println();
    }
    m.result().numerical().remove(tag);
  }
  public static void main(String[] args) throws Exception {
    System.out.println("COMSOL_VERSION="+ModelUtil.getComsolVersion());
    cwd="__RUN_DIRECTORY__";
    // __RUN_CONFIG__
    OBJECTIVE=cfg.getProperty("objective_profile","coherent").equals("state_floor")?STATE_FLOOR_OBJECTIVE:COHERENT_OBJECTIVE;
    OBJECTIVE=profileObjective(OBJECTIVE);
    XMAX=number("outer_half_um",3.15);YMAX=XMAX;WINDOW=number("port_half_um",1.5);
    String mode=cfg.getProperty("mode","baseline");
    require(mode.equals("baseline")||mode.equals("optimize")||mode.equals("gradient")||mode.equals("binary")||mode.equals("frozen"),"unknown mode");
    boolean optimize=mode.equals("optimize");
    System.out.println("MODEL_SCOPE=2D_material_index_surrogate,design_area_um2=1.69,access_centerline_each_um="+(XMAX-HALF)+",outer_box_side_um="+(2*XMAX)+",port_half_um="+WINDOW+",ports=left_bottom_top_right");
    if(mode.equals("frozen")) {
      require(restart.length()>0,"Frozen validation requires an optimization checkpoint");
      Model m=ModelUtil.load("Hadamard",restart);m.modelPath(cwd);
      require(m.component(C).geom(G).getSDim()==2,"Frozen validation requires this 2D fixture");
      verifyRestartGeometry(m);
      for(String key:new String[]{"beta","eps_core","eps_clad"})
        require(Math.abs(m.param().evaluate(key)-number(key,Double.NaN))<1e-12,"Frozen parameter mismatch: "+key);
      require(Math.abs(m.param().evaluate("lambda0")-number("wavelength_nm",1550)*1e-9)<1e-15,"Frozen wavelength mismatch");
      require(Math.abs(m.param().evaluate("rf")-number("rf_um",.05)*1e-6)<1e-15,"Frozen filter mismatch");
      require(Math.abs(m.param().evaluate("meshsize")-number("mesh_um",.045)*1e-6)<1e-15,"Frozen mesh mismatch");
      require(Math.abs(m.param().evaluate("gate_weight")-number("fidelity_weight",1))<1e-12,"Frozen objective weight mismatch");
      require(m.component(C).mesh("mesh1").feature("bgsize").getString("hmax").equals(number("cladding_mesh_um",.10)+"[um]"),"Frozen cladding mesh mismatch");
      require(m.study("std1").feature("freq").getString("plist").equals(trainingFrequencies()),"Frozen training-frequency set mismatch");
      verifyOptimization(m);
      removeValidation(m);ensureFlux(m);verifyExterior(m);verifyPML(m);
      String d=frozenValidation(m,"sol1");
      metrics(m,d,false);density(m,d);m.save(cwd+"/baseline.mph");
      System.out.println("HADAMARD_DIAGNOSTIC_EXPORT_COMPLETE");return;
    }
    Model m=restart.length()>0?resume():build(optimize);
    // The runner owns this single licensed batch process.
    String active=null;
    for(String sol:m.sol().tags()) if(m.sol(sol).feature().tags().length>0) {
      require(active==null,"Multiple executable solver sequences"); active=sol;
    }
    require(active!=null,"Missing executable solver sequence");
    m.sol(active).runAll();
    if(mode.equals("gradient")) { gradientCheck(m,active); return; }
    if(optimize) {
      m.save(cwd+"/stage1.mph");
      trainingObservations(m,active,1);
      for(int stage=1;stage<(int)number("stages",1);stage++) {
        String seed=unusedSolution(m,"seed");
        m.sol(active).copySolution(seed);
        m.component(C).common("cvf1").set("initialValue","withsol('"+seed+"',comp1.theta_c)");
        m.param().set("beta",""+(number("beta",2)*Math.pow(2,stage)));
        System.out.println("CONTINUATION_STAGE="+(stage+1)+",beta="+m.param().get("beta"));
        m.sol(active).clearSolutionData();
        m.sol(active).runAll();
        m.save(cwd+"/stage"+(stage+1)+".mph");
        trainingObservations(m,active,stage+1);
      }
    }
    m.save(cwd+"/"+(optimize?"final.mph":"baseline.mph"));
    String d=optimize?frozenValidation(m,active):drivenDataset(m);
    metrics(m,d,false);
    if(mode.equals("binary")) field(m,d);else density(m,d);
    m.save(cwd+"/"+(optimize?"final.mph":"baseline.mph"));
    System.out.println("HADAMARD_DIAGNOSTIC_EXPORT_COMPLETE");
  }
}
