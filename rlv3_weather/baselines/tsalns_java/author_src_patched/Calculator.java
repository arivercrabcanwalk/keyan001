package test1;

public class Calculator {

    private static double smallStationCost;
    private static double largeStationCost;
    private static double smallDroneCost;
    private static double largeDroneCost;
    private static double distanceCost;

    public Calculator(double smallStationCost, double largeStationCost,
                      double smallDroneCost, double largeDroneCost,
                      double distanceCost) {
        this.smallStationCost = smallStationCost;
        this.largeStationCost = largeStationCost;
        this.smallDroneCost = smallDroneCost;
        this.largeDroneCost = largeDroneCost;
        this.distanceCost = distanceCost;
    }

    // distance calculation
    public static double calculateDistance(Node a, Node b) {
        return Math.sqrt(Math.pow(a.getX() - b.getX(), 2) + Math.pow(a.getY() - b.getY(), 2));
    }


}