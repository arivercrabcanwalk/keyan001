package test1;

import java.util.*;

public class Init {
    public static int[] stationSet(
            Node[] targetNodes,
            Node[] stationNodes,
            double smallRadius,
            double largeRadius) {

        // Initialize the station type array
        // 0 = unopened, 1 = small station, 2 = large station
        int[] stationTypes = new int[stationNodes.length];
        Arrays.fill(stationTypes, 0);

        // Store uncovered target nodes
        List<Node> uncoveredTargets = new ArrayList<>(Arrays.asList(targetNodes));

        // Greedy algorithm: at each step, choose the station covering the most uncovered targets
        while (!uncoveredTargets.isEmpty()) {
            // Compute coverage
            int[] smallCoverage = calculateCoverage(uncoveredTargets, stationNodes, smallRadius);
            int[] largeCoverage = calculateCoverage(uncoveredTargets, stationNodes, largeRadius);

            // Greedy selection: find the most cost-effective station
            int bestStationIndex = -1;
            int maxCoverage = 0;
            boolean useLargeRadius = false;

            for (int i = 0; i < stationNodes.length; i++) {
                if (stationTypes[i] != 0) continue; // Skip opened stations

                // Choose the station with the highest coverage
                if (smallCoverage[i] > maxCoverage) {
                    maxCoverage = smallCoverage[i];
                    bestStationIndex = i;
                    useLargeRadius = false;
                }
                if (largeCoverage[i] > maxCoverage) {
                    maxCoverage = largeCoverage[i];
                    bestStationIndex = i;
                    useLargeRadius = true;
                }
            }

            // If no valid station can be found while uncovered targets remain, return null
            if (bestStationIndex == -1 || maxCoverage == 0) {
                System.out.println("Failed to find an initial feasible solution.");
                return null;
            }

            // Open the best station
            stationTypes[bestStationIndex] = useLargeRadius ? 2 : 1;

            // Update the uncovered target list
            double radius = useLargeRadius ? largeRadius : smallRadius;
            Node station = stationNodes[bestStationIndex];
            uncoveredTargets.removeIf(target -> Calculator.calculateDistance(station, target) <= radius);

            // Stop if all targets have been covered
            if (uncoveredTargets.isEmpty()) {
                break;
            }
        }

        return stationTypes;
    }

    // Heterogeneous-station experiment: no large station is allowed
    public static int[] stationSet1(
            Node[] targetNodes,
            Node[] stationNodes,
            double smallRadius,
            double largeRadius) { // Note: largeRadius is unused but kept for method signature consistency

        // Initialize the station type array
        // 0 = unopened, 1 = small station
        int[] stationTypes = new int[stationNodes.length];
        Arrays.fill(stationTypes, 0);

        // Store uncovered target nodes
        List<Node> uncoveredTargets = new ArrayList<>(Arrays.asList(targetNodes));

        // Greedy algorithm: at each step, choose the small station covering the most uncovered targets
        while (!uncoveredTargets.isEmpty()) {
            // Compute coverage of small stations only
            int[] smallCoverage = calculateCoverage(uncoveredTargets, stationNodes, smallRadius);

            // Greedy selection: find the small station with the largest coverage
            int bestStationIndex = -1;
            int maxCoverage = 0;

            for (int i = 0; i < stationNodes.length; i++) {
                if (stationTypes[i] != 0) continue; // Skip opened stations

                if (smallCoverage[i] > maxCoverage) {
                    maxCoverage = smallCoverage[i];
                    bestStationIndex = i;
                }
            }

            // If no valid station can be found while uncovered targets remain, return null
            if (bestStationIndex == -1 || maxCoverage == 0) {
                System.out.println("Failed to find an initial feasible solution.");
                return null;
            }

            // Open the best station as a small station
            stationTypes[bestStationIndex] = 1;

            // Update the uncovered target list using the small-station radius
            Node station = stationNodes[bestStationIndex];
            uncoveredTargets.removeIf(target -> Calculator.calculateDistance(station, target) <= smallRadius);
        }

        return stationTypes;
    }

