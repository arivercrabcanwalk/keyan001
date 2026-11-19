package test1;

import java.util.*;

public class RoutingOperator {

    public static List<List<List<List<Node>>>> swap1(
            List<List<List<List<Node>>>> routes, int[] stationTypes,
            double largeDroneBattery, double smallDroneBattery,
            double droneSpeed, double largeDroneCons) {

        Random random = new Random();
        // Copy the original routes to avoid modifying the input directly
        List<List<List<List<Node>>>> newRoutes = deepCopyPaths(routes);

        // Get all opened stations
        List<Integer> openedStations = new ArrayList<>();
        for (int i = 0; i < stationTypes.length; i++) {
            if (stationTypes[i] > 0) { // Opened station
                openedStations.add(i);
            }
        }

        // If no station is available, return the original routes
        if (openedStations.isEmpty()) {
            return routes;
        }

        // Randomly choose one opened station
        int stationIndex = openedStations.get(random.nextInt(openedStations.size()));
        List<List<List<Node>>> stationRoutes = newRoutes.get(stationIndex);

        // Get drones with non-empty routes at this station
        List<Integer> validDrones = new ArrayList<>();
        for (int i = 0; i < stationRoutes.size(); i++) {
            if (!stationRoutes.get(i).isEmpty()) { // This drone has at least one route
                validDrones.add(i);
            }
        }

        // If all drones at this station have no routes, return the original routes
        if (validDrones.isEmpty()) {
            return routes;
        }

        // Randomly choose one drone with routes
        int droneIndex = validDrones.get(random.nextInt(validDrones.size()));
        List<List<Node>> droneRoutes = stationRoutes.get(droneIndex);

        // Randomly choose one non-empty subroute
        List<Integer> validSubRoutes = new ArrayList<>();

        for (int i = 0; i < droneRoutes.size(); i++) {
            if (droneRoutes.get(i).size() > 3) { // At least start, end, and one swappable target
                validSubRoutes.add(i);
            }
        }

        // If no valid subroute exists, return the original routes
        if (validSubRoutes.isEmpty()) {
            return routes;
        }

        int subRouteIndex = validSubRoutes.get(random.nextInt(validSubRoutes.size()));
        List<Node> subRoute = droneRoutes.get(subRouteIndex);

        // Randomly choose two different internal nodes (excluding start and end)
        int idx1 = random.nextInt(subRoute.size() - 2) + 1;
        int idx2;
        do {
            idx2 = random.nextInt(subRoute.size() - 2) + 1;
        } while (idx1 == idx2);

        // Swap the two nodes
        Node temp = subRoute.get(idx1);
        subRoute.set(idx1, subRoute.get(idx2));
        subRoute.set(idx2, temp);

        // Feasibility check
        if (isValidRoute(newRoutes, stationTypes, largeDroneBattery, smallDroneBattery, droneSpeed, largeDroneCons)) {
            return newRoutes; // Return the new routes if feasible
        } else {
            return routes; // Otherwise return the original routes
        }
    }

    // Swap operator between different subroutes of the same drone
    public static List<List<List<List<Node>>>> swap2(
            List<List<List<List<Node>>>> routes, int[] stationTypes,
            double largeDroneBattery, double smallDroneBattery,
            double droneSpeed, double largeDroneCons) {

        Random random = new Random();
        // Copy the original routes to avoid modifying the input directly
        List<List<List<List<Node>>>> newRoutes = deepCopyPaths(routes);

        // Choose one station (i.e., one List<List<List<Node>>>)
        int stationIndex = random.nextInt(newRoutes.size());
        List<List<List<Node>>> stationRoutes = newRoutes.get(stationIndex);

        // Choose one drone route set (i.e., one List<List<Node>>)
        if (stationRoutes.isEmpty()) {
            return newRoutes; // If the station has no routes, return the original solution
        }
        int droneIndex = random.nextInt(stationRoutes.size());
        List<List<Node>> droneRoutes = stationRoutes.get(droneIndex);

        // At least two subroutes are needed for swapping
        if (droneRoutes.size() < 2) {
            return newRoutes;
        }

        // Randomly choose two different subroutes
        int subRouteIndex1 = random.nextInt(droneRoutes.size());
        int subRouteIndex2 = random.nextInt(droneRoutes.size());
        while (subRouteIndex1 == subRouteIndex2) {
            subRouteIndex2 = random.nextInt(droneRoutes.size());
        }

        List<Node> subRoute1 = droneRoutes.get(subRouteIndex1);
        List<Node> subRoute2 = droneRoutes.get(subRouteIndex2);

        // Ensure both subroutes have at least one swappable node
        if (subRoute1.isEmpty() || subRoute2.isEmpty()) {
            return newRoutes;
        }

        // Randomly choose two nodes to swap
        int idx1 = random.nextInt(subRoute1.size() - 2) + 1;
        int idx2 = random.nextInt(subRoute2.size() - 2) + 1;

        // Swap the two nodes
        Node temp = subRoute1.get(idx1);
        subRoute1.set(idx1, subRoute2.get(idx2));
        subRoute2.set(idx2, temp);

        // Feasibility check
        if (isValidRoute(newRoutes, stationTypes, largeDroneBattery, smallDroneBattery, droneSpeed, largeDroneCons)) {
            return newRoutes; // Return the new routes if feasible
        } else {
            return routes; // Otherwise return the original routes
        }
    }

    // Swap operator between the large-drone and small-drone routes at the same station
    public static List<List<List<List<Node>>>> swap3(
            List<List<List<List<Node>>>> routes, int[] stationTypes,
            double largeDroneBattery, double smallDroneBattery,
            double droneSpeed, double largeDroneCons,
            double maxTimeLarge, double maxTimeSmall) {

        Random random = new Random();
        List<List<List<List<Node>>>> newRoutes = deepCopyPaths(routes);

        // Collect all large stations
        List<Integer> largeStations = new ArrayList<>();
        for (int i = 0; i < stationTypes.length; i++) {
            if (stationTypes[i] == 2) {
                largeStations.add(i);
            }
        }

        if (largeStations.isEmpty()) {
            return routes;
        }

        // Randomly choose one large station
        int stationIndex = largeStations.get(random.nextInt(largeStations.size()));
        List<List<List<Node>>> stationRoutes = newRoutes.get(stationIndex);

        // A large station has two drones by definition: 0 = large drone, 1 = small drone
        if (stationRoutes.size() < 2) {
            return routes;
        }

        List<List<Node>> dronePaths1 = stationRoutes.get(0);
        List<List<Node>> dronePaths2 = stationRoutes.get(1);

        if (dronePaths1.isEmpty() || dronePaths2.isEmpty()) {
            return routes;
        }

        // No need to enforce different subroute indices here
        int subRouteIndex1 = random.nextInt(dronePaths1.size());
        int subRouteIndex2 = random.nextInt(dronePaths2.size());

        List<Node> subRoute1 = dronePaths1.get(subRouteIndex1);
        List<Node> subRoute2 = dronePaths2.get(subRouteIndex2);

        // Each subroute must contain at least one internal customer node
        if (subRoute1.size() <= 2 || subRoute2.size() <= 2) {
            return routes;
        }

        int idx1 = random.nextInt(subRoute1.size() - 2) + 1;
        int idx2 = random.nextInt(subRoute2.size() - 2) + 1;

        Node temp = subRoute1.get(idx1);
        subRoute1.set(idx1, subRoute2.get(idx2));
        subRoute2.set(idx2, temp);

        boolean isValid =
                Check.checkStationOperation(newRoutes, droneSpeed, maxTimeLarge, maxTimeSmall, stationTypes)
                        && Check.isOverallSolutionValid(newRoutes, stationTypes,
                        largeDroneBattery, smallDroneBattery,
                        droneSpeed, largeDroneCons);

        if (isValid) {
            return newRoutes;
        } else {
            return routes;
        }
    }

