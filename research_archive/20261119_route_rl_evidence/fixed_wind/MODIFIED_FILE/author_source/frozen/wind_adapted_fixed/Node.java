package test1;

public class Node {
    private int nodeNo; // ID
    private double X; // X coordinate
    private double Y; // Y coordinate
    private double serviceEnergy; // service time * rate
    private double serviceTime; //

    public Node() {
    }

    public Node(int nodeNo, double X, double Y, double serviceEnergy, double serviceTime) {
        this.nodeNo = nodeNo;
        this.X = X;
        this.Y = Y;
        this.serviceEnergy = serviceEnergy;
        this.serviceTime = serviceTime;
    }

    /**
     * @return nodeNo
     */
    public int getNodeNo() {
        return nodeNo;
    }

    /**
     * @param nodeNo
     */
    public void setNodeNo(int nodeNo) {
        this.nodeNo = nodeNo;
    }

    /**
     * @return X
     */
    public double getX() {
        return X;
    }

    /**
     * @param X
     */
    public void setX(double X) {
        this.X = X;
    }

    /**
     * @return Y
     */
    public double getY() {
        return Y;
    }

    /**
     * @param Y
     */
    public void setY(double Y) {
        this.Y = Y;
    }

    /**
     * @return serviceEnergy
     */
    public double getServiceEnergy() {
        return serviceEnergy;
    }

    /**
     * @param serviceEnergy
     */
    public void setServiceEnergy(double serviceEnergy) {
        this.serviceEnergy = serviceEnergy;
    }

    /**
     * @return serviceTime
     */
    public double getServiceTime() {
        return serviceTime;
    }

    /**
     * @param serviceTime
     */
    public void setServiceTime(double serviceTime) {
        this.serviceTime = serviceTime;
    }

    public boolean equals(Object obj) {
        if (this == obj) return true;
        if (obj == null || getClass() != obj.getClass()) return false;
        Node node = (Node) obj;
        return nodeNo == node.nodeNo;
    }



}

