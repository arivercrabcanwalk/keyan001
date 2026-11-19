package test1;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.TreeSet;

public final class OperatorMatrixProbe {
    private static final double SPEED = 900.0;
    private static final double FE = 0.018;
    private static final double SMALL_BAT = 0.81;
    private static final double LARGE_BAT = 1.0;
    private static final double SMALL_TIME = 480.0;
    private static final double LARGE_TIME = 600.0;
    private static final double SMALL_RADIUS = 4000.0;
    private static final double LARGE_RADIUS = 5000.0;
    private static final double TIME_COST = 0.5;

    private static Node station(int id, double x) {
        return new Node(id, x, 0.0, 0.0, 0.0);
    }

    private static Node target(int id) {
        double[][] xy = {
                {100, 100}, {300, 300}, {100, 300}, {300, 100},
                {500, 200}, {700, 100}, {800, 300}, {900, 100},
                {1100, 200}, {1200, 100}, {1300, 300}, {1400, 100},
                {1500, 200}
        };
        return new Node(id, xy[id - 1][0], xy[id - 1][1], 0.01, 2.0);
    }

    private static List<Node> trip(Node depot, int... ids) {
        List<Node> path = new ArrayList<>();
        path.add(depot);
        for (int id : ids) path.add(target(id));
        path.add(depot);
        return path;
    }

    private static List<List<Node>> drone(Node depot, int[]... trips) {
        List<List<Node>> routes = new ArrayList<>();
        for (int[] ids : trips) routes.add(trip(depot, ids));
        return routes;
    }

    private static List<List<List<List<Node>>>> baseRoutes() {
        Node a = station(100, 0.0), b = station(101, 1000.0);
        List<List<List<List<Node>>>> routes = new ArrayList<>();
        List<List<List<Node>>> sa = new ArrayList<>();
        sa.add(drone(a, new int[]{1, 2, 3, 4}, new int[]{5}));
        sa.add(drone(a, new int[]{6, 7}));
        routes.add(sa);
        List<List<List<Node>>> sb = new ArrayList<>();
        sb.add(drone(b, new int[]{8, 9}, new int[]{10, 11}));
        sb.add(drone(b, new int[]{12, 13}));
        routes.add(sb);
        return routes;
    }

    private static List<List<List<List<Node>>>> repairTieRoutes() {
        Node a = station(100, 0.0);
        List<List<List<List<Node>>>> routes = new ArrayList<>();
        List<List<List<Node>>> s = new ArrayList<>();
        s.add(Arrays.asList(Arrays.asList(a,
                new Node(1, 100.0, 0.0, 0.01, 2.0), a), Arrays.asList(a,
                new Node(2, -100.0, 0.0, 0.01, 2.0), a)));
        s.add(Arrays.asList(Arrays.asList(a,
                new Node(4, 700.0, 200.0, 0.01, 2.0), a)));
        routes.add(s);
        return routes;
    }

    private static List<List<List<List<Node>>>> boundaryRoutes() {
        Node a = station(100, 0.0);
        List<List<List<List<Node>>>> routes = new ArrayList<>();
        List<List<List<Node>>> s = new ArrayList<>();
        s.add(drone(a, new int[]{1}));
        s.add(drone(a));
        routes.add(s);
        return routes;
    }

    private static String routeJson(int[] types, List<List<List<List<Node>>>> routes) {
        StringBuilder out = new StringBuilder("{\"types\":[");
        for (int i = 0; i < types.length; i++) {
            if (i > 0) out.append(',');
            out.append(types[i]);
        }
        out.append("],\"routes\":[");
        for (int si = 0; si < routes.size(); si++) {
            if (si > 0) out.append(',');
            out.append('[');
            List<List<List<Node>>> station = routes.get(si);
            for (int di = 0; di < station.size(); di++) {
                if (di > 0) out.append(',');
                out.append('[');
                List<List<Node>> drone = station.get(di);
                for (int ti = 0; ti < drone.size(); ti++) {
                    if (ti > 0) out.append(',');
                    out.append('[');
                    List<Node> path = drone.get(ti);
                    for (int pi = 1; pi < path.size() - 1; pi++) {
                        if (pi > 1) out.append(',');
                        out.append(path.get(pi).getNodeNo());
                    }
                    out.append(']');
                }
                out.append(']');
            }
            out.append(']');
        }
        return out.append("]}").toString();
    }

