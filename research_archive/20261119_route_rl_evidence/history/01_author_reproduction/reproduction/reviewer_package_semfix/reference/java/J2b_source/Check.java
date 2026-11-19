package test1;

import java.util.ArrayList;
import java.util.List;

public class Check {

    // A complete solution is a four-dimensional list
    // The routes of one station form a three-dimensional list
    // The routes of one drone form a two-dimensional list
    // A single subpath of one drone is a one-dimensional list

    public static final double FLIGHT_COST_PER_MIN = 0.5; // Flight cost per minute

    /**
     * Calculate the total time of a single path.
     *
     * @param path       a single path, represented as List<Node>
     * @param droneSpeed drone speed (distance units per minute)
     * @return total path time
     */
    public static double calculatePathTime(List<Node> path, double droneSpeed) {
        double totalTime = 0.0;
        if (path.size() <= 2) {
            return totalTime;
        }

        // Traverse adjacent nodes in the path and accumulate travel time and service time
        for (int i = 0; i < path.size() - 1; i++) {
            Node currentNode = path.get(i);
            Node nextNode = path.get(i + 1);

            // Calculate travel time between two consecutive nodes
            double travelTime = Calculator.calculateDistance(currentNode, nextNode) / droneSpeed;
            totalTime += travelTime;

            // Add service time of the current node (excluding the start and end nodes)
            if (i > 0 && i < path.size() - 1) {
                totalTime += currentNode.getServiceTime();
            }
        }

        // Add the service time of the last node
        Node lastNode = path.get(path.size() - 1);
        totalTime += lastNode.getServiceTime();

        return totalTime;
    }

    public static double calculatePathCost(List<Node> path, double droneSpeed) {
        double totalTime = 0.0;
        if (path.size() <= 2) {
            return totalTime; // Return 0 if the path has too few nodes
        }

        // Traverse adjacent nodes in the path and accumulate travel time and service time
        for (int i = 0; i < path.size() - 1; i++) {
            Node currentNode = path.get(i);
            Node nextNode = path.get(i + 1);

            // Calculate travel time between two consecutive nodes
            double travelTime = Calculator.calculateDistance(currentNode, nextNode) / droneSpeed;
            totalTime += travelTime;

            // Add service time of the current node (excluding the start and end nodes)
            if (i > 0 && i < path.size() - 1) {
                totalTime += currentNode.getServiceTime();
            }
        }

        // Add the service time of the last node
        Node lastNode = path.get(path.size() - 1);
        totalTime += lastNode.getServiceTime();

        return totalTime * FLIGHT_COST_PER_MIN;
    }

    // Calculate the total length of a path
    public static double calculatePathLength(List<Node> path) {
        double pathLength = 0.0;

        if (path.size() <= 2) {
            return pathLength; // Return 0 if the path has too few nodes
        }

        // Traverse adjacent nodes and accumulate total distance
        for (int i = 0; i < path.size() - 1; i++) {
            Node fromNode = path.get(i);
            Node toNode = path.get(i + 1);
            pathLength += Calculator.calculateDistance(fromNode, toNode);
        }
        return pathLength;
    }

    // Calculate the total energy consumption of a path
    public static double calculatePathEnergy(List<Node> path, double energyPerUnitTime, double speed) {
        double totalEnergy = 0.0;

        for (int i = 0; i < path.size() - 1; i++) {
            Node currentNode = path.get(i);
            Node nextNode = path.get(i + 1);

            if (currentNode.getNodeNo() == 0 || nextNode.getNodeNo() == 0) {
                continue; // Skip separator nodes
            }

            // Calculate travel energy consumption between two nodes
            double distance = Calculator.calculateDistance(currentNode, nextNode);
            double travelTime = distance / speed;

            totalEnergy += travelTime * energyPerUnitTime;

            // Add service energy of the current node
            if (i > 0 && i < path.size() - 1) {
                totalEnergy += currentNode.getServiceEnergy();
            }
        }
        return totalEnergy;
    }

    // Check whether a drone path satisfies the battery constraint
    public static boolean checkPathEnergy(List<Node> path, double energyPerUnitTime, double speed, double droneBattery) {
        if (calculatePathEnergy(path, energyPerUnitTime, speed) < droneBattery) {
            return true;
        } else {
            return false;
        }
    }

