package test1;

import java.util.*;

public class ALNSSolver {
    // Parameters in TSALNS
    private double initialTemp = 1000;
    private double coolingRate = 0.95;

    private int maxIterations = 5000;
    private double finalTemp = 1e-3;

    private double[] destroyWeights = {1.0, 1.0, 1.0, 1.0};
    private double[] repairWeights = {1.0, 1.0, 1.0, 1.0};

    private double[] destroyScores = new double[4];
    private double[] repairScores = new double[4];
    private int[] destroyCounts = new int[4];
    private int[] repairCounts = new int[4];
    private int updateInterval = 50;
    private int totalIterations = 5000;

    private long[] destroySelectedTotal = new long[]{0, 0, 0, 0};
    private long[] destroyAcceptedTotal = new long[]{0, 0, 0, 0};

    private long[] repairSelectedTotal = new long[]{0, 0, 0, 0};
    private long[] repairAcceptedTotal = new long[]{0, 0, 0, 0};

    private long iterTotal = 0; // Statistics only (optional)

    private int[] cumDestroySelected = new int[]{0, 0, 0, 0};
    private int[] cumRepairSelected = new int[]{0, 0, 0, 0};
    private int[] cumDestroyAccepted = new int[]{0, 0, 0, 0};
    private int[] cumRepairAccepted = new int[]{0, 0, 0, 0};

    public List<List<List<List<Node>>>> solve(
            List<List<List<List<Node>>>> initialRoute,
            int[] stationTypes,
            double largeDroneBattery,
            double smallDroneBattery,
            double droneSpeed,
            double droneCons,
            double maxTimeLarge,
            double maxTimeSmall,
            double smallRadius,
            double largeRadius,
            Node[] stationNodeList) {

        List<List<List<List<Node>>>> currentRoute = deepCopyPaths(initialRoute);
        List<List<List<List<Node>>>> bestRoute = deepCopyPaths(initialRoute);

        double currentCost = calculateTotalCost(currentRoute, droneSpeed);
        double bestCost = currentCost;
        double temperature = initialTemp;

        // Main optimization loop
        for (int iter = 0; iter < maxIterations && temperature > finalTemp; iter++) {
            // 1. Select destroy and repair operators
            int destroyIdx = selectOperator(destroyWeights);
            int repairIdx = selectOperator(repairWeights);

            // Record selection counts
            destroySelectedTotal[destroyIdx]++;
            repairSelectedTotal[repairIdx]++;
            iterTotal++;

            // 2. Apply destroy operator
            DestroyResult destroyResult = applyDestroyOperator(
                    destroyIdx, currentRoute, stationTypes,
                    largeDroneBattery, smallDroneBattery,
                    droneSpeed, droneCons, maxTimeLarge, maxTimeSmall,
                    smallRadius, largeRadius, stationNodeList
            );

            // 3. Apply repair operator
            List<List<List<List<Node>>>> newRoute = applyRepairOperator(
                    repairIdx, destroyResult.newRoutes, destroyResult.removedNodes,
                    stationTypes, largeDroneBattery, smallDroneBattery,
                    droneSpeed, droneCons, maxTimeLarge, maxTimeSmall,
                    smallRadius, largeRadius, stationNodeList
            );

            // 4. Compute cost and improvement
            double newCost = calculateTotalCost(newRoute, droneSpeed);
            boolean accepted = acceptNewSolution(currentCost, newCost, temperature);
            double improvement = bestCost - newCost;

            // 5. Update solution
            if (accepted) {
                currentRoute = newRoute;
                currentCost = newCost;

                destroyAcceptedTotal[destroyIdx]++;
                repairAcceptedTotal[repairIdx]++;

                if (newCost < bestCost) {
                    bestRoute = deepCopyPaths(newRoute);
                    bestCost = newCost;
                }

                cumDestroyAccepted[destroyIdx]++;
                cumRepairAccepted[repairIdx]++;
            }

            // 6. Update operator weights
            updateOperatorWeights(destroyIdx, repairIdx, accepted, improvement);
            totalIterations++;

            // 7. Cooling
            temperature *= coolingRate;

            // Progress output
//            if (iter % 100 == 0) {
//                System.out.printf("Iter %d | Temp %.2f | Current %.2f | Best %.2f%n",
//                        iter, temperature, currentCost, bestCost);
//            }
        }
        //printAlnsStatsFull();
        return bestRoute;
    }