    // Heterogeneous-station experiment: only large stations are allowed
    public static int[] stationSet2(
            Node[] targetNodes,
            Node[] stationNodes,
            double smallRadius,  // Unused, kept only for method signature consistency
            double largeRadius) {

        // Initialize the station type array
        // 0 = unopened, 2 = large station
        int[] stationTypes = new int[stationNodes.length];
        Arrays.fill(stationTypes, 0);

        // Store uncovered target nodes
        List<Node> uncoveredTargets = new ArrayList<>(Arrays.asList(targetNodes));

        // Greedy algorithm: at each step, choose the large station covering the most uncovered targets
        while (!uncoveredTargets.isEmpty()) {
            // Compute coverage of large stations only
            int[] largeCoverage = calculateCoverage(uncoveredTargets, stationNodes, largeRadius);

            // Greedy selection: find the large station with the largest coverage
            int bestStationIndex = -1;
            int maxCoverage = 0;

            for (int i = 0; i < stationNodes.length; i++) {
                if (stationTypes[i] != 0) continue; // Skip opened stations

                if (largeCoverage[i] > maxCoverage) {
                    maxCoverage = largeCoverage[i];
                    bestStationIndex = i;
                }
            }

            // If no valid station can be found while uncovered targets remain, return null
            if (bestStationIndex == -1 || maxCoverage == 0) {
                System.out.println("Failed to find an initial feasible solution.");
                return null;
            }

            // Open the best station as a large station
            stationTypes[bestStationIndex] = 2;

            // Update the uncovered target list using the large-station radius
            Node station = stationNodes[bestStationIndex];
            uncoveredTargets.removeIf(target -> Calculator.calculateDistance(station, target) <= largeRadius);
        }

        return stationTypes;
    }

    // Compute the number of uncovered targets covered by each station
    public static int[] calculateCoverage(List<Node> uncoveredTargets, Node[] stationNodes, double radius) {
        int[] coverage = new int[stationNodes.length];
        for (int i = 0; i < stationNodes.length; i++) {
            for (Node target : uncoveredTargets) {
                if (Calculator.calculateDistance(stationNodes[i], target) <= radius) {
                    coverage[i]++;
                }
            }
        }
        return coverage;
    }

    // Assign target nodes to stations
    public static List<List<Node>> allocateTargetsToStations(
            Node[] targetNodes,
            Node[] stationNodes,
            int[] stationTypes,
            double smallRadius,
            double largeRadius) {

        // Initialize the result list
        // Each sublist stores the targets assigned to one station
        List<List<Node>> stationAllocations = new ArrayList<>();
        for (int i = 0; i < stationNodes.length; i++) {
            stationAllocations.add(new ArrayList<>());
        }

        // Assign each target to the nearest opened station that can cover it
        for (Node target : targetNodes) {
            double minDistance = Double.MAX_VALUE;
            int bestStationIndex = -1;

            // For each target, find the nearest feasible station
            for (int i = 0; i < stationNodes.length; i++) {
                if (stationTypes[i] == 0) continue; // Skip unopened stations

                Node station = stationNodes[i];
                double radius = (stationTypes[i] == 1) ? smallRadius : largeRadius;

                double distance = Calculator.calculateDistance(station, target);

                // The target must lie within the station coverage radius
                if (distance <= radius && distance < minDistance) {
                    minDistance = distance;
                    bestStationIndex = i;
                }
            }

            // Assign the target to the selected station
            if (bestStationIndex != -1) {
                stationAllocations.get(bestStationIndex).add(target);
            } else {
                System.out.println("Target " + target.getNodeNo() + " cannot be covered by any station.");
            }
        }

        return stationAllocations;
    }

    public static List<List<List<List<Node>>>> generateRoutes1(
            Node[] stationNodes, int[] stationTypes,
            List<List<Node>> stationAssignments,
            double smallDroneBattery, double largeDroneBattery,
            double flightEnergyRate, double smallStationDuration, double largeStationDuration, double flightSpeed) {

        List<List<List<List<Node>>>> allRoutes = new ArrayList<>(); // Routes of all stations

        for (int i = 0; i < stationNodes.length; i++) {
            Node station = stationNodes[i];
            int stationType = stationTypes[i];
            List<Node> stationTargets = stationAssignments.get(i); // Targets assigned to the current station

            // Skip unopened stations or stations without assigned targets
            if (stationType == 0 || stationTargets.isEmpty()) {
                allRoutes.add(new ArrayList<>());
                continue;
            }

            // Set the station operating time limit
            double closeTime = (stationType == 2) ? largeStationDuration : smallStationDuration;

            // Initialize drone routes
            List<List<Node>> largeDroneRoutes = new ArrayList<>();
            List<List<Node>> smallDroneRoutes = new ArrayList<>();

            if (stationType == 2) {
                // 1. Assign targets so that both drones at a large station have at least one task
                List<Node> largeDroneTargets = new ArrayList<>();
                List<Node> smallDroneTargets = new ArrayList<>();

                assignTargetsToDrones(station, stationTargets, largeDroneTargets, smallDroneTargets);

                // 2. Plan routes for the two drones separately
                planDroneRoutes(station, largeDroneTargets, largeDroneBattery, flightEnergyRate,
                        flightSpeed, closeTime, largeDroneRoutes);
                planDroneRoutes(station, smallDroneTargets, smallDroneBattery, flightEnergyRate,
                        flightSpeed, closeTime, smallDroneRoutes);
            } else if (stationType == 1) {
                // Small station: only one small drone is planned
                planDroneRoutes(station, stationTargets, smallDroneBattery, flightEnergyRate,
                        flightSpeed, closeTime, smallDroneRoutes);
            }

            // Store all routes of the current station
            List<List<List<Node>>> stationRoutes = new ArrayList<>();
            stationRoutes.add(largeDroneRoutes); // Large-drone routes
            stationRoutes.add(smallDroneRoutes); // Small-drone routes
            allRoutes.add(stationRoutes);
        }

        return allRoutes;
    }