    public static List<List<List<List<Node>>>> swap4(
            List<List<List<List<Node>>>> routes, int[] stationTypes,
            double largeDroneBattery, double smallDroneBattery,
            double droneSpeed, double largeDroneCons,
            double maxTimeLarge, double maxTimeSmall) {

        Random random = new Random();
        // Copy the original routes to avoid modifying the input directly
        List<List<List<List<Node>>>> newRoutes = deepCopyPaths(routes);

        // Get indices of all opened stations
        List<Integer> openedStations = new ArrayList<>();
        for (int i = 0; i < stationTypes.length; i++) {
            if (stationTypes[i] > 0) { // stationTypes[i] == 1 or 2
                openedStations.add(i);
            }
        }

        // If fewer than two candidate stations exist, return the original routes
        if (openedStations.size() < 2) {
            return routes;
        }

        // Randomly choose two different opened stations
        int stationIndex1 = openedStations.get(random.nextInt(openedStations.size()));
        int stationIndex2;
        do {
            stationIndex2 = openedStations.get(random.nextInt(openedStations.size()));
        } while (stationIndex1 == stationIndex2);

        List<List<List<Node>>> stationRoutes1 = newRoutes.get(stationIndex1);
        List<List<List<Node>>> stationRoutes2 = newRoutes.get(stationIndex2);

        // If the station route sets are empty, return the original routes
        if (stationRoutes1.isEmpty() || stationRoutes2.isEmpty()) {
            return routes;
        }

        // Randomly choose two drones
        int droneIndex1 = random.nextInt(stationRoutes1.size());
        int droneIndex2 = random.nextInt(stationRoutes2.size());

        List<List<Node>> dronePaths1 = stationRoutes1.get(droneIndex1);
        List<List<Node>> dronePaths2 = stationRoutes2.get(droneIndex2);

        // Ensure both drones have at least one subroute
        if (dronePaths1.isEmpty() || dronePaths2.isEmpty()) {
            return routes;
        }

        // Choose two subroutes
        int subRouteIndex1 = random.nextInt(dronePaths1.size());
        int subRouteIndex2 = random.nextInt(dronePaths2.size());

        List<Node> subRoute1 = dronePaths1.get(subRouteIndex1);
        List<Node> subRoute2 = dronePaths2.get(subRouteIndex2);

        // Ensure both subroutes have at least one internal swappable node
        if (subRoute1.size() < 3 || subRoute2.size() < 3) {
            return routes;
        }

        // Choose swappable nodes (excluding start and end)
        int idx1 = random.nextInt(subRoute1.size() - 2) + 1;
        int idx2 = random.nextInt(subRoute2.size() - 2) + 1;

        // Perform the swap
        Node temp = subRoute1.get(idx1);
        subRoute1.set(idx1, subRoute2.get(idx2));
        subRoute2.set(idx2, temp);

        // Check feasibility
        boolean isValid = Check.checkStationOperation(newRoutes, droneSpeed, maxTimeLarge, maxTimeSmall, stationTypes) &&
                Check.isOverallSolutionValid(newRoutes, stationTypes, largeDroneBattery, smallDroneBattery, droneSpeed, largeDroneCons);

        if (isValid) {
            return newRoutes; // Return the new routes if feasible
        } else {
            return routes; // Otherwise return the original routes
        }
    }

    // Swap routes between two drones at the same station
    public static List<List<List<List<Node>>>> swapPointsBetweenDrones(
            List<List<List<List<Node>>>> paths, int[] stationType) {

        Random random = new Random();

        // Deep-copy the route data
        List<List<List<List<Node>>>> newPaths = deepCopyPaths(paths);

        // Traverse all station route sets
        for (int stationIndex = 0; stationIndex < newPaths.size(); stationIndex++) {
            List<List<List<Node>>> stationPaths = newPaths.get(stationIndex);

            // Check whether the current station is a large station (stationType = 2)
            if (stationType[stationIndex] != 2 || stationPaths.size() < 2) {
                continue; // Skip if it is not a large station or does not have two drones
            }

            // Select two drone route sets
            int droneIdx1 = 0; // Large drone index
            int droneIdx2 = 1; // Small drone index

            List<List<Node>> dronePath1 = stationPaths.get(droneIdx1); // Large-drone routes
            List<List<Node>> dronePath2 = stationPaths.get(droneIdx2); // Small-drone routes

            // Randomly choose two subroutes
            List<Node> subPath1 = dronePath1.get(random.nextInt(dronePath1.size()));
            List<Node> subPath2 = dronePath2.get(random.nextInt(dronePath2.size()));

            // If either subroute is too short, skip
            if (subPath1.size() <= 3 || subPath2.size() <= 3) {
                continue;
            }

            // Build valid index sets
            List<Integer> validIndices1 = new ArrayList<>();
            List<Integer> validIndices2 = new ArrayList<>();

            for (int i = 1; i < subPath1.size() - 1; i++) {
                if (subPath1.get(i).getNodeNo() != 0) { // Exclude separator nodes
                    validIndices1.add(i);
                }
            }
            for (int i = 1; i < subPath2.size() - 1; i++) {
                if (subPath2.get(i).getNodeNo() != 0) { // Exclude separator nodes
                    validIndices2.add(i);
                }
            }

            // Skip if there are not enough valid indices
            if (validIndices1.isEmpty() || validIndices2.isEmpty()) {
                continue;
            }

            // Randomly choose two nodes to swap
            int idx1 = validIndices1.get(random.nextInt(validIndices1.size()));
            int idx2 = validIndices2.get(random.nextInt(validIndices2.size()));

            // Perform the swap
            Node temp = subPath1.get(idx1);
            subPath1.set(idx1, subPath2.get(idx2));
            subPath2.set(idx2, temp);
        }

        return newPaths;
    }

    // 2-opt operator
    public static List<List<List<List<Node>>>> twoOptOperator(
            List<List<List<List<Node>>>> paths) {

        // Deep-copy the route data to avoid modifying the original routes
        List<List<List<List<Node>>>> newPaths = deepCopyPaths(paths);

        // Traverse each station route set
        for (List<List<List<Node>>> stationPaths : newPaths) {
            // Traverse each drone route set
            for (List<List<Node>> dronePaths : stationPaths) {
                // Traverse each subroute
                for (List<Node> subPath : dronePaths) {
                    // Skip if the subroute is too short for a valid 2-opt move
                    if (subPath.size() <= 3) {
                        continue;
                    }

                    boolean improvement = true;

                    // Keep applying 2-opt until no improvement is found
                    while (improvement) {
                        improvement = false;

                        // Traverse all node pairs in the route
                        for (int i = 1; i < subPath.size() - 2; i++) { // Do not optimize the start and end nodes
                            for (int j = i + 1; j < subPath.size() - 1; j++) {
                                // Calculate the original distance
                                Node nodeA = subPath.get(i - 1);
                                Node nodeB = subPath.get(i);

                                Node nodeC = subPath.get(j);
                                Node nodeD = subPath.get(j + 1);

                                double currentDistance =
                                        Calculator.calculateDistance(nodeA, nodeB) + Calculator.calculateDistance(nodeC, nodeD);

                                // Calculate the distance after reversal
                                double newDistance =
                                        Calculator.calculateDistance(nodeA, nodeC) + Calculator.calculateDistance(nodeB, nodeD);

                                // If reversal reduces the distance, apply it
                                if (newDistance < currentDistance) {
                                    // Reverse nodes from i to j
                                    reverseSubPath(subPath, i, j);
                                    improvement = true; // Mark that an improvement was found
                                }
                            }
                        }
                    }
                }
            }
        }

        return newPaths;
    }

    // *************************************************************************
    // ALNS operators
    // *************************************************************************

    public static List<List<List<List<Node>>>> randomRemoveOnePoint(
            List<List<List<List<Node>>>> routes, int[] stationTypes,
            double largeDroneBattery, double smallDroneBattery,
            double droneSpeed, double droneCons,
            double maxTimeLarge, double maxTimeSmall) {

        Random random = new Random();

        // Deep-copy the routes to avoid modifying the original solution
        List<List<List<List<Node>>>> newRoutes = deepCopyPaths(routes);

        // Store all removable candidate nodes
        List<RemovalPosition> candidates = new ArrayList<>();

        // Traverse all stations
        for (int stationIndex = 0; stationIndex < newRoutes.size(); stationIndex++) {
            if (stationTypes[stationIndex] == 0) {
                continue; // Skip unopened stations
            }

            List<List<List<Node>>> stationRoutes = newRoutes.get(stationIndex);

            // Traverse all drones at this station
            for (int droneIndex = 0; droneIndex < stationRoutes.size(); droneIndex++) {
                List<List<Node>> dronePaths = stationRoutes.get(droneIndex);

                if (dronePaths.isEmpty()) {
                    continue;
                }

                // Count the total number of customer nodes currently assigned to this drone
                int totalCustomerPoints = 0;
                for (List<Node> subRoute : dronePaths) {
                    for (int i = 1; i < subRoute.size() - 1; i++) {
                        if (subRoute.get(i).getNodeNo() != 0) {
                            totalCustomerPoints++;
                        }
                    }
                }

                // If the drone has only one customer node left, removal is not allowed
                if (totalCustomerPoints <= 1) {
                    continue;
                }

                // Traverse all customer nodes in all subroutes
                for (int subRouteIndex = 0; subRouteIndex < dronePaths.size(); subRouteIndex++) {
                    List<Node> subRoute = dronePaths.get(subRouteIndex);

                    // At least start-customer-end is required
                    if (subRoute.size() < 3) {
                        continue;
                    }

                    for (int pointIndex = 1; pointIndex < subRoute.size() - 1; pointIndex++) {
                        Node currentNode = subRoute.get(pointIndex);

                        // Skip separator node 0
                        if (currentNode.getNodeNo() == 0) {
                            continue;
                        }

                        candidates.add(new RemovalPosition(
                                stationIndex, droneIndex, subRouteIndex, pointIndex
                        ));
                    }
                }
            }
        }

        // If no removable point exists, return the original solution
        if (candidates.isEmpty()) {
            return routes;
        }

        // Randomly choose one point to remove
        RemovalPosition selected = candidates.get(random.nextInt(candidates.size()));

        List<Node> targetSubRoute = newRoutes
                .get(selected.stationIndex)
                .get(selected.droneIndex)
                .get(selected.subRouteIndex);

        targetSubRoute.remove(selected.pointIndex);

        // If only the start and end nodes remain, the empty subroute can be kept.
        // If desired, the following code can be used to remove it.
    /*
    if (targetSubRoute.size() <= 2) {
        newRoutes.get(selected.stationIndex)
                 .get(selected.droneIndex)
                 .remove(selected.subRouteIndex);
    }
    */

        // Final global feasibility check
        boolean isValid = Check.checkStationOperation(
                newRoutes, droneSpeed, maxTimeLarge, maxTimeSmall, stationTypes
        ) && Check.isOverallSolutionValid(
                newRoutes, stationTypes, largeDroneBattery, smallDroneBattery, droneSpeed, droneCons
        );

        if (isValid) {
            return newRoutes;
        } else {
            return routes;
        }
    }