    private DestroyResult applyDestroyOperator(int operatorIdx,
                                               List<List<List<List<Node>>>> current, int[] stationTypes,
                                               double largeBat, double smallBat, double speed, double cons,
                                               double maxTL, double maxTS, double smallRadius, double largeRadius, Node[] stationNodeList) {

        // Deep copy
        List<List<List<List<Node>>>> originalCopy = deepCopyPaths(current);
        List<List<List<List<Node>>>> modifiedRoutes = deepCopyPaths(current);

        switch (operatorIdx) {
            case 0: // Greedy removal
                modifiedRoutes = RoutingOperator.greedyRemoveMostExpensivePoint(
                        modifiedRoutes, stationTypes, largeBat, smallBat, speed, cons, maxTL, maxTS
                );
                break;

            case 1: // Probabilistic removal
                modifiedRoutes = RoutingOperator.probabilisticGreedyRemove(modifiedRoutes, 0.7);
                break;

            case 2: // Random removal
                modifiedRoutes = RoutingOperator.randomRemoveOnePoint(
                        modifiedRoutes, stationTypes, largeBat, smallBat,
                        speed, cons, maxTL, maxTS
                );
                break;

            case 3: // Similarity-based removal
                modifiedRoutes = RoutingOperator.removeSimilarCustomers(
                        modifiedRoutes, stationTypes, smallRadius, largeRadius, stationNodeList
                );
                break;
        }

        // Extract removed nodes
        List<Node> removedNodes = RoutingOperator.findRemovedNodes(originalCopy, modifiedRoutes);

        return new DestroyResult(modifiedRoutes, removedNodes);
    }

    private List<List<List<List<Node>>>> applyRepairOperator(int operatorIdx,
                                                             List<List<List<List<Node>>>> destroyed, List<Node> removedNodes,
                                                             int[] stationTypes, double largeBat, double smallBat,
                                                             double speed, double cons, double maxTL, double maxTS,
                                                             double smallR, double largeR, Node[] stationNodeList) {

        switch (operatorIdx) {
            case 0:
                return RoutingOperator.nearestInsertion(destroyed, stationTypes, removedNodes, largeBat, smallBat, speed, cons, maxTL, maxTS, smallR, largeR, stationNodeList);
            case 1:
                return RoutingOperator.minimumRegretInsertion(destroyed, stationTypes, removedNodes, largeBat, smallBat, speed, cons, maxTL, maxTS, smallR, largeR, stationNodeList);
            case 2:
                return RoutingOperator.loadBalancingInsertion(destroyed, stationTypes, removedNodes, largeBat, smallBat, speed, cons, maxTL, maxTS, smallR, largeR, stationNodeList);
            case 3:
                return RoutingOperator.prioritizedInsertion(destroyed, stationTypes, removedNodes, largeBat, smallBat, speed, cons, maxTL, maxTS, smallR, largeR, stationNodeList);
        }
        return destroyed;
    }

    private boolean acceptNewSolution(double currentCost, double newCost, double temp) {
        if (newCost < currentCost) { // Accept if the solution is better
            return true;
        }
        double prob = Math.exp((currentCost - newCost) / temp);
        return Math.random() < prob;
    }

    private int selectOperator(double[] weights) {
        double sum = Arrays.stream(weights).sum();
        double rand = Math.random() * sum;
        double accum = 0;
        for (int i = 0; i < weights.length; i++) {
            accum += weights[i];
            if (rand <= accum) return i;
        }
        return weights.length - 1;
    }

    private double calculateTotalCost(List<List<List<List<Node>>>> routes, double speed) {
        double total = 0;
        for (List<List<List<Node>>> station : routes) {
            for (List<List<Node>> drone : station) {
                for (List<Node> subRoute : drone) {
                    total += Check.calculatePathCost(subRoute, speed);
                }
            }
        }
        return total;
    }

    private void updateOperatorWeights(int destroyIdx, int repairIdx,
                                       boolean accepted, double improvement) {
        // Update usage counters
        destroyCounts[destroyIdx]++;
        repairCounts[repairIdx]++;

        // Compute the base reward
        // Base acceptance reward: +1
        // Improvement reward: normalized as improvement / (improvement + 1)
        // Penalty for rejection: -0.2
        double baseReward = accepted ? 1.0 : -0.2;
        if (accepted && improvement > 0) {
            baseReward += 2.0 * (improvement / (improvement + 1));
        }

        // Apply exponential decay to preserve historical information
        // while placing more emphasis on recent performance
        double decay = 0.9;
        destroyScores[destroyIdx] = decay * destroyScores[destroyIdx] + baseReward;
        repairScores[repairIdx] = decay * repairScores[repairIdx] + baseReward;

        // Periodically update weights
        if (totalIterations % updateInterval == 0) {
            updateAllWeights();
        }
    }

