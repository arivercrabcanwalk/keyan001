package test1;
import java.util.*;
public final class GreedyProbe {
 public static void main(String[] args) {
  for(String file:args) {
   try {
    List<Node> all=FileReaderUtil.readNodesFromFile(file);
    Node[] targets=all.stream().filter(n->n.getServiceEnergy()>0).toArray(Node[]::new);
    Node[] stations=all.stream().filter(n->n.getServiceEnergy()==0).toArray(Node[]::new);
    int[] types=Init.stationSet(targets,stations,Main.SMALL_RADIUS,Main.LARGE_RADIUS);
    List<List<Node>> allocated=Init.allocateTargetsToStations(targets,stations,types,Main.SMALL_RADIUS,Main.LARGE_RADIUS);
    List<List<List<List<Node>>>> routes=Init.generateRoutes1(stations,types,allocated,Main.SMALL_DRONE_BATTERY,Main.LARGE_DRONE_BATTERY,Main.LARGE_DRONE_CONS,Main.SMALL_STATION_TIME,Main.LARGE_STATION_TIME,Main.DRONE_SPEED);
    double cost=Check.calculateTotalCost(routes,types,Main.LARGE_SITE_COST,Main.SMALL_SITE_COST,Main.LARGE_DRONE_COST,Main.SMALL_DRONE_COST,Main.FLIGHT_COST_PER_MIN,Main.DRONE_SPEED);
    System.out.println("REFERENCE_JSON="+new java.io.File(file).getName()+"\t"+ReferenceRecorder.encode(types,routes,targets,stations,cost));
   } catch(Exception e){System.out.println("REFERENCE_ERROR="+new java.io.File(file).getName()+"\t"+e.getClass().getName()+":"+e.getMessage());}
  }
 }
}