    public static List<List<List<List<Node>>>> greedyRemoveMostExpensivePoint(
            List<List<List<List<Node>>>> routes, int[] stationTypes,
            double largeDroneBattery, double smallDroneBattery,
            double droneSpeed, double DroneCons,
            double maxTimeLarge, double maxTimeSmall) {

        // Copy the original routes to avoid modifying the input directly
        List<List<List<List<Node>>>> newRoutes = deepCopyPaths(routes);

        int bestStationIndex = -1;
        int bestDroneIndex = -1;
        int bestSubRouteIndex = -1;
        int bestPointIndex = -1;
        double maxCostSaving = Double.NEGATIVE_INFINITY;

        // Traverse all stations
        for (int stationIndex = 0; stationIndex < newRoutes.size(); stationIndex++) {
            if (stationTypes[stationIndex] == 0) continue; // Skip unopened stations
            List<List<List<Node>>> stationRoutes = newRoutes.get(stationIndex);

            // Traverse all drone routes at this station
            for (int droneIndex = 0; droneIndex < stationRoutes.size(); droneIndex++) {
                List<List<Node>> dronePaths = stationRoutes.get(droneIndex);
                if (dronePaths.isEmpty()) continue; // no routes

                double droneBattery = (stationTypes[stationIndex] == 2 && droneIndex == 0) ? largeDroneBattery : smallDroneBattery;

                // Count the total number of customer nodes over all subroutes of this drone
                int totalCustomerPoints = 0;
                for (List<Node> path : dronePaths) {
                    totalCustomerPoints += path.size() - 2; // exclude start and end nodes
                }

                // Traverse all subroutes
                for (int subRouteIndex = 0; subRouteIndex < dronePaths.size(); subRouteIndex++) {
                    List<Node> subRoute = dronePaths.get(subRouteIndex);

                    // At least three nodes are required: start + target + end
                    if (subRoute.size() < 3) continue;

                    // Traverse all target nodes in this subroute (excluding start and end)
                    for (int i = 1; i < subRoute.size() - 1; i++) {
                        Node removedNode = subRoute.get(i);

                        // If this is the only customer node of the drone, removal is not allowed
                        if (totalCustomerPoints == 1) {
                            continue;
                        }

                        // Calculate the new cost after removing the current node
                        double originalCost = Check.calculatePathCost(subRoute, droneSpeed);
                        List<Node> newSubRoute = deepCopyList(subRoute);
                        newSubRoute.remove(i);

                        double newCost = Check.calculatePathCost(newSubRoute, droneSpeed);
                        double costSaving = originalCost - newCost;

                        // Update the maximum saving if the new path also satisfies the energy constraint
                        if (costSaving > maxCostSaving && Check.checkPathEnergy(newSubRoute, DroneCons, droneSpeed, droneBattery)) {
                            maxCostSaving = costSaving;
                            bestStationIndex = stationIndex;
                            bestDroneIndex = droneIndex;
                            bestSubRouteIndex = subRouteIndex;
                            bestPointIndex = i;
                        }
                    }
                }
            }
        }

        // If a best removable point is found
        if (bestStationIndex != -1) {
            List<List<Node>> dronePaths = newRoutes.get(bestStationIndex).get(bestDroneIndex);
            List<Node> bestSubRoute = dronePaths.get(bestSubRouteIndex);

            // Remove the selected point
            if (bestSubRoute.size() > 3) { // Ensure at least one customer node remains after removal
                Node removed = bestSubRoute.remove(bestPointIndex);
                /* System.out.println("? Removed customer node " + removed + " from drone " + bestDroneIndex + " at station " + bestStationIndex); */
            } else {
                /* System.out.println("?? Cannot remove customer node " + bestSubRoute.get(bestPointIndex) + " because only start and end nodes would remain."); */
            }
        }

        // Ensure the new solution is still feasible
        boolean isValid = Check.checkStationOperation(newRoutes, droneSpeed, maxTimeLarge, maxTimeSmall, stationTypes) &&
                Check.isOverallSolutionValid(newRoutes, stationTypes, largeDroneBattery, smallDroneBattery, droneSpeed, DroneCons);

        return isValid ? newRoutes : routes; // Return the original solution if infeasible
    }

    // Destroy operator 2: probabilistic greedy removal
    public static List<List<List<List<Node>>>> probabilisticGreedyRemove(
            List<List<List<List<Node>>>> paths, double acceptanceProbability) {

        // Deep-copy the path data to avoid affecting the original paths
        List<List<List<List<Node>>>> newPaths = deepCopyPaths(paths);
        boolean anyNodeRemoved = false; // Whether any node has been removed
        Random random = new Random(); // Random number generator

        // Traverse each station route set
        for (List<List<List<Node>>> stationPaths : newPaths) {
            // Traverse each drone route set
            for (List<List<Node>> dronePaths : stationPaths) {
                if (dronePaths.isEmpty()) continue; // Skip drones without routes

                // Count the total number of customer nodes assigned to this drone
                int totalCustomerPoints = 0;
                for (List<Node> path : dronePaths) {
                    totalCustomerPoints += path.size() - 2; // exclude start and end nodes
                }

                // Traverse each subroute
                for (List<Node> subPath : dronePaths) {
                    if (subPath.size() < 3) continue; // Skip if the route is too short

                    // Candidate list: stores removable nodes and their corresponding cost reduction
                    List<NodeRemovalCandidate> candidates = new ArrayList<>();

                    // Traverse internal nodes and compute removal costs
                    for (int i = 1; i < subPath.size() - 1; i++) {
                        Node prevNode = subPath.get(i - 1);
                        Node currentNode = subPath.get(i);
                        Node nextNode = subPath.get(i + 1);

                        // Check whether this is the only customer node of the drone
                        if (totalCustomerPoints == 1) {
                            continue;
                        }

                        // Compute the cost reduction of removing the current node
                        double originalCost = Calculator.calculateDistance(prevNode, currentNode) +
                                Calculator.calculateDistance(currentNode, nextNode);
                        double newCost = Calculator.calculateDistance(prevNode, nextNode);
                        double costReduction = originalCost - newCost;

                        // Add to candidate list if the cost reduction is positive
                        if (costReduction > 0) {
                            candidates.add(new NodeRemovalCandidate(i, costReduction));
                        }
                    }

                    // Skip this path if no candidate node exists
                    if (candidates.isEmpty()) continue;

                    // Sort candidates by decreasing cost reduction
                    candidates.sort((a, b) -> Double.compare(b.costReduction, a.costReduction));

                    // Try to remove candidates in order
                    for (NodeRemovalCandidate candidate : candidates) {
                        double probability = random.nextDouble();
                        if (probability <= acceptanceProbability) {
                            // Before removing, check whether the drone will still have customer nodes left
                            if (totalCustomerPoints > 1) {
                                subPath.remove(candidate.index);
                                totalCustomerPoints--; // Update total customer count
                                anyNodeRemoved = true;
                                break;
                            } /* else {
                                System.out.println("?? Cannot remove " + subPath.get(candidate.index) + " because the drone would become taskless.");
                            } */
                        }
                    }
                }
            }
        }

        // If no node is removed, return the original input paths
        return anyNodeRemoved ? newPaths : paths;
    }