    // Check whether the solution satisfies the station operating time limit
    public static boolean checkStationOperation(
            List<List<List<List<Node>>>> paths,
            double speed,
            double maxTimeLarge,
            double maxTimeSmall,
            int[] stationType) {

        // Traverse all stations
        for (int stationIndex = 0; stationIndex < paths.size(); stationIndex++) {
            // Get all drone routes of the current station
            List<List<List<Node>>> stationPaths = paths.get(stationIndex);

            // Get station type (1 = small station, 2 = large station)
            int type = stationType[stationIndex];
            double maxAllowedTime = (type == 2) ? maxTimeLarge : maxTimeSmall;

            // Traverse all drone routes
            for (List<List<Node>> dronePaths : stationPaths) {
                double accumulatedTime = 0.0;

                for (List<Node> subPath : dronePaths) {
                    double subPathTime = 0.0;
                    if (subPath.size() <= 2) {
                        continue;
                    }

                    for (int i = 0; i < subPath.size() - 1; i++) {
                        Node currentNode = subPath.get(i);
                        Node nextNode = subPath.get(i + 1);

                        if (currentNode.getNodeNo() == 0 || nextNode.getNodeNo() == 0) {
                            continue; // Skip separator nodes
                        }

                        // Time of the current segment = distance / speed
                        double distance = Calculator.calculateDistance(currentNode, nextNode);
                        subPathTime += distance / speed;

                        if (i > 0 && i < subPath.size() - 1) {
                            subPathTime += currentNode.getServiceTime();
                        }

                        Node lastNode = subPath.get(subPath.size() - 1);
                        subPathTime += lastNode.getServiceTime();
                    }

                    // Accumulate subpath time
                    accumulatedTime += subPathTime;

                    // Check whether the accumulated time exceeds the station time limit
                    if (accumulatedTime > maxAllowedTime) {
                        return false;
                    }
                }
            }
        }

        // If no violation is found, the solution is feasible
        return true;
    }

    public static boolean checkStationOperationLRP(
            List<List<List<List<Node>>>> paths,
            double speed,
            double maxTimeLarge,
            double maxTimeSmall,
            int[] stationType) {

        // Traverse all stations
        for (int stationIndex = 0; stationIndex < paths.size(); stationIndex++) {
            // Get all drone routes of the current station
            List<List<List<Node>>> stationPaths = paths.get(stationIndex);

            // Get station type (1 = small station, 2 = large station)
            int type = stationType[stationIndex];
            double maxAllowedTime = (type == 2) ? maxTimeLarge : maxTimeSmall;

            // Traverse all drone routes
            for (List<List<Node>> dronePaths : stationPaths) {
                double accumulatedTime = 0.0;

                for (List<Node> subPath : dronePaths) {
                    double subPathTime = 0.0;
                    if (subPath.size() <= 2) {
                        continue;
                    }

                    for (int i = 0; i < subPath.size() - 1; i++) {
                        Node currentNode = subPath.get(i);
                        Node nextNode = subPath.get(i + 1);

                        if (currentNode.getNodeNo() == 0 || nextNode.getNodeNo() == 0) {
                            continue; // Skip separator nodes
                        }

                        // Time of the current segment = distance / speed
                        double distance = Calculator.calculateDistance(currentNode, nextNode);
                        subPathTime += distance / speed;

                        if (i > 0 && i < subPath.size() - 1) {
                            subPathTime += currentNode.getServiceTime() * currentNode.getServiceTime();
                        }

                        Node lastNode = subPath.get(subPath.size() - 1);
                        subPathTime += lastNode.getServiceTime();
                    }

                    // Accumulate subpath time
                    accumulatedTime += subPathTime;

                    // Check whether the accumulated time exceeds the station time limit
                    if (accumulatedTime > maxAllowedTime) {
                        return false;
                    }
                }
            }
        }

        return true;
    }

    // Calculate the total cost
    public static double calculateTotalCost(
            List<List<List<List<Node>>>> paths,
            int[] stationType,
            double stationFixedCostLarge,
            double stationFixedCostSmall,
            double droneCostLarge,
            double droneCostSmall,
            double unitTimeCost,
            double droneSpeed) {

        double totalCost = 0.0; // Total cost

        // Traverse all stations
        for (int stationIdx = 0; stationIdx < paths.size(); stationIdx++) {
            List<List<List<Node>>> stationPaths = paths.get(stationIdx);

            // Add fixed station and drone costs according to station type
            if (stationType[stationIdx] == 2) {
                totalCost = totalCost + stationFixedCostLarge + droneCostLarge + droneCostSmall;
            } else if (stationType[stationIdx] == 1) {
                totalCost += stationFixedCostSmall + droneCostSmall;
            }

            // Traverse all drone routes
            for (int droneIdx = 0; droneIdx < stationPaths.size(); droneIdx++) {
                List<List<Node>> dronePaths = stationPaths.get(droneIdx);

                // Compute the total operating time of the drone
                double pathTime = calculateDroneTime(dronePaths, droneSpeed);

                // Add route operating cost
                totalCost += pathTime * unitTimeCost;
            }
        }

        return totalCost;
    }

