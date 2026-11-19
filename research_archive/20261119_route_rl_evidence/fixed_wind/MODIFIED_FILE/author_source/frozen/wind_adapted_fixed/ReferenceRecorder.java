package test1;
import java.util.*;
import java.nio.file.*;
public final class ReferenceRecorder {
    private static double last = Double.POSITIVE_INFINITY;
    public static String encode(int[] types, List<List<List<List<Node>>>> paths, Node[] targets, Node[] stations, double cost) {
        Set<Integer> targetIDs=new HashSet<>();Map<Integer,Node> nodes=new HashMap<>();
        for(Node n:targets){targetIDs.add(n.getNodeNo());nodes.put(n.getNodeNo(),n);}for(Node n:stations)nodes.put(n.getNodeNo(),n);
        List<String> issues=new ArrayList<>();StringBuilder routes=new StringBuilder("[");
        for(int si=0;si<types.length;si++){
            if(si>0)routes.append(',');routes.append('[');
            List<List<List<Node>>> ds=si<paths.size()?paths.get(si):Collections.emptyList();
            for(int di=0;di<2;di++){
                if(di>0)routes.append(',');routes.append('[');int count=0;
                if(di<ds.size())for(List<Node> trip:ds.get(di)){
                    if(trip.size()<=2)continue;
                    if(trip.get(0).getNodeNo()!=stations[si].getNodeNo() || trip.get(trip.size()-1).getNodeNo()!=stations[si].getNodeNo())issues.add("base_endpoints:"+si+":"+di);
                    if(count++>0)routes.append(',');routes.append('[');int nc=0;
                    for(int k=1;k<trip.size()-1;k++){
                        Node n=trip.get(k);Node original=nodes.get(n.getNodeNo());
                        if(original==null || !targetIDs.contains(n.getNodeNo()))issues.add("non_target:"+n.getNodeNo());
                        else if(Double.compare(n.getX(),original.getX())!=0 || Double.compare(n.getY(),original.getY())!=0 || Double.compare(n.getServiceEnergy(),original.getServiceEnergy())!=0 || Double.compare(n.getServiceTime(),original.getServiceTime())!=0)issues.add("node_attribute_mutation:"+n.getNodeNo());
                        if(nc++>0)routes.append(',');routes.append(n.getNodeNo());
                    }
                    routes.append(']');
                }
                routes.append(']');
            }
            routes.append(']');
        }
        routes.append(']');StringBuilder errors=new StringBuilder("[");for(int i=0;i<issues.size();i++){if(i>0)errors.append(',');errors.append('"').append(issues.get(i)).append('"');}errors.append(']');
        return "{\"station_types\":"+Arrays.toString(types)+",\"routes\":"+routes+",\"reference_reported_cost\":"+cost+",\"reference_integrity_issues\":"+errors+"}";
    }
    public static void saveFinal(Solution solution, Node[] targets, Node[] stations, double cost) {
        String output=System.getProperty("repro.output");if(output==null)return;
        if(!Double.isFinite(cost))throw new IllegalArgumentException("nonfinite final cost");
        try {Files.writeString(Path.of(output),encode(solution.getStationTypes(),solution.getNodeMatrix(),targets,stations,cost)+"\n");}
        catch(Exception e){throw new RuntimeException(e);}
    }
    public static void save(Solution solution, Node[] targets, Node[] stations, double cost) {
        String output=System.getProperty("repro.output");if(output==null || !Double.isFinite(cost) || cost>=last-1e-12)return;
        last=cost;
        try {Files.writeString(Path.of(output),encode(solution.getStationTypes(),solution.getNodeMatrix(),targets,stations,cost)+"\n");}
        catch(Exception e){throw new RuntimeException(e);}
    }
}
