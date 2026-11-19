package test1;

import java.util.*;

import static test1.Check.printAllRoutes;
import static test1.Init.allocateTargetsToStations;

public class Main {
    // Static parameters: station, drone, and energy-related settings
    public static final double SMALL_RADIUS = 4000.0; // Coverage radius of a small station (m)
    public static final double LARGE_RADIUS = 5000.0; // Coverage radius of a large station (m)

    public static final double SMALL_STATION_TIME = 480; // Operating duration limit of a small station (min)
    public static final double LARGE_STATION_TIME = 600; // Operating duration limit of a large station (min)

    public static final double SMALL_DRONE_BATTERY = 0.81; // Battery capacity of a small drone
    public static final double LARGE_DRONE_BATTERY = 1; // Battery capacity of a large drone

    public static final double HOVER_ENERGY_PER_MIN = 0.02; // This parameter is integrated into the instance data

    public static final double LARGE_DRONE_CONS = 0.018; // Flight energy consumption rate (per minute) used by both large and small drones

    public static final double DRONE_SPEED = 900; // Drone speed (m/min)

    public static final double SMALL_SITE_COST = 22.8; // Fixed cost of opening a small station
    public static final double LARGE_SITE_COST = 30.4; // Fixed cost of opening a large station
    public static final double SMALL_DRONE_COST = 5; // Fixed cost of using a small drone
    public static final double LARGE_DRONE_COST = 8; // Fixed cost of using a large drone
    public static final double FLIGHT_COST_PER_MIN = 0.5; // Flight cost per minute

    // Algorithm-related parameters
    private static final int MAX_ITERATIONS = 500; // Maximum number of iterations
    private static final double INITIAL_TEMPERATURE = 1000.0; // Initial temperature
    private static final double COOLING_RATE = 0.95; // Cooling rate