    public static List<List<List<List<Node>>>> removeSimilarCustomers(
            List<List<List<List<Node>>>> routes, int[] stationTypes,
            double smallRadius, double largeRadius, Node[] stationNodeList) {

        List<List<List<List<Node>>>> newRoutes = deepCopyPaths(routes);
        Random random = new Random();

        List<RemovalPosition> candidates = new ArrayList<>();
        List<Double> similarities = new ArrayList<>();

        double maxSim = Double.NEGATIVE_INFINITY;
        double minSim = Double.POSITIVE_INFINITY;

        for (int stationIdx = 0; stationIdx < newRoutes.size(); stationIdx++) {
            if (stationTypes[stationIdx] == 0) {
                continue;
            }

            List<List<List<Node>>> stationRoutes = newRoutes.get(stationIdx);
            Node stationNode = stationNodeList[stationIdx];
            double stationCoverage = (stationTypes[stationIdx] == 2) ? largeRadius : smallRadius;

            for (int droneIdx = 0; droneIdx < stationRoutes.size(); droneIdx++) {
                List<List<Node>> dronePaths = stationRoutes.get(droneIdx);

                if (dronePaths.isEmpty()) {
                    continue;
                }

                // Count the current total number of customer nodes of this drone
                int totalCustomerPoints = 0;
                for (List<Node> subRoute : dronePaths) {
                    for (int i = 1; i < subRoute.size() - 1; i++) {
                        if (subRoute.get(i).getNodeNo() != 0) {
                            totalCustomerPoints++;
                        }
                    }
                }

                // If only one customer node remains, no further removal is allowed
                if (totalCustomerPoints <= 1) {
                    continue;
                }

                for (int subRouteIdx = 0; subRouteIdx < dronePaths.size(); subRouteIdx++) {
                    List<Node> subRoute = dronePaths.get(subRouteIdx);

                    if (subRoute.size() <= 3) {
                        continue; // start-customer-end; removing the customer would empty the route
                    }

                    for (int pointIdx = 1; pointIdx < subRoute.size() - 1; pointIdx++) {
                        Node current = subRoute.get(pointIdx);

                        if (current.getNodeNo() == 0) {
                            continue;
                        }

                        double sumSim = 0.0;

                        for (int j = 1; j < subRoute.size() - 1; j++) {
                            if (j == pointIdx) {
                                continue;
                            }

                            Node other = subRoute.get(j);
                            if (other.getNodeNo() == 0) {
                                continue;
                            }

                            double sim = calculateSimilarity(
                                    current, other, stationNode, stationCoverage,
                                    newRoutes, stationTypes, largeRadius, smallRadius, stationNodeList
                            );
                            sumSim += sim;
                        }

                        if (sumSim > 0) {
                            candidates.add(new RemovalPosition(stationIdx, droneIdx, subRouteIdx, pointIdx));
                            similarities.add(sumSim);
                            maxSim = Math.max(maxSim, sumSim);
                            minSim = Math.min(minSim, sumSim);
                        }
                    }
                }
            }
        }

        // If no removable point exists, return the original solution
        if (candidates.isEmpty()) {
            return routes;
        }

        // Normalize the weights and apply roulette-wheel selection
        List<Double> normWeights = new ArrayList<>();
        double totalWeight = 0.0;

        for (double sim : similarities) {
            double normSim;
            if (Math.abs(maxSim - minSim) < 1e-9) {
                normSim = 1.0;
            } else {
                normSim = (sim - minSim) / (maxSim - minSim);
            }

            // Avoid an all-zero weight vector
            normSim += 1e-6;

            normWeights.add(normSim);
            totalWeight += normSim;
        }

        double rand = random.nextDouble() * totalWeight;
        double cumulative = 0.0;
        int selectedIndex = -1;

        for (int i = 0; i < candidates.size(); i++) {
            cumulative += normWeights.get(i);
            if (rand <= cumulative) {
                selectedIndex = i;
                break;
            }
        }

        if (selectedIndex == -1) {
            selectedIndex = candidates.size() - 1;
        }

        RemovalPosition selected = candidates.get(selectedIndex);

        List<Node> targetSubRoute = newRoutes
                .get(selected.stationIndex)
                .get(selected.droneIndex)
                .get(selected.subRouteIndex);

        targetSubRoute.remove(selected.pointIndex);

        return newRoutes;
    }

    private static double calculateSimilarity(Node a, Node b, Node station, double stationCoverage,
                                              List<List<List<List<Node>>>> routes, int[] stationTypes,
                                              double largeRadius, double smallRadius, Node[] stationNodeList) {

        double distance = Calculator.calculateDistance(a, b);
        distance = Math.max(distance, 1e-6);

        boolean aCoveredByOther = false;
        boolean bCoveredByOther = false;

        for (int i = 0; i < routes.size(); i++) {
            if (stationTypes[i] == 0) {
                continue;
            }

            Node otherStation = stationNodeList[i];
            double otherCoverage = (stationTypes[i] == 2) ? largeRadius : smallRadius;

            if (Calculator.calculateDistance(otherStation, a) <= otherCoverage) {
                aCoveredByOther = true;
            }
            if (Calculator.calculateDistance(otherStation, b) <= otherCoverage) {
                bCoveredByOther = true;
            }
        }

        double lambda1 = 0.8;
        double lambda2 = 0.5;
        double lambda3 = 0.2;

        if (aCoveredByOther && bCoveredByOther) {
            return lambda1 / distance;
        } else if (aCoveredByOther || bCoveredByOther) {
            return lambda2 / distance;
        } else {
            return lambda3 / distance;
        }
    }

    // ------------------------------------------------------------------
    // Insertion neighborhoods
    // ------------------------------------------------------------------

    // Repair operator 1: greedy minimum-cost insertion
    // Insert the removed node where the cost increase is the smallest
    public static List<List<List<List<Node>>>> greedyInsertMinCost(
            List<List<List<List<Node>>>> routes, int[] stationTypes,
            List<Node> removedNodes, double largeDroneBattery, double smallDroneBattery,
            double droneSpeed, double droneCons, double maxTimeLarge, double maxTimeSmall,
            double smallRadius, double largeRadius) {

        // Copy the original routes to avoid modifying the input directly
        List<List<List<List<Node>>>> newRoutes = deepCopyPaths(routes);

        // Traverse all removed nodes
        for (Node node : removedNodes) {
            int bestStationIndex = -1;
            int bestDroneIndex = -1;
            int bestSubRouteIndex = -1;
            int bestInsertPos = -1;
            double minCostIncrease = Double.POSITIVE_INFINITY;

            // Traverse all stations
            for (int stationIndex = 0; stationIndex < newRoutes.size(); stationIndex++) {
                if (stationTypes[stationIndex] == 0) {
                    continue; // Unopened stations cannot be used for insertion
                }
                List<List<List<Node>>> stationRoutes = newRoutes.get(stationIndex);

                // Get the coverage radius and operating time limit of this station
                double coverageRadius = (stationTypes[stationIndex] == 2) ? largeRadius : smallRadius;
                double maxAllowedTime = (stationTypes[stationIndex] == 2) ? maxTimeLarge : maxTimeSmall;

                Node stationNode = null;

                outer:
                for (List<List<Node>> dronePaths : stationRoutes) {
                    for (List<Node> subRoute : dronePaths) {
                        if (!subRoute.isEmpty()) {
                            stationNode = subRoute.get(0); // The first node is the station
                            break outer;
                        }
                    }
                }
                if (stationNode == null) {
                    continue;
                }

                double distanceToStation = Calculator.calculateDistance(stationNode, node);

                if (distanceToStation > coverageRadius) {
                    continue;
                }

                // Traverse all drone routes at this station
                for (int droneIndex = 0; droneIndex < stationRoutes.size(); droneIndex++) {
                    List<List<Node>> dronePaths = stationRoutes.get(droneIndex);

                    // Battery capacity of this drone
                    double droneBattery = (stationTypes[stationIndex] == 2 && droneIndex == 0) ? largeDroneBattery : smallDroneBattery;

                    // Traverse all subroutes
                    for (int subRouteIndex = 0; subRouteIndex < dronePaths.size(); subRouteIndex++) {
                        List<Node> subRoute = dronePaths.get(subRouteIndex);

                        // Traverse all possible insertion positions (excluding the start)
                        for (int i = 1; i < subRoute.size(); i++) {
                            List<Node> newSubRoute = deepCopyList(subRoute);
                            newSubRoute.add(i, node);

                            // Calculate the cost before and after insertion
                            double oldCost = Check.calculatePathCost(subRoute, droneSpeed);
                            double newCost = Check.calculatePathCost(newSubRoute, droneSpeed);
                            double costIncrease = newCost - oldCost;

                            // Also compute the total operating time of this drone
                            double totalDroneTime = 0;
                            for (List<Node> path : dronePaths) {
                                if (path == subRoute) {
                                    totalDroneTime += Check.calculatePathTime(newSubRoute, droneSpeed);
                                } else {
                                    totalDroneTime += Check.calculatePathTime(path, droneSpeed);
                                }
                            }

                            // Must satisfy both local path feasibility and total drone-time feasibility
                            if (costIncrease < minCostIncrease && totalDroneTime <= maxAllowedTime &&
                                    Check.checkPathEnergy(newSubRoute, droneCons, droneSpeed, droneBattery)) {
                                minCostIncrease = costIncrease;
                                bestStationIndex = stationIndex;
                                bestDroneIndex = droneIndex;
                                bestSubRouteIndex = subRouteIndex;
                                bestInsertPos = i;
                            }
                        }
                    }
                }
            }

            // Apply the best insertion
            if (bestStationIndex != -1) {
                newRoutes.get(bestStationIndex)
                        .get(bestDroneIndex)
                        .get(bestSubRouteIndex)
                        .add(bestInsertPos, node);
            }
        }

        // Ensure the final solution is feasible
        boolean isValid = Check.checkStationOperation(newRoutes, droneSpeed, maxTimeLarge, maxTimeSmall, stationTypes) &&
                Check.isOverallSolutionValid(newRoutes, stationTypes, largeDroneBattery, smallDroneBattery, droneSpeed, droneCons);

        if (isValid) {
            return newRoutes;
        } else {
            return routes; // Return the original solution if infeasible
        }
    }

