package test1;

import java.util.List;


public class Solution {

    private List<List<List<List<Node>>>> nodeMatrix;

    // one dimensional list
    private int[] stationTypes;
    public Solution(){

    }

    public Solution(int targetNum, int candidateNum) {

        nodeMatrix = new java.util.ArrayList<>();
        for (int i = 0; i < targetNum; i++) {
            nodeMatrix.add(new java.util.ArrayList<>(candidateNum));
        }

        stationTypes = new int[candidateNum];
    }

    // Getter 和 Setter


    public List<List<List<List<Node>>>> getNodeMatrix() {
        return nodeMatrix;
    }


    public void setNodeMatrix(List<List<List<List<Node>>>> nodeMatrix) {
        this.nodeMatrix = nodeMatrix;
    }


    public int[] getStationTypes() {
        return stationTypes;
    }


    public void setStationTypes(int[] stationTypes) {
        this.stationTypes = stationTypes;
    }


    /**
     *
     * @param stationIndex
     * @param droneTypeIndex   (0 = large drone 1 = small drone)
     * @param subPathIndex
     * @param node
     */
    public void addNode(int stationIndex, int droneTypeIndex, int subPathIndex, Node node) {

        if (stationIndex < 0 || stationIndex >= nodeMatrix.size()) {
            throw new IndexOutOfBoundsException("Station index out of bounds.");
        }


        List<List<List<Node>>> stationRoutes = nodeMatrix.get(stationIndex);


        if (droneTypeIndex < 0 || droneTypeIndex >= stationRoutes.size()) {
            throw new IndexOutOfBoundsException("Drone type index out of bounds.");
        }


        List<List<Node>> droneRoutes = stationRoutes.get(droneTypeIndex);


        if (subPathIndex < 0 || subPathIndex >= droneRoutes.size()) {
            throw new IndexOutOfBoundsException("Subpath index out of bounds.");
        }


        List<Node> subPath = droneRoutes.get(subPathIndex);


        subPath.add(node);
    }


    public void setStationType(int candidateIndex, int type) {
        if (candidateIndex >= 0 && candidateIndex < stationTypes.length) {
            stationTypes[candidateIndex] = type;
        } else {
            throw new IndexOutOfBoundsException("Candidate index out of bounds.");
        }
    }



    public void printSolutionInfo() {
        System.out.println("Solution Information:");


        System.out.println("Station Types:");
        for (int i = 0; i < stationTypes.length; i++) {
            String stationType = switch (stationTypes[i]) {
                case 0 -> "Not Opened";
                case 1 -> "Small Station";
                case 2 -> "Large Station";
                default -> "Unknown";
            };
            System.out.println("  Station " + i + ": " + stationType);
        }
    }

    @Override
    public String toString() {
        StringBuilder sb = new StringBuilder();
        sb.append("[");
        for (int stationIndex = 0; stationIndex < nodeMatrix.size(); stationIndex++) {
            sb.append("[");
            List<List<List<Node>>> stationPaths = nodeMatrix.get(stationIndex);
            for (int droneIndex = 0; droneIndex < stationPaths.size(); droneIndex++) {
                sb.append("[");
                List<List<Node>> dronePaths = stationPaths.get(droneIndex);
                for (int subPathIndex = 0; subPathIndex < dronePaths.size(); subPathIndex++) {
                    List<Node> subPath = dronePaths.get(subPathIndex);
                    sb.append("[");
                    for (int i = 0; i < subPath.size(); i++) {
                        sb.append(subPath.get(i).getNodeNo());
                        if (i < subPath.size() - 1) {
                            sb.append(", ");
                        }
                    }
                    sb.append("]");
                    if (subPathIndex < dronePaths.size() - 1) {
                        sb.append(", ");
                    }
                }
                sb.append("]");
                if (droneIndex < stationPaths.size() - 1) {
                    sb.append(", ");
                }
            }
            sb.append("]");
            if (stationIndex < nodeMatrix.size() - 1) {
                sb.append(", ");
            }
        }
        sb.append("]");
        return sb.toString();
    }


}

