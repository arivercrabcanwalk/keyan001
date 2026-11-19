package test1;
import java.util.*;
public final class Round4Guard {
    private static Node[] targets;
    private static Node[] stations;
    private static Map<Integer,Node> byId;
    private static final double SPEED=900.0;
    private static final double FLIGHT_ENERGY=0.018;
    private static final double LARGE_BATTERY=1.0;
    private static final double SMALL_BATTERY=0.81;
    private static final double SMALL_DURATION=480.0;
    private static final double LARGE_DURATION=600.0;
    private static final double SMALL_RADIUS=4000.0;
    private static final double LARGE_RADIUS=5000.0;
    private static final double EPS=1e-7;

    public static void init(Node[] targetNodes, Node[] stationNodes) {
        targets=targetNodes; stations=stationNodes; byId=new HashMap<>();
        for(Node n:targets) byId.put(n.getNodeNo(),n);
    }

    public static boolean valid(int[] types, List<List<List<List<Node>>>> paths) {
        if(targets==null || stations==null || byId==null) return false;
        if(types==null || paths==null || types.length!=stations.length || paths.size()!=stations.length) return false;
        Set<Integer> seen=new HashSet<>();
        for(int si=0;si<types.length;si++) {
            int kind=types[si];
            if(kind<0 || kind>2) return false;
            List<List<List<Node>>> ds=paths.get(si);
            if(ds==null || ds.size()>2) return false;
            if(kind==0) {
                for(List<List<Node>> drone:ds) for(List<Node> trip:drone)
                    if(trip.size()>2) return false;
                continue;
            }
            double[] work={0.0,0.0};
            for(int di=0;di<2;di++) {
                if(di>=ds.size()) continue;
                List<List<Node>> trips=ds.get(di);
                if(trips==null) return false;
                if(kind==1 && di==0) {
                    for(List<Node> trip:trips) if(trip.size()>2) return false;
                    continue;
                }
                double capacity=(kind==2 && di==0)?LARGE_BATTERY:SMALL_BATTERY;
                double radius=(kind==1)?SMALL_RADIUS:LARGE_RADIUS;
                for(List<Node> trip:trips) {
                    if(trip==null) return false;
                    if(trip.size()<=2) continue;
                    int stationId=stations[si].getNodeNo();
                    if(trip.get(0).getNodeNo()!=stationId ||
                       trip.get(trip.size()-1).getNodeNo()!=stationId) return false;
                    double flightTime=0.0,serviceTime=0.0,serviceEnergy=0.0;
                    for(int k=1;k<trip.size();k++) {
                        Node a=trip.get(k-1),b=trip.get(k);
                        flightTime+=Calculator.calculateTravelTime(a,b,SPEED);
                        if(k<trip.size()-1) {
                            Node target=byId.get(b.getNodeNo());
                            if(target==null || !seen.add(target.getNodeNo())) return false;
                            if(Calculator.calculateDistance(stations[si],target)>radius+EPS) return false;
                            serviceTime+=target.getServiceTime();
                            serviceEnergy+=target.getServiceEnergy();
                        }
                    }
                    // flightTime already includes every directed leg, including return.
                    double energy=flightTime*FLIGHT_ENERGY+serviceEnergy;
                    if(energy>capacity+EPS) return false;
                    work[di]+=flightTime+serviceTime;
                }
            }
            double limit=(kind==1)?SMALL_DURATION:LARGE_DURATION;
            for(int di=0;di<2;di++) {
                if(kind==1 && di==0) continue;
                if(work[di]>limit+EPS) return false;
            }
        }
        return seen.size()==targets.length;
    }
}