    public static List<List<List<List<Node>>>> nearestInsertion(
            List<List<List<List<Node>>>> routes, int[] stationTypes,
            List<Node> removedNodes, double largeDroneBattery,
            double smallDroneBattery, double droneSpeed, double droneCons,
            double maxTimeLarge, double maxTimeSmall, double smallRadius,
            double largeRadius, Node[] stationNodeList) {

        List<List<List<List<Node>>>> newRoutes = deepCopyPaths(routes);

        for (Node node : removedNodes) {
            double minDistanceIncrease = Double.MAX_VALUE;
            InsertionPosition bestPos = null;
            boolean needNewSubPath = false; // Whether a new subpath needs to be created
            int newSubPathStationIdx = -1;
            int newSubPathDroneIdx = -1;

            // Collect opened stations and their routes
            for (int stationIndex = 0; stationIndex < newRoutes.size(); stationIndex++) {
                if (stationTypes[stationIndex] == 0) {
                    continue; // Unopened stations cannot be used for insertion
                }
                List<List<List<Node>>> stationRoutes = newRoutes.get(stationIndex);

                // Get the coverage radius and operating time limit of this station
                double coverageRadius = (stationTypes[stationIndex] == 2) ? largeRadius : smallRadius;
                double maxAllowedTime = (stationTypes[stationIndex] == 2) ? maxTimeLarge : maxTimeSmall;

                // 1. Coverage check
                Node stationNode = stationNodeList[stationIndex];

                if (Calculator.calculateDistance(stationNode, node) > coverageRadius) {
                    continue;
                }

                // Traverse drones
                for (int droneIdx = 0; droneIdx < stationRoutes.size(); droneIdx++) {
                    List<List<Node>> dronePaths = stationRoutes.get(droneIdx);

                    if (dronePaths.isEmpty()) {
                        continue; // Skip drones without routes
                    }

                    double droneBattery = (stationTypes[stationIndex] == 2 && droneIdx == 0) ? largeDroneBattery : smallDroneBattery;

                    // Compute the current total time load of this drone
                    double originalDroneTime = Check.calculateDroneTime(dronePaths, droneSpeed);
                    boolean foundInsertion = false;

                    for (int subIdx = 0; subIdx < dronePaths.size(); subIdx++) {
                        List<Node> subRoute = dronePaths.get(subIdx);

                        for (int insertPos = 1; insertPos < subRoute.size(); insertPos++) {
                            // 3. Generate a temporary route
                            List<Node> tempRoute = insertIntoRoute(subRoute, insertPos, node);

                            // 4. Local feasibility check
                            boolean localValid = isSubPathValid(tempRoute, droneBattery, droneSpeed, droneCons);
                            if (!localValid) continue;

                            // 5. Compute the new route time load
                            double newSubRouteTime = Check.calculatePathTime(tempRoute, droneSpeed);
                            double originalSubRouteTime = Check.calculatePathTime(subRoute, droneSpeed);
                            double newDroneTime = originalDroneTime - originalSubRouteTime + newSubRouteTime;

                            if (newDroneTime > maxAllowedTime) continue; // Violates the station time limit

                            // 6. Compute the cost increment
                            double delta = calculateDeltaCost(subRoute, insertPos, node);

                            if (delta < minDistanceIncrease) {
                                minDistanceIncrease = delta;
                                bestPos = new InsertionPosition(stationIndex, droneIdx, subIdx, insertPos);
                                foundInsertion = true;
                            }
                        }
                    }

                    // If insertion into existing routes is impossible, try to create a new subpath
                    if (!foundInsertion) {
                        double baseCost = Calculator.calculateDistance(stationNode, node);
                        if (baseCost < minDistanceIncrease) {
                            needNewSubPath = true;
                            newSubPathStationIdx = stationIndex;
                            newSubPathDroneIdx = droneIdx;
                            minDistanceIncrease = baseCost;
                        }
                    }
                }
            }

            // 7. Apply insertion (prefer inserting into an existing path)
            if (bestPos != null) {
                applyInsertion(newRoutes, bestPos, node);
            }
            // 8. If no feasible insertion position exists, create a new subpath
            else if (needNewSubPath) {
                List<List<List<Node>>> stationRoutes = newRoutes.get(newSubPathStationIdx);
                List<List<Node>> dronePaths = stationRoutes.get(newSubPathDroneIdx);

                // Create a new subpath
                List<Node> newSubPath = new ArrayList<>();
                newSubPath.add(getStationNode(stationRoutes)); // Start: station
                newSubPath.add(node); // Inserted node
                newSubPath.add(getStationNode(stationRoutes)); // End: return to station
                dronePaths.add(newSubPath);
            }
        }

        // Final feasibility check
        boolean isValid = Check.checkStationOperation(newRoutes, droneSpeed, maxTimeLarge, maxTimeSmall, stationTypes) &&
                Check.isOverallSolutionValid(newRoutes, stationTypes, largeDroneBattery, smallDroneBattery, droneSpeed, droneCons);

        return isValid ? newRoutes : routes;
    }

