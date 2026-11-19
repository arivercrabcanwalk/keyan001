package test1;

import java.util.ArrayList;
import java.util.List;

public final class EmptyStationRepairProbe {
    private static final double SPEED = 900.0;
    private static final double FLIGHT_ENERGY = 0.018;
    private static final double SMALL_BATTERY = 0.81;
    private static final double LARGE_BATTERY = 1.0;
    private static final double SMALL_TIME = 480.0;
    private static final double LARGE_TIME = 600.0;
    private static final double SMALL_RADIUS = 4000.0;
    private static final double LARGE_RADIUS = 5000.0;

    private static List<List<List<List<Node>>>> emptyRoutes() {
        List<List<List<Node>>> stationRoutes = new ArrayList<>();
        stationRoutes.add(new ArrayList<>());
        stationRoutes.add(new ArrayList<>());
        List<List<List<List<Node>>>> routes = new ArrayList<>();
        routes.add(stationRoutes);
        return routes;
    }

    private static List<List<List<List<Node>>>> repair(int kind, int op,
            Node target, Node station, int[] stationTypes, Node[] targetNodes,
            Node[] stationNodes) {
        List<List<List<List<Node>>>> routes = emptyRoutes();
        List<Node> removed = List.of(target);
        if (op == 2) {
            return RoutingOperator.loadBalancingInsertion(routes, stationTypes, removed,
                    LARGE_BATTERY, SMALL_BATTERY, SPEED, FLIGHT_ENERGY,
                    LARGE_TIME, SMALL_TIME, SMALL_RADIUS, LARGE_RADIUS, stationNodes);
        }
        return RoutingOperator.prioritizedInsertion(routes, stationTypes, removed,
                LARGE_BATTERY, SMALL_BATTERY, SPEED, FLIGHT_ENERGY,
                LARGE_TIME, SMALL_TIME, SMALL_RADIUS, LARGE_RADIUS, stationNodes);
    }

    private static void run(int kind, int op) {
        // The reference time evaluator reserves node id 0 for route separators.
        Node station = new Node(100, 0.0, 0.0, 0.0, 0.0);
        Node target = new Node(1, 100.0, 0.0, 0.01, 2.0);
        Node[] targets = {target};
        Node[] stations = {station};
        int[] stationTypes = {kind};
        Round4Guard.init(targets, stations);

        List<List<List<List<Node>>>> repaired = repair(kind, op, target, station,
                stationTypes, targets, stations);
        double candidateCost = Check.calculateTotalCost(repaired, stationTypes,
                30.4, 22.8, 8.0, 5.0, 0.5, SPEED);
        boolean sourceGuard = Round4Guard.valid(stationTypes, repaired);
        double currentCost = candidateCost;
        boolean equalCostAccept = candidateCost < currentCost
                || ReplayRandom.RNG.nextDouble()
                < Math.exp((currentCost - candidateCost) / 1000.0);
        boolean finalAccept = equalCostAccept && sourceGuard;
        String encoded = ReferenceRecorder.encode(stationTypes, repaired,
                targets, stations, candidateCost);
        System.out.println("JAVA kind=" + kind + " op=" + op
                + " source_guard=" + sourceGuard
                + " equal_cost_accept_before_guard=" + equalCostAccept
                + " equal_cost_accept_after_guard=" + finalAccept
                + " result=" + encoded);
    }

    private static void runNearestMultiPendingRollback() {
        Node smallStation = new Node(10, 0.0, 0.0, 0.0, 0.0);
        Node largeStation = new Node(20, 1000.0, 0.0, 0.0, 0.0);
        Node badFirst = new Node(1, 100.0, 0.0, 0.90, 2.0);
        Node existingSmall = new Node(2, 50.0, 0.0, 0.12, 479.0);
        Node existingLarge = new Node(3, 1000.0, 0.0, 0.31, 1.0);
        Node goodSecond = new Node(4, 1000.0, 0.0, 0.01, 1.0);
        Node[] targets = {badFirst, existingSmall, existingLarge, goodSecond};
        Node[] stations = {smallStation, largeStation};
        int[] stationTypes = {1, 2};

        List<List<List<List<Node>>>> routes = new ArrayList<>();
        List<List<List<Node>>> smallRoutes = new ArrayList<>();
        smallRoutes.add(new ArrayList<>());
        smallRoutes.add(new ArrayList<>());
        smallRoutes.get(1).add(new ArrayList<>(List.of(smallStation, existingSmall, smallStation)));
        routes.add(smallRoutes);
        List<List<List<Node>>> largeRoutes = new ArrayList<>();
        largeRoutes.add(new ArrayList<>());
        largeRoutes.add(new ArrayList<>());
        largeRoutes.get(0).add(new ArrayList<>(List.of(largeStation, existingLarge, largeStation)));
        routes.add(largeRoutes);

        Round4Guard.init(targets, stations);
        List<List<List<List<Node>>>> repaired = RoutingOperator.nearestInsertion(
                routes, stationTypes, List.of(badFirst, goodSecond),
                LARGE_BATTERY, SMALL_BATTERY, SPEED, FLIGHT_ENERGY,
                LARGE_TIME, SMALL_TIME, SMALL_RADIUS, LARGE_RADIUS, stations);
        List<Integer> assigned = new ArrayList<>();
        for (List<List<List<Node>>> station : repaired) {
            for (List<List<Node>> drone : station) {
                for (List<Node> trip : drone) {
                    for (Node node : trip) {
                        if (node.getNodeNo() != 10 && node.getNodeNo() != 20) {
                            assigned.add(node.getNodeNo());
                        }
                    }
                }
            }
        }
        System.out.println("JAVA op=0 pending=[1,4] returned_original=" + (repaired == routes)
                + " assigned_targets=" + assigned);
    }

    public static void main(String[] args) {
        int kind = args.length == 0 ? 2 : Integer.parseInt(args[0]);
        if (kind != 1 && kind != 2) throw new IllegalArgumentException("kind must be 1 or 2");
        run(kind, 2);
        run(kind, 3);
        if (kind == 2) runNearestMultiPendingRollback();
    }
}
