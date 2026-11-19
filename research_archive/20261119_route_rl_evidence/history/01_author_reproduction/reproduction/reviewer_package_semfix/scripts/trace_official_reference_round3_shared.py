"""Build a separate pinned Java reference with optional bounded event logging."""
from pathlib import Path
import difflib,json,re,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'build/round3_reference';out.mkdir(parents=True,exist_ok=True)
src=out/'src';src.mkdir(exist_ok=True);patch=[]
for path in sorted((ROOT/'external/LRPHSD/code/TSALNS').glob('*.java')):
    old=path.read_text();new=old.replace('new Random()','ReplayRandom.RNG').replace('Math.random()','ReplayRandom.RNG.nextDouble()')
    new=re.sub(r'Collections\.shuffle\((\w+)\)',r'Collections.shuffle(\1,ReplayRandom.RNG)',new)
    if path.name=='Main.java':
        new=new.replace('String filePath = "PATH";','String filePath = System.getProperty("repro.instance");')
        new=new.replace('private static final int MAX_ITERATIONS = 500;','private static final int MAX_ITERATIONS = Integer.getInteger("repro.outer",500);')
        new=new.replace('iter < MAX_ITERATIONS;','iter < MAX_ITERATIONS && ReplayRandom.inBudget();')
        new=new.replace('i < 100;','i < Integer.getInteger("repro.local",100) && ReplayRandom.inBudget();')
        new=new.replace('int[] stationTypes = new int[stationNodes.length];','ReplayRandom.start();\n        int[] stationTypes = new int[stationNodes.length];')
        new=new.replace('double temperature = INITIAL_TEMPERATURE;', 'ReferenceRecorder.save(bestSolution1,targetNodes,stationNodes,bestCost);\n        Round3Trace.event("initial",0,-1,stationTypes,initRoute,"");\n        double temperature = INITIAL_TEMPERATURE;')
        new=new.replace('int[] newStationType = LocationOperator.applyRandomNeighborhood(currentSolution.getStationTypes());','int[] newStationType = LocationOperator.applyRandomNeighborhood(currentSolution.getStationTypes());\n            Round3Trace.event("location",iter,-1,newStationType,currentRoute,"");')
        new=new.replace('ALNSSolver solver = new ALNSSolver();','Round3Trace.event("local_end",iter,-1,newStationType,newRoutes,"");\n            ALNSSolver solver = new ALNSSolver();')
        needle='''                }
            }


            Round3Trace.event("local_end"'''
        replacement='''                }
                Round3Trace.event("local",i,operator,newStationType,newRoutes,"");
            }


            Round3Trace.event("local_end"'''
        assert needle in new
        new=new.replace(needle,replacement)
        new=new.replace('temperature *= COOLING_RATE;', 'ReferenceRecorder.save(bestSolution1,targetNodes,stationNodes,bestCost);\n            Round3Trace.event("outer_end",iter,-1,currentStationType,currentRoute,"\\\"current_cost\\\":"+currentCost+",\\\"best_cost\\\":"+bestCost+",\\\"temperature\\\":"+temperature);\n            temperature *= COOLING_RATE;')
        new=new.replace('System.out.println("--------------------Final results-------------------");','Round3Trace.event("final",MAX_ITERATIONS,-1,bestSolution1.getStationTypes(),bestSolution1.getNodeMatrix(),"\\\"best_cost\\\":"+bestCost+",\\\"budget_alive\\\":"+ReplayRandom.inBudget());\n        System.out.println("--------------------Final results-------------------");')
        new=new.replace('double latestTime = Check.calculateLatestTime(', 'Round3Trace.saveMetrics();\n        double latestTime = Check.calculateLatestTime(')
    elif path.name=='ALNSSolver.java':
        new=new.replace('private int maxIterations = 5000;','private int maxIterations = Integer.getInteger("repro.alns",5000);')
        new=new.replace('temperature > finalTemp;','temperature > finalTemp && ReplayRandom.inBudget();')
        new=new.replace('Math.min(5.0,','Math.min(Double.parseDouble(System.getProperty("repro.weight_upper","5.0")),')
        new=new.replace('// 3. Apply repair operator','Round3Trace.event("destroy",iter,destroyIdx,stationTypes,destroyResult.newRoutes,"\\\"repair_op\\\":"+repairIdx+",\\\"removed\\\":"+Round3Trace.ids(destroyResult.removedNodes));\n            // 3. Apply repair operator')
        new=new.replace('// 5. Update solution','Round3Trace.event("repair",iter,repairIdx,stationTypes,newRoute,"\\\"accepted\\\":"+accepted+",\\\"temperature\\\":"+temperature+",\\\"weights_d\\\":"+Arrays.toString(destroyWeights)+",\\\"weights_r\\\":"+Arrays.toString(repairWeights)+",\\\"scores_d\\\":"+Arrays.toString(destroyScores));\n            // 5. Update solution')
        new=new.replace('double total = 0;','Round3Trace.evaluations++;\n        double total = 0;')
    elif path.name=='Check.java':
        # Count only actual algorithm full-objective calls, not trace geometry.
        signature=new.index('public static double calculateTotalCost(')
        brace=new.index('{',signature)
        new=new[:brace+1]+'\n        Round3Trace.evaluations++;'+new[brace+1:]
    elif path.name=='RoutingOperator.java':
        new=new.replace('return new ArrayList<>(removed);','List<Node> ordered = new ArrayList<>(removed);\n        if (System.getProperty("repro.removed_order","native").equals("sorted_id")) ordered.sort(Comparator.comparingInt(Node::getNodeNo));\n        return ordered;')
    (src/path.name).write_text(new)
    patch.extend(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='pinned/'+path.name,tofile='round3/'+path.name))
for name in ['ReferenceRecorder.java','Round3Trace.java','OperationProbe.java']:
    shutil.copyfile(ROOT/'scripts/java'/name,src/name)
shutil.copyfile(ROOT/'scripts/java/Round3ReplayRandom.java.txt',src/'ReplayRandom.java')
classes=out/'classes';classes.mkdir(exist_ok=True)
home=Path((ROOT/'.runtime/JAVA_HOME.txt').read_text().strip())
run=subprocess.run([str(home/'bin/javac'),'-encoding','UTF-8','-d',str(classes),*[str(p) for p in src.glob('*.java')]],capture_output=True,text=True)
log=ROOT/'results/round3_differential';log.mkdir(parents=True,exist_ok=True)
(log/'reference_patch.diff').write_text(''.join(patch));(log/'compile.log').write_text(run.stdout+run.stderr)
print(run.stdout+run.stderr,end='');print('ROUND3_REFERENCE_BUILD_EXIT='+str(run.returncode))
raise SystemExit(run.returncode)