    // Calculate the total completion time of a solution
    public static double calculateSolutionTime(List<List<List<List<Node>>>> paths, double speed) {
        double totalTime = 0.0;

        // Traverse all stations
        for (List<List<List<Node>>> stationPaths : paths) {
            // Traverse all drone routes of the station
            for (List<List<Node>> dronePaths : stationPaths) {
                totalTime += calculateDroneTime(dronePaths, speed);
            }
        }

        return totalTime;
    }

    // Calculate the total time of a drone
    public static double calculateDroneTime(List<List<Node>> dronePaths, double speed) {
        double accumulatedTime = 0.0;

        for (List<Node> subPath : dronePaths) {
            double subPathTime = 0.0;
            if (subPath.size() <= 2) {
                continue;
            }

            // Traverse each node in the subpath
            for (int i = 0; i < subPath.size() - 1; i++) {
                Node currentNode = subPath.get(i);
                Node nextNode = subPath.get(i + 1);

                if (currentNode.getNodeNo() == 0 || nextNode.getNodeNo() == 0) {
                    continue; // Skip separator nodes
                }

                // Time of the current segment = distance / speed
                double distance = Calculator.calculateDistance(currentNode, nextNode);
                subPathTime += distance / speed;

                // Add service time of the current node (excluding start and end nodes)
                if (i > 0 && i < subPath.size() - 1) {
                    subPathTime += currentNode.getServiceTime();
                }

                // Add service time of the last node for station-level experiments
                Node lastNode = subPath.get(subPath.size() - 1);
                subPathTime += lastNode.getServiceTime();
            }

            // Accumulate subpath time
            accumulatedTime += subPathTime;
        }

        return accumulatedTime;
    }

    // Compute and print remaining battery
    public static void printRemainingBattery(
            List<List<List<List<Node>>>> paths,
            double speed,
            double largeDroneBattery,
            double smallDroneBattery,
            double consumptionRate,
            int[] stationTypes) {

        // Traverse all stations
        for (int stationIndex = 0; stationIndex < paths.size(); stationIndex++) {
            System.out.println("Station " + stationIndex + ":");

            // Get all drone routes of the current station
            List<List<List<Node>>> stationPaths = paths.get(stationIndex);

            // Determine drone types according to station type
            int stationType = stationTypes[stationIndex];
            if (stationType == 2) {
                // Large station: first drone is large, second drone is small
                processDronePaths(stationPaths, largeDroneBattery, smallDroneBattery, speed, consumptionRate, true);
            } else if (stationType == 1) {
                // Small station: only one small drone
                processDronePaths(stationPaths, 0.0, smallDroneBattery, speed, consumptionRate, false);
            } else {
                System.out.println("  No drones assigned for this station (Station type: " + stationType + ").");
            }
        }
    }

    /**
     * Process all drone paths of a station and compute remaining battery.
     *
     * @param stationPaths       drone route data of the current station
     * @param largeDroneBattery  battery capacity of the large drone
     * @param smallDroneBattery  battery capacity of the small drone
     * @param speed              drone speed
     * @param consumptionRate    energy consumption rate
     * @param hasLargeDrone      whether the station has a large drone
     */
    private static void processDronePaths(
            List<List<List<Node>>> stationPaths,
            double largeDroneBattery,
            double smallDroneBattery,
            double speed,
            double consumptionRate,
            boolean hasLargeDrone) {

        for (int droneIndex = 0; droneIndex < stationPaths.size(); droneIndex++) {
            // Dynamically determine drone type and battery capacity
            double batteryCapacity;
            String droneType;
            if (hasLargeDrone && droneIndex == 0) {
                batteryCapacity = largeDroneBattery;
                droneType = "Large";
            } else {
                batteryCapacity = smallDroneBattery;
                droneType = "Small";
            }

            // Skip drones without valid battery capacity
            if (batteryCapacity == 0.0) {
                continue;
            }

            System.out.println("  Drone " + droneType + ":");

            List<List<Node>> dronePaths = stationPaths.get(droneIndex);
            for (int subPathIndex = 0; subPathIndex < dronePaths.size(); subPathIndex++) {
                List<Node> subPath = dronePaths.get(subPathIndex);

                // Use calculatePathLength to compute total path distance
                double totalDistance = calculatePathLength(subPath);

                // Accumulate service energy
                double serviceEnergy = 0.0;
                for (int i = 1; i < subPath.size() - 1; i++) {
                    serviceEnergy += subPath.get(i).getServiceEnergy();
                }

                // Compute battery consumption of the current subpath
                double consumedBattery = (totalDistance / speed) * consumptionRate + serviceEnergy;

                // Output remaining battery after the subpath
                double remainingBattery = batteryCapacity - consumedBattery;

                System.out.printf(
                        "    Subpath %d: Remaining Battery = %.2f (Travel Energy = %.2f, Service Energy = %.2f)%n",
                        subPathIndex, remainingBattery, totalDistance / speed * consumptionRate, serviceEnergy
                );

                // Warn if the battery is insufficient
                if (remainingBattery < 0) {
                    System.out.println("      Warning: Insufficient battery to complete this subpath.");
                    return;
                }
            }
        }
    }