    public static List<List<List<List<Node>>>> loadBalancingInsertion(
            List<List<List<List<Node>>>> routes, int[] stationTypes,
            List<Node> removedNodes, double largeDroneBattery,
            double smallDroneBattery, double droneSpeed, double droneCons,
            double maxTimeLarge, double maxTimeSmall, double smallRadius,
            double largeRadius, Node[] stationNodeList) {

        List<List<List<List<Node>>>> newRoutes = deepCopyPaths(routes);

        for (Node node : removedNodes) {
            double bestScore = Double.NEGATIVE_INFINITY;
            InsertionPosition bestPos = null;

            boolean needNewSubPath = false;
            int newSubPathStationIdx = -1;
            int newSubPathDroneIdx = -1;

            for (int stationIdx = 0; stationIdx < newRoutes.size(); stationIdx++) {
                if (stationTypes[stationIdx] == 0) {
                    continue;
                }

                List<List<List<Node>>> stationRoutes = newRoutes.get(stationIdx);
                Node stationNode = stationNodeList[stationIdx];

                double coverageRadius = (stationTypes[stationIdx] == 2) ? largeRadius : smallRadius;
                if (Calculator.calculateDistance(stationNode, node) > coverageRadius) {
                    continue;
                }

                for (int droneIdx = 0; droneIdx < stationRoutes.size(); droneIdx++) {
                    List<List<Node>> dronePaths = stationRoutes.get(droneIdx);

                    double droneBattery = (stationTypes[stationIdx] == 2 && droneIdx == 0)
                            ? largeDroneBattery : smallDroneBattery;
                    double maxAllowedTime = (stationTypes[stationIdx] == 2)
                            ? maxTimeLarge : maxTimeSmall;

                    // Case 1: insert into an existing subpath
                    if (!dronePaths.isEmpty()) {
                        double originalDroneTime = Check.calculateDroneTime(dronePaths, droneSpeed);

                        for (int subIdx = 0; subIdx < dronePaths.size(); subIdx++) {
                            List<Node> subRoute = dronePaths.get(subIdx);

                            for (int insertPos = 1; insertPos < subRoute.size(); insertPos++) {
                                List<Node> tempRoute = insertIntoRoute(subRoute, insertPos, node);

                                if (!isSubPathValid(tempRoute, droneBattery, droneSpeed, droneCons)) {
                                    continue;
                                }

                                double newSubRouteTime = Check.calculatePathTime(tempRoute, droneSpeed);
                                double originalSubRouteTime = Check.calculatePathTime(subRoute, droneSpeed);
                                double newDroneTime = originalDroneTime - originalSubRouteTime + newSubRouteTime;

                                if (newDroneTime > maxAllowedTime) {
                                    continue;
                                }

                                double score = calculateLoadBalanceScore(
                                        originalDroneTime, newDroneTime, maxAllowedTime,
                                        tempRoute, subRoute, droneSpeed
                                );

                                if (score > bestScore) {
                                    bestScore = score;
                                    bestPos = new InsertionPosition(stationIdx, droneIdx, subIdx, insertPos);
                                    needNewSubPath = false;
                                }
                            }
                        }
                    }

                    // Case 2: if insertion into existing paths is impossible, try creating a new subpath
                    List<Node> newSubRoute = new ArrayList<>();
                    newSubRoute.add(stationNode);
                    newSubRoute.add(node);
                    newSubRoute.add(stationNode);

                    if (!isSubPathValid(newSubRoute, droneBattery, droneSpeed, droneCons)) {
                        continue;
                    }

                    double newPathTime = Check.calculatePathTime(newSubRoute, droneSpeed);
                    double originalDroneTime = Check.calculateDroneTime(dronePaths, droneSpeed);
                    double newDroneTime = originalDroneTime + newPathTime;

                    if (newDroneTime > maxAllowedTime) {
                        continue;
                    }

                    double newPathScore = (maxAllowedTime - newDroneTime) / maxAllowedTime;

                    if (newPathScore > bestScore) {
                        bestScore = newPathScore;
                        bestPos = null;
                        needNewSubPath = true;
                        newSubPathStationIdx = stationIdx;
                        newSubPathDroneIdx = droneIdx;
                    }
                }
            }

            boolean inserted = false;

            if (bestPos != null) {
                applyInsertion(newRoutes, bestPos, node);
                inserted = true;
            } else if (needNewSubPath) {
                Node stationNode = stationNodeList[newSubPathStationIdx];
                List<Node> newSubRoute = new ArrayList<>();
                newSubRoute.add(stationNode);
                newSubRoute.add(node);
                newSubRoute.add(stationNode);
                newRoutes.get(newSubPathStationIdx).get(newSubPathDroneIdx).add(newSubRoute);
                inserted = true;
            }

            // Key rule: if even one node cannot be inserted back, abandon this repair and return the original destroyed routes
            if (!inserted) {
                return routes;
            }
        }

        boolean isValid = Check.checkStationOperation(newRoutes, droneSpeed, maxTimeLarge, maxTimeSmall, stationTypes) &&
                Check.isOverallSolutionValid(newRoutes, stationTypes, largeDroneBattery, smallDroneBattery, droneSpeed, droneCons);

        if (!isValid) {
            return routes;
        }

        // Double-check that all removed nodes have been reinserted
        List<Node> stillRemoved = findRemovedNodes(routes, newRoutes);
        if (!stillRemoved.isEmpty()) {
            return routes;
        }

        return newRoutes;
    }

    public static List<List<List<List<Node>>>> minimumRegretInsertion(
            List<List<List<List<Node>>>> routes, int[] stationTypes,
            List<Node> removedNodes, double largeDroneBattery,
            double smallDroneBattery, double droneSpeed, double droneCons,
            double maxTimeLarge, double maxTimeSmall, double smallRadius,
            double largeRadius, Node[] stationNodeList) {

        List<List<List<List<Node>>>> newRoutes = deepCopyPaths(routes);

        for (Node node : removedNodes) {
            List<InsertionCandidate> candidates = new ArrayList<>();
            double minDelta = Double.MAX_VALUE;

            // ======== Phase 1: try inserting into existing routes ========
            for (int stationIdx = 0; stationIdx < newRoutes.size(); stationIdx++) {
                if (stationTypes[stationIdx] == 0) continue;  // Skip unopened stations
                List<List<List<Node>>> stationRoutes = newRoutes.get(stationIdx);
                Node stationNode = stationNodeList[stationIdx];

                // Skip if out of coverage
                double coverageRadius = (stationTypes[stationIdx] == 2) ? largeRadius : smallRadius;
                if (Calculator.calculateDistance(stationNode, node) > coverageRadius)
                    continue;

                for (int droneIdx = 0; droneIdx < stationRoutes.size(); droneIdx++) {
                    List<List<Node>> dronePaths = stationRoutes.get(droneIdx);
                    if (dronePaths.isEmpty()) {
                        continue;
                    }

                    double droneBattery = (stationTypes[stationIdx] == 2 && droneIdx == 0) ? largeDroneBattery : smallDroneBattery;
                    double maxTime = (stationTypes[stationIdx] == 2) ? maxTimeLarge : maxTimeSmall;
                    double originalDroneTime = Check.calculateDroneTime(dronePaths, droneSpeed);

                    for (int subIdx = 0; subIdx < dronePaths.size(); subIdx++) {
                        List<Node> subRoute = dronePaths.get(subIdx);

                        for (int insertPos = 1; insertPos < subRoute.size(); insertPos++) {
                            List<Node> tempRoute = insertIntoRoute(subRoute, insertPos, node);

                            if (!isSubPathValid(tempRoute, droneBattery, droneSpeed, droneCons)) continue;
                            double newSubTime = Check.calculatePathTime(tempRoute, droneSpeed);
                            double newDroneTime = originalDroneTime - Check.calculatePathTime(subRoute, droneSpeed) + newSubTime;

                            if (newDroneTime > maxTime) continue;

                            double delta = calculateDeltaCost(subRoute, insertPos, node);
                            candidates.add(new InsertionCandidate(stationIdx, droneIdx, subIdx, insertPos, delta));
                            minDelta = Math.min(minDelta, delta);
                        }
                    }
                }
            }

            // ======== Phase 2: choose the best insertion position ========
            if (!candidates.isEmpty()) {
                InsertionCandidate bestCandidate = null;
                double minRegretValue = Double.MAX_VALUE;

                for (InsertionCandidate candidate : candidates) {
                    double regretValue = calculateRegret(candidate, candidates, minDelta);
                    if (regretValue < minRegretValue) {
                        minRegretValue = regretValue;
                        bestCandidate = candidate;
                    }
                }

                if (bestCandidate != null) {
                    applyInsertion(newRoutes,
                            new InsertionPosition(bestCandidate.stationIdx, bestCandidate.droneIdx, bestCandidate.subIdx, bestCandidate.insertPos),
                            node);
                    continue;
                }
            }

            // ======== Phase 3: if no feasible insertion exists, create a new subpath ========
            double minNewPathCost = Double.MAX_VALUE;
            int bestStation = -1, bestDrone = -1;

            for (int stationIdx = 0; stationIdx < newRoutes.size(); stationIdx++) {
                if (stationTypes[stationIdx] == 0) continue;
                List<List<List<Node>>> stationRoutes = newRoutes.get(stationIdx);
                Node stationNode = stationNodeList[stationIdx];

                double coverageRadius = (stationTypes[stationIdx] == 2) ? largeRadius : smallRadius;
                if (Calculator.calculateDistance(stationNode, node) > coverageRadius) continue;

                for (int droneIdx = 0; droneIdx < stationRoutes.size(); droneIdx++) {
                    if (stationRoutes.get(droneIdx).isEmpty()) continue;

                    double droneBattery = (stationTypes[stationIdx] == 2 && droneIdx == 0) ? largeDroneBattery : smallDroneBattery;
                    double maxTime = (stationTypes[stationIdx] == 2) ? maxTimeLarge : maxTimeSmall;

                    // Compute the cost from the station to this node
                    List<Node> newSubRoute = Arrays.asList(stationNode, node, stationNode);
                    if (!isSubPathValid(newSubRoute, droneBattery, droneSpeed, droneCons))
                        continue;

                    double newPathCost = Check.calculatePathCost(newSubRoute, droneSpeed);
                    if (newPathCost <= maxTime && newPathCost < minNewPathCost) {
                        minNewPathCost = newPathCost;
                        bestStation = stationIdx;
                        bestDrone = droneIdx;
                    }
                }
            }

            // Insert as a new route
            if (bestStation != -1 && bestDrone != -1) {
                List<Node> newSubRoute = new ArrayList<>();
                newSubRoute.add(getStationNode(newRoutes.get(bestStation)));
                newSubRoute.add(node);
                newSubRoute.add(getStationNode(newRoutes.get(bestStation)));

                newRoutes.get(bestStation).get(bestDrone).add(newSubRoute);
                //System.out.println("Node " + node.getNodeNo() + " starts a new subpath at station " + bestStation + " on drone " + bestDrone + ".");
            }
        }

        // Final check to avoid returning an invalid solution
        boolean isValid = Check.checkStationOperation(newRoutes, droneSpeed, maxTimeLarge, maxTimeSmall, stationTypes) &&
                Check.isOverallSolutionValid(newRoutes, stationTypes, largeDroneBattery, smallDroneBattery, droneSpeed, droneCons);

        return isValid ? newRoutes : routes;
    }

