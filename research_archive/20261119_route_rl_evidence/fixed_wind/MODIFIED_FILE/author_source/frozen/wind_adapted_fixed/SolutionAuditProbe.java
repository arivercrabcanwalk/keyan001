package test1;
import java.util.*;
import java.nio.file.*;
public final class SolutionAuditProbe {
 public static void main(String[] args) throws Exception {
  List<Node> all=FileReaderUtil.readNodesFromFile(args[0]);Map<Integer,Node> byID=new HashMap<>();for(Node n:all)byID.put(n.getNodeNo(),n);
  Node[] targets=all.stream().filter(n->n.getServiceEnergy()>0).toArray(Node[]::new);
  Node[] stations=all.stream().filter(n->n.getServiceEnergy()==0).toArray(Node[]::new);
  List<String> lines=Files.readAllLines(Path.of(args[1]));int[] types=Arrays.stream(lines.get(0).trim().split("\\s+")).mapToInt(Integer::parseInt).toArray();
  List<List<List<List<Node>>>> routes=new ArrayList<>();
  for(Node station:stations){List<List<List<Node>>> ds=new ArrayList<>();ds.add(new ArrayList<>());ds.add(new ArrayList<>());routes.add(ds);}
  for(String line:lines.subList(1,lines.size())){
   if(line.isBlank())continue;int[] q=Arrays.stream(line.trim().split("\\s+")).mapToInt(Integer::parseInt).toArray();int si=q[0],di=q[1];List<Node> trip=new ArrayList<>();trip.add(stations[si]);for(int k=2;k<q.length;k++)trip.add(byID.get(q[k]));trip.add(stations[si]);routes.get(si).get(di).add(trip);
  }
  double cost=Check.calculateTotalCost(routes,types,Main.LARGE_SITE_COST,Main.SMALL_SITE_COST,Main.LARGE_DRONE_COST,Main.SMALL_DRONE_COST,Main.FLIGHT_COST_PER_MIN,Main.DRONE_SPEED);
  boolean energy=Check.isOverallSolutionValid(routes,types,Main.LARGE_DRONE_BATTERY,Main.SMALL_DRONE_BATTERY,Main.DRONE_SPEED,Main.LARGE_DRONE_CONS);
  boolean time=Check.checkStationOperation(routes,Main.DRONE_SPEED,Main.LARGE_STATION_TIME,Main.SMALL_STATION_TIME,types);
  System.out.println("JAVA_CROSSCHECK={\"objective\":"+cost+",\"energy_valid\":"+energy+",\"cumulative_time_valid\":"+time+"}");
 }
}