    /**
     * Assign targets to drones so that both drones at a large station have tasks.
     */
    private static void assignTargetsToDrones(Node station, List<Node> stationTargets,
                                              List<Node> largeDroneTargets, List<Node> smallDroneTargets) {
        // 1. Sort targets by their distance to the station
        stationTargets.sort(Comparator.comparingDouble(target -> Calculator.calculateDistance(station, target)));

        // 2. Assign targets alternately
        boolean assignToLarge = true;
        for (Node target : stationTargets) {
            if (assignToLarge) {
                largeDroneTargets.add(target);
            } else {
                smallDroneTargets.add(target);
            }
            assignToLarge = !assignToLarge;
        }

        // 3. Ensure that both drones have at least one assigned target
        if (largeDroneTargets.isEmpty()) {
            largeDroneTargets.add(smallDroneTargets.remove(0));
        }
        if (smallDroneTargets.isEmpty()) {
            smallDroneTargets.add(largeDroneTargets.remove(0));
        }
    }

    /**
     * Greedily plan the routes of a single drone.
     */
    private static void planDroneRoutes(Node station, List<Node> targets, double battery,
                                        double flightEnergyRate, double speed, double closeTime,
                                        List<List<Node>> droneRoutes) {
        while (!targets.isEmpty()) {
            List<Node> route = new ArrayList<>();
            route.add(station); // The route starts from the station

            Node currentLocation = station;
            double remainingBattery = battery;
            double currentTime = 0.0;

            while (true) {
                Node closestTarget = findClosestTarget(currentLocation, targets, remainingBattery,
                        currentTime, speed, flightEnergyRate, station, closeTime);

                if (closestTarget != null) {
                    // Update drone state
                    double distanceToTarget = Calculator.calculateDistance(currentLocation, closestTarget);
                    double timeToTarget = distanceToTarget / speed;
                    double energyToTarget = timeToTarget * flightEnergyRate;

                    remainingBattery -= energyToTarget + closestTarget.getServiceEnergy();
                    currentTime += timeToTarget + closestTarget.getServiceTime();

                    route.add(closestTarget);
                    targets.remove(closestTarget);
                    currentLocation = closestTarget;
                } else {
                    // No more reachable target; return to the station
                    double distanceToStation = Calculator.calculateDistance(currentLocation, station);
                    double timeToStation = distanceToStation / speed;
                    double energyToStation = timeToStation * flightEnergyRate;

                    if (remainingBattery >= energyToStation && currentTime + timeToStation <= closeTime) {
                        route.add(station); // Return to the station
                    } else {
                        System.out.println("Warning: the drone cannot return to the station because of battery or time-limit violation.");
                    }
                    break;
                }
            }

            // Add the current route to the set of drone routes
            droneRoutes.add(route);
        }
    }

    /**
     * Find the nearest feasible target (core step of the greedy algorithm).
     */
    private static Node findClosestTarget(Node currentLocation, List<Node> targets,
                                          double battery, double time, double speed,
                                          double energyRate, Node station, double closeTime) {
        Node closestTarget = null;
        double minDistance = Double.MAX_VALUE;

        for (Node target : targets) {
            double distanceToTarget = Calculator.calculateDistance(currentLocation, target);
            double timeToTarget = distanceToTarget / speed;
            double energyToTarget = timeToTarget * energyRate;

            double distanceToStation = Calculator.calculateDistance(target, station);
            double timeToStation = distanceToStation / speed;
            double energyToStation = timeToStation * energyRate;

            if (battery >= energyToTarget + target.getServiceEnergy() + energyToStation &&
                    time + timeToTarget + target.getServiceTime() + timeToStation <= closeTime &&
                    distanceToTarget < minDistance) {
                closestTarget = target;
                minDistance = distanceToTarget;
            }
        }

        return closestTarget;
    }
}