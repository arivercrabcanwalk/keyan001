package test1;
import java.nio.file.*;
import java.util.*;
public final class FinalRecorderProbe {
    private static List<List<List<List<Node>>>> routes(Node base,Node a,Node b,boolean swap) {
        List<List<List<List<Node>>>> r=new ArrayList<>();
        List<List<List<Node>>> ds=new ArrayList<>();
        ds.add(new ArrayList<>(List.of(new ArrayList<>(List.of(base,swap?b:a,base)))));
        ds.add(new ArrayList<>(List.of(new ArrayList<>(List.of(base,swap?a:b,base)))));
        r.add(ds);return r;
    }
    public static void main(String[] args) throws Exception {
        Node base=new Node(100,0,0,0,0),a=new Node(1,100,50,.1,2),b=new Node(2,-80,120,.1,3);
        Node[] targets={a,b},stations={base};int[] types={2};
        double cost=100.0, next=switch(args[0]) {
            case "equal" -> cost;
            case "tiny" -> cost-5e-13;
            case "improve" -> cost-1;
            default -> throw new IllegalArgumentException(args[0]);
        };
        Solution first=new Solution();first.setStationTypes(types);first.setNodeMatrix(routes(base,a,b,false));
        Solution last=new Solution();last.setStationTypes(types);last.setNodeMatrix(routes(base,a,b,true));
        ReferenceRecorder.save(first,targets,stations,cost);
        ReferenceRecorder.save(last,targets,stations,next);
        boolean finalMethod=true;
        try {
            ReferenceRecorder.class.getMethod("saveFinal",Solution.class,Node[].class,Node[].class,double.class)
                .invoke(null,last,targets,stations,next);
        } catch (NoSuchMethodException absent) {finalMethod=false;}
        String actual=Files.readString(Path.of(System.getProperty("repro.output"))).trim();
        String expected=ReferenceRecorder.encode(types,last.getNodeMatrix(),targets,stations,next);
        System.out.println("CASE="+args[0]+" FINAL_METHOD="+finalMethod+" FINAL_ROUTE_MATCH="+actual.equals(expected));
    }
}