    public static List<List<List<List<Node>>>> prioritizedInsertion(
            List<List<List<List<Node>>>> routes, int[] stationTypes,
            List<Node> removedNodes, double largeDroneBattery,
            double smallDroneBattery, double droneSpeed, double droneCons,
            double maxTimeLarge, double maxTimeSmall, double smallRadius,
            double largeRadius, Node[] stationNodeList) {

        List<List<List<List<Node>>>> newRoutes = deepCopyPaths(routes);

        for (Node node : removedNodes) {
            boolean inserted = false;

            double bestScore = Double.NEGATIVE_INFINITY;
            InsertionPosition bestPos = null;

            int bestStation = -1, bestDrone = -1;
            int emptyStationIdx = -1, emptyDroneIdx = -1;

            // 1. Prioritize empty drones that are opened and can cover the node
            for (int stationIdx = 0; stationIdx < newRoutes.size() && !inserted; stationIdx++) {
                if (stationTypes[stationIdx] == 0) continue;

                List<List<List<Node>>> stationRoutes = newRoutes.get(stationIdx);
                Node stationNode = stationNodeList[stationIdx];
                double coverageRadius = (stationTypes[stationIdx] == 2) ? largeRadius : smallRadius;

                if (Calculator.calculateDistance(stationNode, node) > coverageRadius) continue;

                for (int droneIdx = 0; droneIdx < stationRoutes.size(); droneIdx++) {
                    List<List<Node>> droneRoutes = stationRoutes.get(droneIdx);

                    if (droneRoutes.isEmpty()) {
                        double droneBattery = (stationTypes[stationIdx] == 2 && droneIdx == 0)
                                ? largeDroneBattery : smallDroneBattery;
                        double maxTime = (stationTypes[stationIdx] == 2)
                                ? maxTimeLarge : maxTimeSmall;

                        List<Node> newSubRoute = new ArrayList<>();
                        newSubRoute.add(stationNode);
                        newSubRoute.add(node);
                        newSubRoute.add(stationNode);

                        if (isSubPathValid(newSubRoute, droneBattery, droneSpeed, droneCons)
                                && Check.calculatePathTime(newSubRoute, droneSpeed) <= maxTime) {
                            droneRoutes.add(newSubRoute);
                            inserted = true;
                            break;
                        }
                    }
                }
            }

            if (inserted) {
                continue;
            }

            // 2. Try insertion into existing subroutes
            for (int stationIdx = 0; stationIdx < newRoutes.size(); stationIdx++) {
                if (stationTypes[stationIdx] == 0) continue;

                List<List<List<Node>>> stationRoutes = newRoutes.get(stationIdx);
                Node stationNode = stationNodeList[stationIdx];
                double coverageRadius = (stationTypes[stationIdx] == 2) ? largeRadius : smallRadius;

                if (Calculator.calculateDistance(stationNode, node) > coverageRadius) continue;

                for (int droneIdx = 0; droneIdx < stationRoutes.size(); droneIdx++) {
                    List<List<Node>> dronePaths = stationRoutes.get(droneIdx);
                    if (dronePaths.isEmpty()) continue;

                    double droneBattery = (stationTypes[stationIdx] == 2 && droneIdx == 0)
                            ? largeDroneBattery : smallDroneBattery;
                    double maxTime = (stationTypes[stationIdx] == 2)
                            ? maxTimeLarge : maxTimeSmall;

                    double originalDroneTime = Check.calculateDroneTime(dronePaths, droneSpeed);

                    for (int subIdx = 0; subIdx < dronePaths.size(); subIdx++) {
                        List<Node> subRoute = dronePaths.get(subIdx);

                        for (int insertPos = 1; insertPos < subRoute.size(); insertPos++) {
                            List<Node> tempRoute = insertIntoRoute(subRoute, insertPos, node);

                            if (!isSubPathValid(tempRoute, droneBattery, droneSpeed, droneCons)) {
                                continue;
                            }

                            double newSubTime = Check.calculatePathTime(tempRoute, droneSpeed);
                            double oldSubTime = Check.calculatePathTime(subRoute, droneSpeed);
                            double newDroneTime = originalDroneTime - oldSubTime + newSubTime;

                            if (newDroneTime > maxTime) {
                                continue;
                            }

                            double score = 1.0 / (1.0 + calculateDeltaCost(subRoute, insertPos, node));

                            if (score > bestScore) {
                                bestScore = score;
                                bestPos = new InsertionPosition(stationIdx, droneIdx, subIdx, insertPos);
                            }
                        }
                    }
                }
            }

            if (bestPos != null) {
                applyInsertion(newRoutes, bestPos, node);
                inserted = true;
            }

            if (inserted) {
                continue;
            }

            // 3. Final fallback: create a new subpath
            double minNewPathCost = Double.MAX_VALUE;

            for (int stationIdx = 0; stationIdx < newRoutes.size(); stationIdx++) {
                if (stationTypes[stationIdx] == 0) continue;

                Node stationNode = stationNodeList[stationIdx];
                double coverageRadius = (stationTypes[stationIdx] == 2) ? largeRadius : smallRadius;
                if (Calculator.calculateDistance(stationNode, node) > coverageRadius) continue;

                List<List<List<Node>>> stationRoutes = newRoutes.get(stationIdx);

                for (int droneIdx = 0; droneIdx < stationRoutes.size(); droneIdx++) {
                    List<List<Node>> dronePaths = stationRoutes.get(droneIdx);

                    double droneBattery = (stationTypes[stationIdx] == 2 && droneIdx == 0)
                            ? largeDroneBattery : smallDroneBattery;
                    double maxTime = (stationTypes[stationIdx] == 2)
                            ? maxTimeLarge : maxTimeSmall;

                    List<Node> newSubRoute = new ArrayList<>();
                    newSubRoute.add(stationNode);
                    newSubRoute.add(node);
                    newSubRoute.add(stationNode);

                    if (!isSubPathValid(newSubRoute, droneBattery, droneSpeed, droneCons)) {
                        continue;
                    }

                    double currentDroneTime = Check.calculateDroneTime(dronePaths, droneSpeed);
                    double newPathTime = Check.calculatePathTime(newSubRoute, droneSpeed);

                    if (currentDroneTime + newPathTime > maxTime) {
                        continue;
                    }

                    double newPathCost = Check.calculatePathCost(newSubRoute, droneSpeed);
                    if (newPathCost < minNewPathCost) {
                        minNewPathCost = newPathCost;
                        bestStation = stationIdx;
                        bestDrone = droneIdx;
                    }
                }
            }

            if (bestStation != -1 && bestDrone != -1) {
                Node stationNode = stationNodeList[bestStation];
                List<Node> newSubRoute = new ArrayList<>();
                newSubRoute.add(stationNode);
                newSubRoute.add(node);
                newSubRoute.add(stationNode);
                newRoutes.get(bestStation).get(bestDrone).add(newSubRoute);
                inserted = true;
            }

            // Key rule: if this node cannot be reinserted, abandon this repair directly
            if (!inserted) {
                return routes;
            }
        }

        boolean isValid = Check.checkStationOperation(newRoutes, droneSpeed, maxTimeLarge, maxTimeSmall, stationTypes) &&
                Check.isOverallSolutionValid(newRoutes, stationTypes, largeDroneBattery, smallDroneBattery, droneSpeed, droneCons);

        if (!isValid) {
            return routes;
        }

        List<Node> stillRemoved = findRemovedNodes(routes, newRoutes);
        if (!stillRemoved.isEmpty()) {
            return routes;
        }

        return newRoutes;
    }

