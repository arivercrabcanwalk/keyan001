package test1;
import java.util.*;
import java.nio.file.*;
/** Read-only source rescoring of Recorder's complete witness, in a fresh JVM. */
public final class WitnessAuditMain {
    public static void main(String[] args) throws Exception {
        List<Node> all = FileReaderUtil.readNodesFromFile(args[0]);
        Map<Integer,Node> byID = new HashMap<>();
        for (Node n : all) byID.put(n.getNodeNo(), n);
        Node[] targets = all.stream().filter(n -> n.getServiceEnergy()>0).toArray(Node[]::new);
        Node[] stations = all.stream().filter(n -> n.getServiceEnergy()==0).toArray(Node[]::new);
        List<String> lines = Files.readAllLines(Path.of(args[1]));
        int[] types = Arrays.stream(lines.get(0).trim().split("\\s+")).mapToInt(Integer::parseInt).toArray();
        List<List<List<List<Node>>>> routes = new ArrayList<>();
        for (Node station : stations) {
            List<List<List<Node>>> drones = new ArrayList<>();
            drones.add(new ArrayList<>()); drones.add(new ArrayList<>()); routes.add(drones);
        }
        for (String line : lines.subList(1, lines.size())) {
            if (line.isBlank()) continue;
            int[] q = Arrays.stream(line.trim().split("\\s+")).mapToInt(Integer::parseInt).toArray();
            List<Node> trip = new ArrayList<>(); trip.add(stations[q[0]]);
            for (int k=2;k<q.length;k++) trip.add(byID.get(q[k]));
            trip.add(stations[q[0]]); routes.get(q[0]).get(q[1]).add(trip);
        }
        Round4Guard.init(targets, stations);
        boolean guard = Round4Guard.valid(types, routes);
        double cost = Check.calculateTotalCost(routes, types, Main.LARGE_SITE_COST, Main.SMALL_SITE_COST,
            Main.LARGE_DRONE_COST, Main.SMALL_DRONE_COST, Main.FLIGHT_COST_PER_MIN, Main.DRONE_SPEED);
        double latest = Check.calculateLatestTime(routes, Main.DRONE_SPEED);
        System.out.println("FULL_WITNESS_AUDIT={\"cost\":"+cost+",\"M_return\":"+latest+",\"guard\":"+guard+"}");
    }
}