    // Drone energy constraints
    public static boolean checkEnergyConstraints(
            List<List<List<List<Node>>>> paths,
            int[] stationType,
            double speed,
            double energyPerUnitTime,
            double batteryCapacityLarge,
            double batteryCapacitySmall) {

        for (int stationIndex = 0; stationIndex < paths.size(); stationIndex++) {
            List<List<List<Node>>> stationPaths = paths.get(stationIndex);
            int type = stationType[stationIndex];
            boolean isLargeStation = (type == 2);

            for (int droneIndex = 0; droneIndex < stationPaths.size(); droneIndex++) {
                List<List<Node>> dronePaths = stationPaths.get(droneIndex);

                // Determine battery capacity according to station type and drone index
                // Only the first drone of a large station is a large drone
                double maxBatteryCapacity = (isLargeStation && droneIndex == 0)
                        ? batteryCapacityLarge
                        : batteryCapacitySmall;

                double totalEnergyConsumed = 0.0;
                for (List<Node> subPath : dronePaths) {
                    totalEnergyConsumed += calculatePathEnergy(subPath, energyPerUnitTime, speed);

                    // Return false if battery capacity is exceeded
                    if (totalEnergyConsumed > maxBatteryCapacity) {
                        return false;
                    }
                }
            }
        }
        return true;
    }

    // Check whether the entire solution is feasible
    public static boolean isOverallSolutionValid(
            List<List<List<List<Node>>>> paths,
            int[] stationTypes,
            double largeDroneBattery,
            double smallDroneBattery,
            double speed,
            double consumptionRate) {

        // Traverse all stations
        for (int stationIndex = 0; stationIndex < paths.size(); stationIndex++) {
            List<List<List<Node>>> stationPaths = paths.get(stationIndex);

            // Get current station type (0 = unopened, 1 = small station, 2 = large station)
            int stationType = stationTypes[stationIndex];

            // Skip unopened stations
            if (stationType == 0) {
                continue;
            }

            // Check whether the station has a large drone
            boolean hasLargeDrone = (stationType == 2);

            // Check whether the current station satisfies energy constraints
            boolean isStationValid = checkStationPathsEnergy(
                    stationPaths,
                    largeDroneBattery,
                    smallDroneBattery,
                    speed,
                    consumptionRate,
                    hasLargeDrone
            );

            // Return false if any station is infeasible
            if (!isStationValid) {
                return false;
            }
        }

        // All stations satisfy the energy constraints
        return true;
    }

    /**
     * Check whether a single station satisfies the battery constraints.
     *
     * @param stationPaths       route set of one station
     * @param largeDroneBattery  battery capacity of the large drone
     * @param smallDroneBattery  battery capacity of the small drone
     * @param speed              drone speed (m/min)
     * @param consumptionRate    drone energy consumption rate
     * @param hasLargeDrone      whether the station has a large drone
     * @return true if the battery constraints are satisfied; false otherwise
     */
    private static boolean checkStationPathsEnergy(
            List<List<List<Node>>> stationPaths,
            double largeDroneBattery,
            double smallDroneBattery,
            double speed,
            double consumptionRate,
            boolean hasLargeDrone) {

        // Traverse route sets of all drones
        for (int droneIndex = 0; droneIndex < stationPaths.size(); droneIndex++) {
            // Dynamically determine battery capacity
            double batteryCapacity;
            // The first drone of a large station is the large drone
            if (hasLargeDrone && droneIndex == 0) {
                batteryCapacity = largeDroneBattery;
            } else {
                batteryCapacity = smallDroneBattery;
            }

            // Skip drones without valid battery capacity
            if (batteryCapacity == 0.0) {
                continue;
            }

            List<List<Node>> dronePaths = stationPaths.get(droneIndex);
            for (List<Node> subPath : dronePaths) {
                // Calculate total distance of the subpath
                double totalDistance = calculatePathLength(subPath);

                // Accumulate service energy
                double serviceEnergy = 0.0;
                for (int i = 1; i < subPath.size() - 1; i++) {
                    serviceEnergy += subPath.get(i).getServiceEnergy();
                }

                // Calculate consumed battery on the subpath
                double consumedBattery = (totalDistance / speed) * consumptionRate + serviceEnergy;

                // Return false if battery capacity is insufficient
                if (consumedBattery > batteryCapacity) {
                    return false;
                }
            }
        }

        // All routes of the current station satisfy the battery constraints
        return true;
    }

