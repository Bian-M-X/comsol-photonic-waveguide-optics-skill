import com.comsol.model.*;
import com.comsol.model.util.ModelUtil;
import java.util.*;

/** Fixed-mesh legacy-CVF beta16 diagnostic. No optimization, remesh or model save.
 * All output is stdout: native batch filesystem security is left untouched.
 * Fixed beta8 checkpoint -> beta16; one feasible discrete-control direction.
 */
public class CvfDiscreteGradientProbe {
  static final String INPUT="__RESTART_MODEL__";
  static final String OUTPUT="__RUN_DIRECTORY__";
  static final double[] WL={1580,1565,1550,1536.61,1520};
  static final double H=1e-3, BOUND_TOL=1e-8, READBACK_TOL=2e-10;
  static void req(boolean b,String s){if(!b)throw new IllegalStateException(s);}
  public static void main(String[] args)throws Exception{
    try{run();}catch(Exception e){System.out.println("PROBE_EXCEPTION="+e.getClass().getName()+":"+e.getMessage());e.printStackTrace(System.out);System.out.flush();throw e;}
  }
  // Primitive arrays and static methods only: comsolcompile exports one class.
  static boolean TREE_DUMPED=false;
  static int[] INDEX;
  static double[][] COORD;
  static int[] controlIndices(SolverSequence s){
    XmeshInfoDofs d=s.xmeshInfo().dofs();String[] names=d.dofNames();int[] ni=d.nameInds(),vi=d.solVectorInds();
    req(ni.length==vi.length,"Unknown xmesh layout");int count=0;
    for(int k=0;k<ni.length;k++)if("comp1.theta_c".equals(names[ni[k]]))count++;
    req(count>0,"No exact comp1.theta_c DOFs");int[] p=new int[count];int j=0;
    for(int k=0;k<ni.length;k++)if("comp1.theta_c".equals(names[ni[k]]))p[j++]=vi[k];
    Arrays.sort(p);for(j=1;j<p.length;j++)req(p[j]!=p[j-1],"Duplicate CVF full-vector index");return p;
  }
  static double[][] controlCoords(SolverSequence s,int[] p){
    XmeshInfoDofs d=s.xmeshInfo().dofs();String[] names=d.dofNames();int[] ni=d.nameInds(),vi=d.solVectorInds();double[][] xy=d.coords();
    req(xy.length==2&&xy[0].length==ni.length&&xy[1].length==ni.length,"Unknown 2D coordinate layout");double[][] out=new double[2][p.length];
    for(int k=0;k<ni.length;k++)if("comp1.theta_c".equals(names[ni[k]])){int j=Arrays.binarySearch(p,vi[k]);req(j>=0,"Missing mapped CVF index");out[0][j]=xy[0][k];out[1][j]=xy[1][k];}
    return out;
  }
  static void sameMap(SolverSequence s){
    int[] p=controlIndices(s);req(Arrays.equals(INDEX,p),"Unknown CVF full-vector index remapping");double[][] xy=controlCoords(s,p);
    for(int j=0;j<p.length;j++)req(Double.doubleToLongBits(COORD[0][j])==Double.doubleToLongBits(xy[0][j])&&Double.doubleToLongBits(COORD[1][j])==Double.doubleToLongBits(xy[1][j]),"Unknown remapping/component order at CVF row "+j);
  }
  static void configure(SolverFeature f,String path){
    req(!"Optimization".equals(f.getType()),"Optimization forbidden in diagnostic sequence");
    if("StudyStep".equals(f.getType()))f.set("splitcomplex",true);
    if("ControlField".equals(f.getType()))System.out.println("FRESH_CONTROL="+path+",valuetype="+f.getString("valuetype")+",scale="+f.getString("scaleval"));
    if("Direct".equals(f.getType()))f.set("linsolver","mumps");
    if("FullyCoupled".equals(f.getType())){
      f.set("dtech","const");f.set("damp",1);f.set("jtech","onevery");f.set("ntermconst","tol");f.set("termonres","off");
      req("const".equals(f.getString("dtech"))&&"onevery".equals(f.getString("jtech"))&&f.getDouble("damp")==1&&"tol".equals(f.getString("ntermconst"))&&"off".equals(f.getString("termonres")),"Fresh-Jacobian readback failed");
    }
    for(String t:f.feature().tags())configure(f.feature(t),path+"/"+t);
  }
  static void dump(SolverFeature f,String path){System.out.println("FRESH_TREE="+path+":"+f.getType()+",properties="+Arrays.toString(f.properties()));for(String t:f.feature().tags())dump(f.feature(t),path+"/"+t);}
  static String dataset(Model m,String sol){
    for(String t:m.result().dataset().tags())if("Solution".equals(m.result().dataset(t).getType())&&sol.equals(m.result().dataset(t).getString("solution")))return t;
    String t="probeData";m.result().dataset().create(t,"Solution");m.result().dataset(t).set("solution",sol);return t;
  }
  static double global(Model m,String ds,String expr){
    String t="probeGlobal";m.result().numerical().create(t,"Global");
    try{m.result().numerical(t).set("data",ds);m.result().numerical(t).set("expr",new String[]{expr});double[][][] a=m.result().numerical(t).getData();
      double value=Double.NaN;int count=0;for(double[] row:a[0])for(double v:row){value=v;count++;}
      req(count==1&&Double.isFinite(value),"Expected one finite per-frequency objective: "+count);return value;
    }finally{m.result().numerical().remove(t);}
  }
  static double[] evaluate(Model m,double[] seed,double[] dir,double alpha,double wavelength,String objective)throws Exception{
    // The stored seed's five frequency vectors all have identical controls.
    // setU() input becomes evaluable only after createSolution(), as documented.
    SolverSequence frozen=m.sol("probeSeed");int ns=frozen.getSize()[1];double[] freqs=frozen.getPVals();
    req("std1".equals(frozen.study()),"Stored seed must be associated with checkpoint study before createSolution");
    double[][] old=new double[ns][],imag=new double[ns][];
    for(int sn=1;sn<=ns;sn++){
      old[sn-1]=frozen.getU(sn,"Sol");imag[sn-1]=frozen.isRealU(sn,"Sol")?new double[old[sn-1].length]:frozen.getUImag(sn,"Sol");
      for(int k=0;k<INDEX.length;k++)old[sn-1][INDEX[k]]=seed[k]+alpha*dir[k];
    }
    frozen.setPNames(new String[]{"freq"});
    for(int sn=1;sn<=ns;sn++){frozen.setU(sn,old[sn-1]);frozen.setUImag(sn,imag[sn-1]);frozen.setPVals(sn,new double[]{freqs[sn-1]});}
    System.out.println("CREATE_SOLUTION_BEGIN="+wavelength+","+alpha+",study="+frozen.study()+",features="+Arrays.toString(frozen.feature().tags()));System.out.flush();
    frozen.createSolution();
    System.out.println("CREATE_SOLUTION_RETURNED="+wavelength+","+alpha+",size="+Arrays.toString(frozen.getSize()));System.out.flush();
    sameMap(frozen);
    for(int sn=1;sn<=ns;sn++){double[] u=frozen.getU(sn,"Sol");for(int k=0;k<INDEX.length;k++)req(Math.abs(u[INDEX[k]]-(seed[k]+alpha*dir[k]))<READBACK_TOL,"Stored perturbation readback mismatch");}
    m.component("comp1").common("cvf1").set("initialValue","withsol('probeSeed',comp1.theta_c)");
    m.study("probeStudy").feature("freq").set("plist","c_const/"+wavelength+"[nm]");
    // New sequence for every evaluation; neither old MMA state nor prior Fsens is reused.
    if(Arrays.asList(m.sol().tags()).contains("probeSol")){
      for(String d:m.result().dataset().tags())if("Solution".equals(m.result().dataset(d).getType())&&"probeSol".equals(m.result().dataset(d).getString("solution")))m.result().dataset().remove(d);
      m.sol().remove("probeSol");
    }
    Set<String> before=new HashSet<String>(Arrays.asList(m.sol().tags()));m.study("probeStudy").createAutoSequences("sol");String active=null;
    for(String s:m.sol().tags())if(!before.contains(s)){req(active==null,"Multiple fresh sequences; inspect metadata");active=s;}
    req(active!=null,"No fresh sensitivity sequence");m.sol(active).tag("probeSol");SolverSequence s=m.sol("probeSol");
    for(String f:s.feature().tags()){configure(s.feature(f),"probeSol/"+f);if(!TREE_DUMPED)dump(s.feature(f),"probeSol/"+f);}
    TREE_DUMPED=true;
    System.out.println("EVALUATION_BEGIN="+wavelength+","+alpha);s.runAll();
    req(s.getSize()[1]==1,"Unexpected frequency/sensitivity solution indexing");int sn=s.getDefaultSolnum();sameMap(s);
    double[] u=s.getU(sn,"Sol");double err=0;
    for(int k=0;k<INDEX.length;k++)err=Math.max(err,Math.abs(u[INDEX[k]]-(seed[k]+alpha*dir[k])));
    req(err<READBACK_TOL,"Fresh primal controls changed or split-component mapping unknown: max_error="+err);
    System.out.println("SEED_READBACK="+wavelength+","+alpha+",max_error="+err);
    double j=global(m,dataset(m,"probeSol"),objective),w=global(m,dataset(m,"probeSol"),"c_const/freq/1[nm]");req(Math.abs(w-wavelength)<1e-6,"Frequency readback mismatch");
    req(s.getNU("Fsens")==1,"Unknown objective Fsens layout; expected one functional");double[] gradient=s.getU(sn,"Fsens",1);
    req(gradient.length==u.length,"Unknown Fsens vector layout; refuse assumed mapping");
    double[] gradientImag=s.isRealU(sn,"Fsens",1)?new double[gradient.length]:s.getUImag(sn,"Fsens",1);
    req(gradientImag.length==gradient.length,"Unknown Fsens imaginary-vector layout");
    double dot=0,maxMappedImag=0;
    for(int k=0;k<INDEX.length;k++){
      int p=INDEX[k];req(Double.isFinite(gradient[p]),"Nonfinite mapped CVF Fsens at "+p);
      req(Double.isFinite(gradientImag[p])&&Math.abs(gradientImag[p])<=1e-12,"Mapped CVF Fsens has nonzero/unknown imaginary part at "+p);
      maxMappedImag=Math.max(maxMappedImag,Math.abs(gradientImag[p]));
      if(alpha==0)System.out.printf(Locale.US,"CVF_GRADIENT=%.8f,%d,%.17g,%.17g,%.17g%n",wavelength,p,seed[k],dir[k],gradient[p]);
      dot+=gradient[p]*dir[k]; // actual discrete-vector contraction, NO area factor
    }
    System.out.printf(Locale.US,"OBSERVATION=%.8f,%.17g,%.17g,%.17g,mapped_fsens_max_imag=%.17g%n",wavelength,alpha,j,dot,maxMappedImag);return new double[]{j,dot};
  }
  public static Model run()throws Exception{
    Model m=ModelUtil.load("CvfGradient",INPUT);m.modelPath(OUTPUT);
    req("shdisc".equals(m.component("comp1").common("cvf1").getString("shapeFunctionType"))&&"0".equals(m.component("comp1").common("cvf1").getString("order")),"Expected elementwise-constant CVF");
    req("theta_c".equals(m.component("comp1").common("cvf1").getString("name")),"CVF name mismatch");
    req(Math.abs(m.param().evaluate("beta")-8)<1e-12,"Input must be beta8 endpoint seed");
    req(Math.abs(m.param().evaluate("gate_weight")-10)<1e-12,"Weight10 contract mismatch");
    String objective=m.study("std1").feature("topo").getStringMatrix("optobj")[0][0];
    req(objective.contains("sqrt(4*")&&objective.contains("1e-8")&&objective.contains("comp1.modal_a3")&&objective.contains("comp1.modal_a4"),"Expected state_floor + PML modal objective");
    req(m.component("comp1").physics("ewfd").feature("port1").getBoolean("PortSlit"),"PML slit port contract mismatch");
    req(m.study("std1").feature("freq").getString("plist").equals("c_const/1580[nm] c_const/1565[nm] c_const/1550[nm] c_const/1536.61[nm] c_const/1520[nm]"),"Five-frequency checkpoint contract mismatch");
    SolverSequence original=m.sol("sol1");INDEX=controlIndices(original);COORD=controlCoords(original,INDEX);double[] all=original.getU(original.getDefaultSolnum(),"Sol"),seed=new double[INDEX.length],dir=new double[INDEX.length];
    double maximum=0;int supported=0;
    for(int k=0;k<INDEX.length;k++){
      seed[k]=all[INDEX[k]];req(seed[k]>=-BOUND_TOL&&seed[k]<=1+BOUND_TOL,"CVF stored component outside legacy bounds");
      if(seed[k]>BOUND_TOL&&seed[k]<1-BOUND_TOL){dir[k]=Math.sin(2*Math.PI*COORD[0][k]/(1.3e-6))+0.37*Math.cos(2*Math.PI*COORD[1][k]/(1.3e-6));maximum=Math.max(maximum,Math.abs(dir[k]));supported++;}
    }
    req(supported>0&&maximum>0,"No feasible interior direction");
    for(int k=0;k<INDEX.length;k++){
      dir[k]/=maximum;
      if(seed[k]-H*Math.abs(dir[k])<=BOUND_TOL||seed[k]+H*Math.abs(dir[k])>=1-BOUND_TOL)dir[k]=0; // zero, never clip
      System.out.printf(Locale.US,"DIRECTION=%d,%.17g,%.17g,%.17g,%.17g%n",INDEX[k],COORD[0][k],COORD[1][k],seed[k],dir[k]);
    }
    double norm=0;for(double d:dir)norm+=d*d;req(norm>0,"Direction became zero");
    for(int sn=1;sn<=original.getSize()[1];sn++){double[] u=original.getU(sn,"Sol");for(int k=0;k<INDEX.length;k++)req(Math.abs(u[INDEX[k]]-seed[k])<READBACK_TOL,"Checkpoint controls differ across frequency");}
    original.copySolution("probeSeed");
    // copySolution copies data only (not features/study association). The
    // documented study(String) associates this data holder without attach(),
    // which would replace the study's attached executable sequence.
    req("std1".equals(original.study()),"Checkpoint solver study association mismatch");
    m.sol("probeSeed").study("std1");
    req("std1".equals(m.sol("probeSeed").study()),"Seed study association readback failed");
    req(!m.sol("probeSeed").isAttached(),"Seed data holder unexpectedly attached for execution");
    // Study association is not the equation-compilation problem definition.
    // A minimal documented StudyStep defines the checkpoint Frequency problem
    // for createSolution, with the original split complex representation.
    m.sol("probeSeed").create("seedStep","StudyStep");
    m.sol("probeSeed").feature("seedStep").set("study","std1");
    m.sol("probeSeed").feature("seedStep").set("studystep","freq");
    m.sol("probeSeed").feature("seedStep").set("splitcomplex",true);
    req("std1".equals(m.sol("probeSeed").feature("seedStep").getString("study"))&&"freq".equals(m.sol("probeSeed").feature("seedStep").getString("studystep"))&&m.sol("probeSeed").feature("seedStep").getBoolean("splitcomplex"),"Seed StudyStep readback failed");
    sameMap(m.sol("probeSeed"));
    System.out.println("SEED_STUDY_ASSOCIATION=std1,attached=false,StudyStep=std1/freq,splitcomplex=true");
    m.param().set("beta","16");
    m.study().create("probeStudy");m.study("probeStudy").create("freq","Frequency");m.study("probeStudy").feature("freq").set("useparam","off");
    m.study("probeStudy").create("sens","Sensitivity");m.study("probeStudy").feature("sens").set("controlVariableActive",new String[]{"on"});
    m.study("probeStudy").feature("sens").set("pname",new String[]{});m.study("probeStudy").feature("sens").set("optobj",new String[]{objective});m.study("probeStudy").feature("sens").set("gradientMethod","adjoint");
    req(Arrays.equals(m.study("probeStudy").feature("sens").getStringArray("controlVariableActive"),new String[]{"on"}),"CVF sensitivity activation readback failed");
    System.out.println("LEGACY_COMPLEX_CVF_RETAINED=true;NO_OPTIMIZER_UPDATES=true;NO_REMESH=true;BETA=16;OBJECTIVE="+objective);
    double[][] values=new double[WL.length][5];double[] dots=new double[WL.length];double[] steps={0,H,-H,H/2,-H/2};
    for(int i=0;i<WL.length;i++){
      for(int a=0;a<5;a++){double[] o=evaluate(m,seed,dir,steps[a],WL[i],objective);values[i][a]=o[0];if(a==0)dots[i]=o[1];}
      for(int q=0;q<2;q++){double h=H/Math.pow(2,q),fd=(values[i][1+2*q]-values[i][2+2*q])/(2*h),scale=Math.max(1e-10,Math.max(Math.abs(fd),Math.abs(dots[i])));
        System.out.printf(Locale.US,"COMPARISON=%.8f,%.17g,%.17g,%.17g,%.17g%n",WL[i],h,dots[i],fd,Math.abs(fd-dots[i])/scale);}
      System.out.println("WAVELENGTH_DIAGNOSTIC_COMPLETE="+WL[i]);System.out.flush();
    }
    double[] mins=new double[5];Arrays.fill(mins,Double.POSITIVE_INFINITY);int active=-1;double next=Double.POSITIVE_INFINITY;
    for(int i=0;i<WL.length;i++){for(int a=0;a<5;a++)mins[a]=Math.min(mins[a],values[i][a]);if(active<0||values[i][0]<values[active][0])active=i;}
    for(int i=0;i<WL.length;i++)if(i!=active)next=Math.min(next,values[i][0]);
    double tieTol=1e-9,gPlus=Double.POSITIVE_INFINITY,gMinus=Double.NEGATIVE_INFINITY;
    for(int i=0;i<WL.length;i++)if(values[i][0]-mins[0]<=tieTol){gPlus=Math.min(gPlus,dots[i]);gMinus=Math.max(gMinus,dots[i]);}
    System.out.printf(Locale.US,"MIN_ACTIVE=%.8f,%.17g,gap=%.17g,right_derivative=%.17g,left_derivative=%.17g,tie_tol=%.17g%n",WL[active],mins[0],next-mins[0],gPlus,gMinus,tieTol);
    for(int q=0;q<2;q++){double h=H/Math.pow(2,q),central=(mins[1+2*q]-mins[2+2*q])/(2*h);
      System.out.printf(Locale.US,"MIN_FD=%.17g,central=%.17g,right=%.17g,left=%.17g,central_expected=%.17g%n",h,central,(mins[1+2*q]-mins[0])/h,(mins[0]-mins[2+2*q])/h,(gPlus+gMinus)/2);}
    System.out.println("DIAGNOSTIC_COMPLETE=true;FIVE_FREQUENCY_COMPLETE="+(WL.length==5)+";NO_PERFORMANCE_ACCEPTANCE=true");return m;
  }
}