    private static TreeSet<Integer> targetSet(List<List<List<List<Node>>>> routes) {
        TreeSet<Integer> ids = new TreeSet<>();
        for (List<List<List<Node>>> station : routes)
            for (List<List<Node>> drone : station)
                for (List<Node> path : drone)
                    for (int i = 1; i < path.size() - 1; i++)
                        ids.add(path.get(i).getNodeNo());
        return ids;
    }

    private static Node pending(int id) {
        if (id == 14) return new Node(14, 600.0, 500.0, 0.01, 2.0);
        if (id == 15) return new Node(15, 0.0, 200.0, 0.01, 2.0);
        if (id == 16) return new Node(16, 900.0, 0.0, 0.964, 598.0);
        throw new IllegalArgumentException("pending target");
    }

    private static List<List<List<List<Node>>>> repair(int op,
            List<List<List<List<Node>>>> routes, int kind, List<Node> pending, Node[] stations) {
        int[] types = {kind};
        if (op == 0)
            return RoutingOperator.nearestInsertion(routes, types, pending, LARGE_BAT, SMALL_BAT,
                    SPEED, FE, LARGE_TIME, SMALL_TIME, SMALL_RADIUS, LARGE_RADIUS, stations);
        if (op == 1)
            return RoutingOperator.minimumRegretInsertion(routes, types, pending, LARGE_BAT, SMALL_BAT,
                    SPEED, FE, LARGE_TIME, SMALL_TIME, SMALL_RADIUS, LARGE_RADIUS, stations);
        if (op == 2)
            return RoutingOperator.loadBalancingInsertion(routes, types, pending, LARGE_BAT, SMALL_BAT,
                    SPEED, FE, LARGE_TIME, SMALL_TIME, SMALL_RADIUS, LARGE_RADIUS, stations);
        return RoutingOperator.prioritizedInsertion(routes, types, pending, LARGE_BAT, SMALL_BAT,
                SPEED, FE, LARGE_TIME, SMALL_TIME, SMALL_RADIUS, LARGE_RADIUS, stations);
    }

    private static String sentinel() {
        return Double.toHexString(ReplayRandom.RNG.nextDouble());
    }

    private static void emit(String kind, int seed, int[] types,
            List<List<List<List<Node>>>> routes, List<Integer> removed) {
        StringBuilder out = new StringBuilder("{\"case\":\"").append(kind)
                .append("\",\"seed\":").append(seed).append(",\"state\":")
                .append(routeJson(types, routes));
        if (removed != null) out.append(",\"removed\":").append(removed.toString());
        out.append(",\"rng_after\":\"").append(sentinel()).append("\"}");
        System.out.println(out);
    }

    private static void emitLocation(int op, int seed) {
        int[] types = {1, 2, 0, 1, 0};
        ReplayRandom.RNG.setSeed(seed);
        int[] result;
        switch (op) {
            case 0: result = LocationOperator.randomSwapStationTypes(types); break;
            case 1: result = LocationOperator.upgradeStationType(types); break;
            case 2: result = LocationOperator.downgradeStationType(types); break;
            default: result = LocationOperator.closeStation(types); break;
        }
        emit("location" + op, seed, result, new ArrayList<>(), null);
    }