    // Regret value computation
    private static double calculateRegret(InsertionCandidate candidate,
                                          List<InsertionCandidate> allCandidates, double minDelta) {
        // Regret value is defined as the difference between this option and the second-best option
        double secondMinDelta = allCandidates.stream()
                .mapToDouble(c -> c.delta)
                .filter(d -> d != minDelta)
                .min()
                .orElse(minDelta);

        return candidate.delta - secondMinDelta;
    }

    // Candidate record class
    private static class InsertionCandidate {
        int stationIdx, droneIdx, subIdx, insertPos;
        double delta;

        public InsertionCandidate(int s, int d, int sr, int p, double delta) {
            stationIdx = s;
            droneIdx = d;
            subIdx = sr;
            insertPos = p;
            this.delta = delta;
        }
    }

    private static Node getStationNode(List<List<List<Node>>> stationRoutes) {
        if (stationRoutes.isEmpty()) {
            throw new IllegalStateException("2");
        }

        for (List<List<Node>> dronePaths : stationRoutes) {
            if (dronePaths.isEmpty())
                continue;

            for (List<Node> subRoute : dronePaths) {
                if (!subRoute.isEmpty()) {
                    return subRoute.get(0); // Return the start node of the first non-empty subroute
                }
            }
        }

        throw new IllegalStateException("1");
    }

    // Local feasibility check for one subpath
    private static boolean isSubPathValid(List<Node> route, double battery,
                                          double speed, double cons) {
        double time = Check.calculatePathTime(route, speed);
        double energy = Check.calculatePathEnergy(route, cons, speed);
        return energy <= battery;
    }

    // Compute the insertion cost increment
    private static double calculateDeltaCost(List<Node> subRoute, int insertPos, Node node) {
        Node a = subRoute.get(insertPos - 1);
        Node b = subRoute.get(insertPos);
        return Calculator.calculateDistance(a, node)
                + Calculator.calculateDistance(node, b)
                - Calculator.calculateDistance(a, b);
    }

    private static double calculateLoadBalanceScore(
            double originalDroneTime, double newDroneTime, double maxAllowedTime,
            List<Node> newRoute, List<Node> originalRoute, double speed) {
        // Load-balance factor (remaining capacity ratio)
        double loadBalanceFactor = (maxAllowedTime - newDroneTime) / maxAllowedTime;

        // Route-efficiency factor (inverse of path-cost increment)
        double originalCost = Check.calculatePathCost(originalRoute, speed);
        double newCost = Check.calculatePathCost(newRoute, speed);
        double efficiencyFactor = 1.0 / (1 + Math.abs(newCost - originalCost));

        // Composite score (weights can be adjusted)
        return 0.6 * loadBalanceFactor + 0.4 * efficiencyFactor;
    }

    public static List<List<List<List<Node>>>> deepCopyPaths(List<List<List<List<Node>>>> original) {
        List<List<List<List<Node>>>> copy = new ArrayList<>();
        for (List<List<List<Node>>> station : original) {
            List<List<List<Node>>> stationCopy = new ArrayList<>();
            for (List<List<Node>> drone : station) {
                List<List<Node>> droneCopy = new ArrayList<>();
                for (List<Node> subRoute : drone) {
                    // Create a deep copy of the subroute.
                    // This assumes Node is immutable or does not need to be copied deeply.
                    List<Node> subRouteCopy = new ArrayList<>(subRoute);
                    droneCopy.add(subRouteCopy);
                }
                stationCopy.add(droneCopy);
            }
            copy.add(stationCopy);
        }
        return copy;
    }

    public static boolean isValidRoute(List<List<List<List<Node>>>> routes, int[] stationTypes,
                                       double largeDroneBattery, double smallDroneBattery,
                                       double droneSpeed, double largeDroneCons) {
        // Feasibility check for energy and station-operation constraints
        return Check.isOverallSolutionValid(routes, stationTypes, largeDroneBattery, smallDroneBattery, droneSpeed, largeDroneCons);
    }

    // Deep copy of a subroute
    private static List<Node> deepCopyList(List<Node> route) {
        return new ArrayList<>(route);
    }

    // Find removed nodes
    public static List<Node> findRemovedNodes(
            List<List<List<List<Node>>>> originalRoutes,
            List<List<List<List<Node>>>> modifiedRoutes) {

        if (originalRoutes == null || modifiedRoutes == null) {
            throw new IllegalArgumentException("Input routes cannot be null.");
        }

        // Extract all nodes
        Set<Node> originalNodes = extractAllNodes(originalRoutes);
        Set<Node> modifiedNodes = extractAllNodes(modifiedRoutes);

        // Identify all start and end nodes to avoid incorrectly removing them
        Set<Node> fixedEndpoints = extractStartAndEndNodes(originalRoutes);

        // Compute removed nodes while excluding start and end nodes
        Set<Node> removed = new HashSet<>(originalNodes);
        removed.removeAll(modifiedNodes);
        removed.removeAll(fixedEndpoints);

        return new ArrayList<>(removed);
    }

    // Extract all nodes from all routes (including starts and ends)
    private static Set<Node> extractAllNodes(List<List<List<List<Node>>>> routes) {
        Set<Node> nodeSet = new HashSet<>();
        for (List<List<List<Node>>> stationRoutes : routes) {
            for (List<List<Node>> droneRoutes : stationRoutes) {
                for (List<Node> subRoute : droneRoutes) {
                    nodeSet.addAll(subRoute);
                }
            }
        }
        return nodeSet;
    }

    // Identify all start and end nodes of all stations
    private static Set<Node> extractStartAndEndNodes(List<List<List<List<Node>>>> routes) {
        Set<Node> endpoints = new HashSet<>();
        for (List<List<List<Node>>> stationRoutes : routes) {
            for (List<List<Node>> droneRoutes : stationRoutes) {
                for (List<Node> subRoute : droneRoutes) {
                    if (!subRoute.isEmpty()) {
                        endpoints.add(subRoute.get(0)); // Start node
                        endpoints.add(subRoute.get(subRoute.size() - 1)); // End node
                    }
                }
            }
        }
        return endpoints;
    }

    /**
     * Reverse a subpath.
     *
     * @param subPath the subpath
     * @param startIndex start index
     * @param endIndex end index
     */
    private static void reverseSubPath(List<Node> subPath, int startIndex, int endIndex) {
        while (startIndex < endIndex) {
            Node temp = subPath.get(startIndex);
            subPath.set(startIndex, subPath.get(endIndex));
            subPath.set(endIndex, temp);
            startIndex++;
            endIndex--;
        }
    }

    private static List<Node> insertIntoRoute(List<Node> subRoute, int insertPos, Node node) {
        // Defensive copy to avoid modifying the original route
        List<Node> newRoute = new ArrayList<>(subRoute);

        // Validate insertion position
        if (insertPos < 1 || insertPos >= newRoute.size()) {
            throw new IllegalArgumentException("Invalid insertion position: " + insertPos
                    + ", route length: " + newRoute.size());
        }

        // Perform insertion
        newRoute.add(insertPos, node);

        // Post-condition checks
        assert newRoute.get(0).equals(subRoute.get(0)) : "The start node was modified.";
        assert newRoute.get(newRoute.size() - 1).equals(subRoute.get(subRoute.size() - 1)) : "The end node was modified.";

        return newRoute;
    }

    private static void applyInsertion(List<List<List<List<Node>>>> routes,
                                       InsertionPosition pos, Node node) {
        List<Node> subRoute = routes.get(pos.stationIdx)
                .get(pos.droneIdx)
                .get(pos.subRouteIdx);
        subRoute.add(pos.insertPos, node);
    }

    // Record insertion position
    private static class InsertionPosition {
        int stationIdx;
        int droneIdx;
        int subRouteIdx;
        int insertPos;

        public InsertionPosition(int s, int d, int sr, int p) {
            stationIdx = s;
            droneIdx = d;
            subRouteIdx = sr;
            insertPos = p;
        }
    }

    /**
     * Helper class for storing candidate-node information.
     */
    private static class NodeRemovalCandidate {
        int index; // Node index
        double costReduction; // Cost reduction value

        public NodeRemovalCandidate(int index, double costReduction) {
            this.index = index;
            this.costReduction = costReduction;
        }
    }

    private static class RemovalPosition {
        int stationIndex;
        int droneIndex;
        int subRouteIndex;
        int pointIndex;

        RemovalPosition(int stationIndex, int droneIndex, int subRouteIndex, int pointIndex) {
            this.stationIndex = stationIndex;
            this.droneIndex = droneIndex;
            this.subRouteIndex = subRouteIndex;
            this.pointIndex = pointIndex;
        }
    }
}