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



    // Geometry stays physical. Wind is explicit and immutable within a run.
    public static double calculateTravelTime(Node from, Node to, double speed) {
        double wx=Double.parseDouble(System.getProperty("repro.wind.x","0"));
        double wy=Double.parseDouble(System.getProperty("repro.wind.y","0"));
        if (!Double.isFinite(speed) || speed<=0 || !Double.isFinite(wx) ||
            !Double.isFinite(wy) || Math.hypot(wx,wy)>=speed)
            throw new IllegalArgumentException("finite wind below airspeed required");
        if (wx==0 && wy==0) return calculateDistance(from,to)/speed;
        double dx=to.getX()-from.getX(),dy=to.getY()-from.getY();
        double l2=dx*dx+dy*dy;
        if (l2==0) return 0;
        double d=speed*speed-wx*wx-wy*wy;
        double dot=wx*dx+wy*dy;
        double q=Math.sqrt(d*l2+dot*dot);
        return dot>=0 ? l2/(q+dot) : (q-dot)/d;
    }

    // Symmetric effective metres: exact total for closed tours only.
    // Reversing a 2-opt segment must not use a directed four-edge delta.
    public static double calculateRouteDistance(Node a, Node b) {
        double speed=Main.DRONE_SPEED;
        double wx=Double.parseDouble(System.getProperty("repro.wind.x","0"));
        double wy=Double.parseDouble(System.getProperty("repro.wind.y","0"));
        if (!Double.isFinite(wx) || !Double.isFinite(wy) || Math.hypot(wx,wy)>=speed)
            throw new IllegalArgumentException("finite wind below airspeed required");
        if(wx==0 && wy==0) return calculateDistance(a,b);
        double dx=b.getX()-a.getX(),dy=b.getY()-a.getY();
        double d=speed*speed-wx*wx-wy*wy,dot=wx*dx+wy*dy;
        return speed*Math.sqrt(d*(dx*dx+dy*dy)+dot*dot)/d;
    }
}