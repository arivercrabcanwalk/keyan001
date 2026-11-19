"""Patch only isolated copies; RNG edits refer to original source line IDs."""
import re
def rng_source(old,name,mode):
    if mode=='conditional':return old.replace('new Random()','ReplayRandom.RNG').replace('Math.random()','ReplayRandom.RNG.nextDouble()')
    if mode=='shared':return old.replace('new Random()','ReplayRandom.shared()').replace('Math.random()','ReplayRandom.shared().nextDouble()')
    if mode=='raw':return old
    lines=[]
    for number,line in enumerate(old.splitlines(True),1):
        line=line.replace('new Random()',f'ReplayRandom.create("{name}:{number}")').replace('Math.random()','ReplayRandom.math().nextDouble()')
        lines.append(line)
    return ''.join(lines)

def patch(new,name,mode):
    if mode=='conditional':return new
    def entry(text,signature,insert):
        offset=text.index(signature);brace=text.index('{',offset)
        return text[:brace+1]+'\n'+insert+'\n'+text[brace+1:]
    if name=='Main.java':
        new=new.replace('long startTime =', 'Round4Audit.mark("main_enter");\n        long startTime =')
        new=new.replace('Node[] stationNodes = stationNodesList.toArray(new Node[0]);','Node[] stationNodes = stationNodesList.toArray(new Node[0]);\n        Round4Audit.init(targetNodes,stationNodes);')
        new=new.replace('double temperature = INITIAL_TEMPERATURE;', 'if(Round4Audit.guarded() && !Round4Audit.valid(stationTypes,initRoute))throw new IllegalStateException("invalid initializer");\n        Round4Audit.mark("greedy_end");Round4Audit.mark("search_start");\n        double temperature = INITIAL_TEMPERATURE;')
        new=new.replace('int[] newStationType = LocationOperator.applyRandomNeighborhood', 'Round4Audit.enter("location");Round4Audit.inc("candidate_generated_location");\n            int[] newStationType = LocationOperator.applyRandomNeighborhood')
        new=new.replace('Round3Trace.event("location",','Round4Audit.leave("location");\n            Round3Trace.event("location",')
        new=new.replace('if (!LocationOperator.isFeasible(targetNodes, stationNodes, newStationType, SMALL_RADIUS, LARGE_RADIUS)) {','if (!LocationOperator.isFeasible(targetNodes, stationNodes, newStationType, SMALL_RADIUS, LARGE_RADIUS)) {\n                Round4Audit.inc("location_rejected");')
        new=new.replace('boolean isSolutionF=', 'Round4Audit.inc("source_feasibility_checkpoints");\n            boolean isSolutionF=')
        new=new.replace('if(!isSolutionF){','if(!isSolutionF){Round4Audit.inc("location_rejected");')
        new=new.replace('for (int i = 0; i < Integer.getInteger', 'Round4Audit.enter("local");\n            for (int i = 0; i < Integer.getInteger')
        new=new.replace('int operator = random.nextInt(5);','Round4Audit.inc("candidate_generated_local");\n                int operator = random.nextInt(5);')
        new=new.replace('Round3Trace.event("local_end",', 'Round4Audit.leave("local");\n            Round3Trace.event("local_end",')
        new=new.replace('double newCost = Check.calculateTotalCost', 'Round4Audit.inc("candidate_generated_outer");\n            double newCost = Check.calculateTotalCost')
        new=new.replace('if (acceptanceProbability > random.nextDouble()) {','boolean outerAccepted=acceptanceProbability > random.nextDouble();\n            if(Round4Audit.guarded()&&!Round4Audit.valid(newStationType,newRoutes))outerAccepted=false;\n            Round4Audit.outer(outerAccepted);\n            if (outerAccepted) {')
        new=new.replace('bestCost = currentCost;\n                }','bestCost = currentCost;Round4Audit.inc("best_improvements_outer");\n                }')
        new=new.replace('Round3Trace.event("final",', 'Round4Audit.freeze();\n        Round3Trace.event("final",')
        new=new.replace('Round3Trace.saveMetrics();','Round4Audit.save();')
    if name=='ALNSSolver.java':
        new=new.replace('// 2. Apply destroy operator','Round4Audit.enter("destroy");\n            // 2. Apply destroy operator')
        new=new.replace('// 3. Apply repair operator','Round4Audit.leave("destroy");Round4Audit.enter("repair");\n            // 3. Apply repair operator')
        new=new.replace('// 4. Compute cost and improvement','Round4Audit.leave("repair");Round4Audit.repair(newRoute,destroyResult.newRoutes);\n            // 4. Compute cost and improvement')
        new=new.replace('double improvement = bestCost - newCost;', 'if(Round4Audit.guarded()&&!Round4Audit.valid(stationTypes,newRoute))accepted=false;\n            double improvement = bestCost - newCost;')
        new=new.replace('if (accepted) {','if (accepted) {Round4Audit.inc("candidate_accepted");Round4Audit.inc("alns_accepted");',1)
        new=new.replace('bestCost = newCost;', 'bestCost = newCost;Round4Audit.inc("best_improvements_alns");')
        new=entry(new,'private double calculateTotalCost(', 'Round4Audit.inc("route_set_objectives");')
    if name=='Check.java':
        for signature,key in [('public static double calculateTotalCost(','full_solution_objectives'),('public static double calculatePathTime(','route_time_api_calls'),('public static double calculatePathCost(','route_time_api_calls'),('public static double calculatePathEnergy(','route_energy_api_calls'),('public static boolean isOverallSolutionValid(','source_energy_query_api_requests'),('public static boolean checkStationOperation(','source_time_query_api_requests')]:
            new=entry(new,signature,f'Round4Audit.inc("{key}");')
    if name in ('Check.java','ALNSSolver.java'):
        signature='public static double calculateTotalCost(' if name=='Check.java' else 'private double calculateTotalCost('
        begin=new.index('{',new.index(signature));depth=1;end=begin+1
        while depth:
            if new[end]=='{':depth+=1
            elif new[end]=='}':depth-=1
            end+=1
        new=new[:begin+1]+'\nRound4Audit.enter("objective");try{'+new[begin+1:end-1]+'}finally{Round4Audit.leave("objective");}\n'+new[end-1:]
    if name=='Main.java':
        new=re.sub(r'(List<List<List<List<Node>>>> (?:route1|newRoutes) = Init.generateRoutes1\([\s\S]*?\);)',r'Round4Audit.enter("greedy");\n\1\nRound4Audit.leave("greedy");',new)
    return new