    private static void emitLocal(int op, int seed) {
        int[] types = {2, 2};
        Node[] stations = {station(100, 0.0), station(101, 1000.0)};
        List<List<List<List<Node>>>> source = baseRoutes();
        ReplayRandom.RNG.setSeed(seed);
        List<List<List<List<Node>>>> result;
        switch (op) {
            case 0: result = RoutingOperator.swap1(source, types, LARGE_BAT, SMALL_BAT, SPEED, FE); break;
            case 1: result = RoutingOperator.swap2(source, types, LARGE_BAT, SMALL_BAT, SPEED, FE); break;
            case 2: result = RoutingOperator.swap3(source, types, LARGE_BAT, SMALL_BAT, SPEED, FE,
                    LARGE_TIME, SMALL_TIME); break;
            case 3: result = RoutingOperator.swap4(source, types, LARGE_BAT, SMALL_BAT, SPEED, FE,
                    LARGE_TIME, SMALL_TIME); break;
            default: result = RoutingOperator.twoOptOperator(source); break;
        }
        emit("local" + op, seed, types, result, null);
    }

    private static void emitDestroy(int op, int seed) {
        int[] types = {2, 2};
        Node[] stations = {station(100, 0.0), station(101, 1000.0)};
        List<List<List<List<Node>>>> source = baseRoutes();
        TreeSet<Integer> before = targetSet(source);
        ReplayRandom.RNG.setSeed(seed);
        List<List<List<List<Node>>>> result;
        switch (op) {
            case 0: result = RoutingOperator.greedyRemoveMostExpensivePoint(source, types, LARGE_BAT,
                    SMALL_BAT, SPEED, FE, LARGE_TIME, SMALL_TIME); break;
            case 1: result = RoutingOperator.probabilisticGreedyRemove(source, 0.7); break;
            case 2: result = RoutingOperator.randomRemoveOnePoint(source, types, LARGE_BAT,
                    SMALL_BAT, SPEED, FE, LARGE_TIME, SMALL_TIME); break;
            default: result = RoutingOperator.removeSimilarCustomers(source, types, SMALL_RADIUS,
                    LARGE_RADIUS, stations); break;
        }
        before.removeAll(targetSet(result));
        emit("destroy" + op, seed, types, result, new ArrayList<>(before));
    }

    private static void emitRepair(int op, String fixture, int seed) {
        Node st = station(100, 0.0);
        Node[] stations = {st};
        List<List<List<List<Node>>>> source;
        List<Node> removed;
        if (fixture.equals("tie")) {
            source = repairTieRoutes();
            removed = List.of(pending(15));
        } else if (fixture.equals("boundary") || fixture.equals("boundary_multi")) {
            source = boundaryRoutes();
            removed = fixture.equals("boundary_multi")
                    ? Arrays.asList(pending(16), pending(14)) : List.of(pending(16));
        } else {
            source = new ArrayList<>();
            List<List<List<Node>>> station = new ArrayList<>();
            station.add(drone(st, new int[]{1, 2, 3}, new int[]{4, 5}));
            station.add(drone(st, new int[]{6, 7}));
            source.add(station);
            removed = List.of(pending(14));
        }
        ReplayRandom.RNG.setSeed(seed);
        List<List<List<List<Node>>>> result = repair(op, source, 2, removed, stations);
        emit("repair" + op + "_" + fixture, seed, new int[]{2}, result, null);
    }

    public static void main(String[] args) {
        int seeds = args.length == 0 ? 16 : Integer.parseInt(args[0]);
        for (int op = 0; op < 4; op++)
            for (int seed = 0; seed < seeds; seed++) emitLocation(op, seed);
        for (int op = 0; op < 4; op++)
            for (int seed = 0; seed < seeds; seed++) emitLocal(op, seed);
        emitLocal(4, 0);
        for (int op = 0; op < 4; op++)
            for (int seed = 0; seed < seeds; seed++) emitDestroy(op, seed);
        for (int op = 0; op < 4; op++) {
            emitRepair(op, "base", 0);
            emitRepair(op, "tie", 0);
            emitRepair(op, "boundary", 0);
            emitRepair(op, "boundary_multi", 0);
        }
    }
}