    private void updateAllWeights() {
        // Update destroy operator weights
        // Keep 80% of the original weight and use 20% of the new average score
        // to avoid large oscillations
        for (int i = 0; i < destroyWeights.length; i++) {
            if (destroyCounts[i] > 0) {
                double avg = destroyScores[i] / destroyCounts[i];
                destroyWeights[i] = Math.max(0.1, Math.min(5.0,
                        destroyWeights[i] * 0.8 + avg * 0.2));
            }
        }

        // Update repair operator weights
        for (int i = 0; i < repairWeights.length; i++) {
            if (repairCounts[i] > 0) {
                double avg = repairScores[i] / repairCounts[i];
                repairWeights[i] = Math.max(0.1, Math.min(5.0,
                        repairWeights[i] * 0.8 + avg * 0.2));
            }
        }

        // Reset statistics
        Arrays.fill(destroyScores, 0);
        Arrays.fill(repairScores, 0);
        Arrays.fill(destroyCounts, 0);
        Arrays.fill(repairCounts, 0);
    }

    // Deep copy method
    private static List<List<List<List<Node>>>> deepCopyPaths(List<List<List<List<Node>>>> original) {
        List<List<List<List<Node>>>> copy = new ArrayList<>();
        for (List<List<List<Node>>> station : original) {
            List<List<List<Node>>> stationCopy = new ArrayList<>();
            for (List<List<Node>> drone : station) {
                List<List<Node>> droneCopy = new ArrayList<>();
                for (List<Node> subRoute : drone) {
                    List<Node> subCopy = new ArrayList<>(subRoute);
                    droneCopy.add(subCopy);
                }
                stationCopy.add(droneCopy);
            }
            copy.add(stationCopy);
        }
        return copy;
    }

    // Data structure returned by a destroy operator:
    // it contains the modified routes and the removed nodes
    private static class DestroyResult {
        List<List<List<List<Node>>>> newRoutes;
        List<Node> removedNodes;

        public DestroyResult(List<List<List<List<Node>>>> routes, List<Node> nodes) {
            this.newRoutes = routes;
            this.removedNodes = nodes;
        }
    }

    // Simple reporting method: call at the end of solve()
    // One can use the function to record the performance of destroy and repair operators
    private void printAlnsStatsFull() {
        long dSum = Arrays.stream(destroySelectedTotal).sum();
        long rSum = Arrays.stream(repairSelectedTotal).sum();

        System.out.println("=== ALNS Operator Statistics (Overall) ===");
        for (int i = 0; i < destroySelectedTotal.length; i++) {
            double usage = dSum == 0 ? 0.0 : (double) destroySelectedTotal[i] / dSum;
            double acc = destroySelectedTotal[i] == 0 ? 0.0 :
                    (double) destroyAcceptedTotal[i] / destroySelectedTotal[i];
            System.out.printf("Destroy[%d] Usage Rate = %.3f  Acceptance Rate = %.3f  (Selected = %d, Accepted = %d)%n",
                    i, usage, acc, destroySelectedTotal[i], destroyAcceptedTotal[i]);
        }
        for (int j = 0; j < repairSelectedTotal.length; j++) {
            double usage = rSum == 0 ? 0.0 : (double) repairSelectedTotal[j] / rSum;
            double acc = repairSelectedTotal[j] == 0 ? 0.0 :
                    (double) repairAcceptedTotal[j] / repairSelectedTotal[j];
            System.out.printf("Repair[%d]  Usage Rate = %.3f  Acceptance Rate = %.3f  (Selected = %d, Accepted = %d)%n",
                    j, usage, acc, repairSelectedTotal[j], repairAcceptedTotal[j]);
        }
        System.out.printf("Total Destroy Usage Rate = %.3f, Total Repair Usage Rate = %.3f%n",
                dSum == 0 ? 0.0 : 1.0, rSum == 0 ? 0.0 : 1.0);
    }
}