    /**
     * Calculate the latest completion time among all paths.
     *
     * @param paths      route set, represented as List<List<List<List<Node>>>>
     * @param droneSpeed drone speed (distance units per minute)
     * @return latest completion time
     */
    public static double calculateLatestTime(
            List<List<List<List<Node>>>> paths,
            double droneSpeed) {

        double latestTime = 0.0;

        // Traverse all stations
        for (List<List<List<Node>>> stationPaths : paths) {
            // Traverse all drones of the station
            for (List<List<Node>> dronePaths : stationPaths) {
                double totalDroneTime = 0.0;

                // Traverse all subpaths
                for (List<Node> subPath : dronePaths) {
                    double subPathTime = calculatePathTime(subPath, droneSpeed);
                    totalDroneTime += subPathTime;
                }

                // Update the latest completion time
                latestTime = Math.max(latestTime, totalDroneTime);
            }
        }

        return latestTime;
    }

    public static List<List<List<List<Node>>>> deepCopyRoute(List<List<List<List<Node>>>> original) {
        List<List<List<List<Node>>>> copy = new ArrayList<>();

        for (List<List<List<Node>>> stationPaths : original) {
            List<List<List<Node>>> stationCopy = new ArrayList<>();

            for (List<List<Node>> dronePaths : stationPaths) {
                List<List<Node>> droneCopy = new ArrayList<>();

                for (List<Node> subPath : dronePaths) {
                    List<Node> subPathCopy = new ArrayList<>();

                    for (Node node : subPath) {
                        // Create a new node and copy its attributes
                        Node nodeCopy = new Node(node.getNodeNo(), node.getX(), node.getY(),
                                node.getServiceEnergy(), node.getServiceTime());
                        subPathCopy.add(nodeCopy);
                    }

                    droneCopy.add(subPathCopy);
                }

                stationCopy.add(droneCopy);
            }

            copy.add(stationCopy);
        }

        return copy;
    }


    //The raw solution output contains empty subpaths because this representation is convenient
    // for insertion and removal operations during the search process; these empty paths do not
    // affect the correctness of the cost calculation.
    public static void printAllRoutes(List<List<List<List<Node>>>> allRoutes) {
        for (int stationIndex = 0; stationIndex < allRoutes.size(); stationIndex++) {
            List<List<List<Node>>> stationRoutes = allRoutes.get(stationIndex);

            boolean stationHasValidRoute = false;
            for (List<List<Node>> droneRoutes : stationRoutes) {
                for (List<Node> route : droneRoutes) {
                    if (route != null && route.size() > 2) {
                        stationHasValidRoute = true;
                        break;
                    }
                }
                if (stationHasValidRoute) {
                    break;
                }
            }

            if (!stationHasValidRoute) {
                continue;
            }

            System.out.println("Station " + (stationIndex + 1) + " Routes:");

            for (int droneType = 0; droneType < stationRoutes.size(); droneType++) {
                List<List<Node>> droneRoutes = stationRoutes.get(droneType);

                boolean droneHasValidRoute = false;
                for (List<Node> route : droneRoutes) {
                    if (route != null && route.size() > 2) {
                        droneHasValidRoute = true;
                        break;
                    }
                }

                if (!droneHasValidRoute) {
                    continue;
                }

                System.out.println(droneType == 0 ? "  Large Drone Routes:" : "  Small Drone Routes:");

                int validRouteCount = 1;
                for (List<Node> route : droneRoutes) {
                    if (route == null || route.size() <= 2) {
                        continue;
                    }

                    System.out.print("    Route " + validRouteCount + ": ");
                    for (int i = 0; i < route.size(); i++) {
                        if (i > 0) {
                            System.out.print(" -> ");
                        }
                        System.out.print(route.get(i).getNodeNo());
                    }
                    System.out.println();
                    validRouteCount++;
                }
            }
        }
    }

}