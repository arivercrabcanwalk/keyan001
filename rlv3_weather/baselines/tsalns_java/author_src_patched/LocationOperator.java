package test1;
import java.util.*;

public class LocationOperator {

    /**
     * Neighborhood operator: randomly swap the types of two stations.
     *
     * @param stationTypes station type array of the current solution
     * @return a new station type array after swapping the types of two stations
     */
    // Neighborhood 1: station swap
    public static int[] randomSwapStationTypes(int[] stationTypes) {

        Random random = new Random();
        // Create a new array to avoid modifying the original solution
        int[] newStationTypes = stationTypes.clone();

        // Randomly select two different station indices
        int index1 = random.nextInt(stationTypes.length);
        int index2 = random.nextInt(stationTypes.length);

        while (index1 == index2) {
            index2 = random.nextInt(stationTypes.length); // Ensure that the two indices are different
        }

        // Swap the station types
        int temp = newStationTypes[index1];
        newStationTypes[index1] = newStationTypes[index2];
        newStationTypes[index2] = temp;

        return newStationTypes;
    }

    // Neighborhood 2: station upgrade
    public static int[] upgradeStationType(int[] stationTypes) {
        Random random = new Random();
        int[] newStationTypes = stationTypes.clone();

        // Record the indices of stations that can be upgraded
        List<Integer> upgradableIndices = new ArrayList<>();
        for (int i = 0; i < newStationTypes.length; i++) {
            if (newStationTypes[i] < 2) {
                upgradableIndices.add(i);
            }
        }

        // If no station can be upgraded, return the original solution directly
        if (upgradableIndices.isEmpty()) {
            return stationTypes.clone();
        }

        // Randomly select one upgradable station
        int index = upgradableIndices.get(random.nextInt(upgradableIndices.size()));
        newStationTypes[index]++;
        return newStationTypes;
    }

    // Neighborhood 3: station downgrade
    public static int[] downgradeStationType(int[] stationTypes) {
        Random random = new Random();
        int[] newStationTypes = stationTypes.clone();

        // Record the indices of stations that can be downgraded
        List<Integer> downGradableIndices = new ArrayList<>();
        for (int i = 0; i < newStationTypes.length; i++) {
            if (newStationTypes[i] > 0) {
                downGradableIndices.add(i);
            }
        }

        // If no station can be downgraded, return the original solution directly
        if (downGradableIndices.isEmpty()) {
            return stationTypes.clone();
        }

        // Randomly select one degradable station
        int index = downGradableIndices.get(random.nextInt(downGradableIndices.size()));
        newStationTypes[index]--;
        return newStationTypes;
    }

    // Neighborhood 4: station closure
    public static int[] closeStation(int[] stationTypes) {
        Random random = new Random();
        int[] newStationTypes = stationTypes.clone();

        // Record the indices of stations that can be closed
        List<Integer> closableIndices = new ArrayList<>();
        for (int i = 0; i < newStationTypes.length; i++) {
            if (newStationTypes[i] != 0) {
                closableIndices.add(i);
            }
        }

        // If no station can be closed, return the original solution directly
        if (closableIndices.isEmpty()) {
            return stationTypes.clone();
        }

        // Randomly select one station to close
        int index = closableIndices.get(random.nextInt(closableIndices.size()));
        newStationTypes[index] = 0;
        return newStationTypes;
    }

    // Neighborhood 5: close a station with low utilization


    // Randomly apply one of the four neighborhood operators
    static int[] applyRandomNeighborhood(int[] stationTypes) {
        if (CovExt.fix != null) return CovExt.fix.clone();   // v3: siting fixed -> routing stage only
        Random random = new Random();
        int choice = random.nextInt(4);
        return switch (choice) {
            case 0 -> LocationOperator.randomSwapStationTypes(stationTypes); // Swap station types
            case 1 -> LocationOperator.upgradeStationType(stationTypes); // Upgrade a station
            case 2 -> LocationOperator.downgradeStationType(stationTypes); // Downgrade a station
            case 3 -> LocationOperator.closeStation(stationTypes); // Close a station
            default -> stationTypes;
        };
    }

    /**
     * Check whether a station configuration is feasible
     * (i.e., every target node is covered by at least one opened station).
     */
    static boolean isFeasible(Node[] targetNodes, Node[] stationNodes, int[] stationTypes,
                              double smallRadius, double largeRadius) {
        Set<Node> coveredTargets = new HashSet<>();

        for (int i = 0; i < stationNodes.length; i++) {
            if (stationTypes[i] == 0) continue; // Skip unopened stations
            double radius = (stationTypes[i] == 1) ? smallRadius : largeRadius;

            // Count the target nodes covered by the station
            for (Node target : targetNodes) {
                if (Calculator.calculateDistance(stationNodes[i], target) <= radius) {
                    coveredTargets.add(target);
                }
            }
        }

        // The solution is feasible if all target nodes are covered
        // v3 adaptation: + hard emergency-support coverage (CovExt, -Dcovfile); fixed siting (-Dfixtypes)
        if (CovExt.fix != null && !Arrays.equals(stationTypes, CovExt.fix)) return false;
        return coveredTargets.size() == targetNodes.length && CovExt.covered(stationNodes, stationTypes, smallRadius, largeRadius);
    }
}