    public static void main(String[] args) {
        long startTime = System.currentTimeMillis(); // start time


        // your file path
        String filePath = "PATH";
        List<Node> allNodes = FileReaderUtil.readNodesFromFile(filePath);


        List<Node> targetNodesList = new ArrayList<>();
        List<Node> stationNodesList = new ArrayList<>();

        for (Node node : allNodes) {
            if (node.getServiceEnergy() > 0) {
                targetNodesList.add(node);
            } else {
                stationNodesList.add(node);
            }
        }

        Node[] targetNodes = targetNodesList.toArray(new Node[0]);
        Node[] stationNodes = stationNodesList.toArray(new Node[0]);


        // initial as unopened
        int[] stationTypes = new int[stationNodes.length];


        Solution initSolution = new Solution();
        stationTypes = Init.stationSet(targetNodes, stationNodes, SMALL_RADIUS, LARGE_RADIUS);

        for (int i = 0; i < stationTypes.length; i++) {
            System.out.println("Station type："+stationTypes[i]);
        }
        initSolution.setStationTypes(stationTypes);

        List<List<Node>> allocations = allocateTargetsToStations(
                targetNodes, stationNodes, stationTypes, SMALL_RADIUS, LARGE_RADIUS
        );

        for (int i = 0; i < allocations.size(); i++) {
            List<Node> allocatedTargets = allocations.get(i);

            List<Integer> targetIds = new ArrayList<>();
            for (Node target : allocatedTargets) {
                targetIds.add(target.getNodeNo());
            }

            System.out.println("Station " + i + " targets: " + targetIds);
            System.out.println("-----------------------------------------------");
        }
        //初始路径生成
        List<List<List<List<Node>>>> route1 = Init.generateRoutes1(stationNodes, stationTypes,allocations,SMALL_DRONE_BATTERY,
                LARGE_DRONE_BATTERY,LARGE_DRONE_CONS,SMALL_STATION_TIME,LARGE_STATION_TIME,DRONE_SPEED);

        initSolution.setNodeMatrix(route1);
        System.out.println("--------------------");
        System.out.println(initSolution);


        boolean is_timeTrue=Check.checkStationOperation(initSolution.getNodeMatrix(),DRONE_SPEED,LARGE_STATION_TIME,SMALL_STATION_TIME,stationTypes);

        System.out.println("Time feasible:"+is_timeTrue);

        boolean is_EnergyTrue = Check.isOverallSolutionValid(route1,stationTypes,LARGE_DRONE_BATTERY,SMALL_DRONE_BATTERY,DRONE_SPEED,LARGE_DRONE_CONS);
        System.out.println("Energy feasible:"+is_EnergyTrue);
        System.out.println("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++");

        Check.printRemainingBattery(route1,DRONE_SPEED,LARGE_DRONE_BATTERY,SMALL_DRONE_BATTERY,LARGE_DRONE_CONS,stationTypes);
        //Check.printAllRoutes(route1);
        System.out.println("----------------------------------------------------");

        //System.out.println(initSolution);

//*******************************************************************Stage1——location optimization*************************************************************************

        Random random = new Random();
        int[] initStationType = stationTypes.clone();
        List<List<List<List<Node>>>> initRoute =Check.deepCopyRoute(route1);

        // deep copy
        Solution currentSolution = new Solution();
        int[] currentStationType = initStationType.clone();
        List<List<List<List<Node>>>> currentRoute =Check.deepCopyRoute(initRoute);
        currentSolution.setStationTypes(currentStationType);
        currentSolution.setNodeMatrix(new ArrayList<>(initSolution.getNodeMatrix()));


        /*        double currentCost = Calculator.calculateLRP(currentSolution.getNodeMatrix(),currentSolution.getStationTypes(),use,LRPstationCost,1);*/
        double currentCost=Check.calculateTotalCost(initRoute,initStationType,LARGE_SITE_COST,SMALL_SITE_COST,LARGE_DRONE_COST,SMALL_DRONE_COST,FLIGHT_COST_PER_MIN,DRONE_SPEED);

        double bestCost = currentCost;

        //Initialize the best colution
        Solution bestSolution1 = new Solution();
        bestSolution1.setNodeMatrix(initRoute);
        bestSolution1.setStationTypes(initStationType);
        System.out.println("The obj of initial solution:"+currentCost);




        double temperature = INITIAL_TEMPERATURE;

        for (int iter = 0; iter < MAX_ITERATIONS; iter++) {
            //System.out.println(iter);
            // **1. select new station **
            int[] newStationType = LocationOperator.applyRandomNeighborhood(currentSolution.getStationTypes());
            //System.out.println("The solution of new station is feasible?"+LocationOperator.isFeasible(targetNodes, stationNodes, newStationType, SMALL_RADIUS, LARGE_RADIUS));
            //System.out.println("-------------------------------------------------------------------------");

            // **2. is feasible or not**
            if (!LocationOperator.isFeasible(targetNodes, stationNodes, newStationType, SMALL_RADIUS, LARGE_RADIUS)) {
                continue;
            }


            // **3. generate new routes for the new station decision**
            List<List<List<List<Node>>>> newRoutes = Init.generateRoutes1(stationNodes, newStationType,
                    allocateTargetsToStations(targetNodes, stationNodes, newStationType, SMALL_RADIUS, LARGE_RADIUS),
                    SMALL_DRONE_BATTERY, LARGE_DRONE_BATTERY, LARGE_DRONE_CONS,
                    SMALL_STATION_TIME, LARGE_STATION_TIME, DRONE_SPEED);

            boolean isSolutionF= Check.isOverallSolutionValid(newRoutes,newStationType,LARGE_DRONE_BATTERY,SMALL_DRONE_BATTERY,DRONE_SPEED,LARGE_DRONE_CONS);


            //System.out.println("The routes solution is feasible before optimize："+isSolutionF);

            if(!isSolutionF){
                continue;
            }

            // **4. local search **
            for (int i = 0; i < 100; i++) {
                int operator = random.nextInt(5); // randomly select swap opertaors
                switch (operator) {
                    case 0:
                        newRoutes = RoutingOperator.swap1(newRoutes, newStationType, LARGE_DRONE_BATTERY,
                                SMALL_DRONE_BATTERY, DRONE_SPEED, LARGE_DRONE_CONS);
                        break;
                    case 1:
                        newRoutes = RoutingOperator.swap2(newRoutes, newStationType, LARGE_DRONE_BATTERY,
                                SMALL_DRONE_BATTERY, DRONE_SPEED, LARGE_DRONE_CONS);
                        break;
                    case 2:
                        newRoutes = RoutingOperator.swap3(newRoutes, newStationType, LARGE_DRONE_BATTERY, SMALL_DRONE_BATTERY,
                                DRONE_SPEED, LARGE_DRONE_CONS, LARGE_STATION_TIME, SMALL_STATION_TIME
                        );
                        break;
                    case 3:
                        newRoutes = RoutingOperator.swap4(newRoutes, newStationType, LARGE_DRONE_BATTERY,
                                SMALL_DRONE_BATTERY, DRONE_SPEED, LARGE_DRONE_CONS,
                                LARGE_STATION_TIME, SMALL_STATION_TIME);
                        break;
                    case 4:
                        newRoutes = RoutingOperator.twoOptOperator(newRoutes);
                        break;

                }
            }


            ALNSSolver solver = new ALNSSolver();
            newRoutes = solver.solve(
                    newRoutes,
                    newStationType,
                    LARGE_DRONE_BATTERY,
                    SMALL_DRONE_BATTERY,
                    DRONE_SPEED,
                    LARGE_DRONE_CONS,
                    LARGE_STATION_TIME,
                    SMALL_STATION_TIME,
                    SMALL_RADIUS,
                    LARGE_RADIUS,
                    stationNodes);


            double newCost = Check.calculateTotalCost(newRoutes,newStationType,LARGE_SITE_COST,SMALL_SITE_COST,LARGE_DRONE_COST,SMALL_DRONE_COST,FLIGHT_COST_PER_MIN,DRONE_SPEED);
            /*            double newCost = Calculator.calculateLRP(newRoutes,newStationType,use,LRPstationCost,1);*/
            //System.out.println("Current Obj"+newCost);


            double acceptanceProbability = (newCost < currentCost) ? 1.0 : Math.exp((currentCost - newCost) / temperature);

            if (acceptanceProbability > random.nextDouble()) {


                currentSolution.setStationTypes(newStationType);
                currentSolution.setNodeMatrix(newRoutes);
                currentStationType = currentSolution.getStationTypes();
                currentRoute = currentSolution.getNodeMatrix();
                currentCost = newCost;


                if (currentCost < bestCost) {
                    bestSolution1.setStationTypes(currentStationType);
                    bestSolution1.setNodeMatrix(currentRoute);
                    bestCost = currentCost;
                }
            }
            //System.out.println("Current best obj："+bestCost);


            temperature *= COOLING_RATE;
            //System.out.println("Current temperature:"+temperature);

        }

        System.out.println("----------------------------------------------------");
        System.out.println("----------------------------------------------------");
        System.out.println("--------------------Final results-------------------");


        for (int i = 0; i < bestSolution1.getStationTypes().length; i++) {
            int type = bestSolution1.getStationTypes()[i];
            String typeName;

            if (type == 0) {
                typeName = "Closed";
            } else if (type == 1) {
                typeName = "Small Station";
            } else if (type == 2) {
                typeName = "Large Station";
            } else {
                typeName = "Unknown";
            }

            System.out.println("Station " + i + ": " + typeName + " (" + type + ")");
        }
        //System.out.println("Is solution right?:"+Check.isOverallSolutionValid(bestSolution1.getNodeMatrix(),bestSolution1.getStationTypes(),LARGE_DRONE_BATTERY,SMALL_DRONE_BATTERY,DRONE_SPEED,LARGE_DRONE_CONS));
        //printAllRoutes(initSolution.getNodeMatrix());
        System.out.println("----------------------------------------------------");
        printAllRoutes(bestSolution1.getNodeMatrix());

        System.out.println("Obj:"+bestCost);
                System.out.println("Total cost: " + Check.calculateTotalCost(
                bestSolution1.getNodeMatrix(),
                bestSolution1.getStationTypes(),
                LARGE_SITE_COST,
                SMALL_SITE_COST,
                LARGE_DRONE_COST,
                SMALL_DRONE_COST,
                FLIGHT_COST_PER_MIN,
                DRONE_SPEED
        ));
        System.out.println("-----------------------------------------------");

        double latestTime = Check.calculateLatestTime(bestSolution1.getNodeMatrix(),DRONE_SPEED);
        System.out.println("latest completion time:"+latestTime);

        long endTime = System.currentTimeMillis();
        long totalTime = endTime - startTime;
        //System.out.println("Algorithm: " + totalTime + " ms");
        System.out.println("The time of algorithm execution: " + (totalTime / 1000.0) + " s");
        System.out.println("Initial solution: ");
        System.out.println(Check.calculateTotalCost(initSolution.getNodeMatrix(),initStationType,LARGE_SITE_COST,
                SMALL_SITE_COST,LARGE_DRONE_COST,SMALL_DRONE_COST,FLIGHT_COST_PER_MIN,DRONE_SPEED));

    }



}


