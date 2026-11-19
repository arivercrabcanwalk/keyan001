package test1;

import java.io.*;
import java.util.ArrayList;
import java.util.List;

public class FileReaderUtil {

    public static List<Node> readNodesFromFile(String filePath) {
        List<Node> nodes = new ArrayList<>();

        try (BufferedReader br = new BufferedReader(new FileReader(filePath))) {
            String line;
            boolean isHeader = true;

            while ((line = br.readLine()) != null) {

                if (isHeader) {
                    isHeader = false;
                    continue;
                }

                String[] parts = line.trim().split("\\s+");
                if (parts.length < 5) {
                    continue;
                }


                int custNo = Integer.parseInt(parts[0]);
                double xCoord = Double.parseDouble(parts[1]);
                double yCoord = Double.parseDouble(parts[2]);
                double serviceEnergy = Double.parseDouble(parts[3]);
                double serviceTime = Double.parseDouble(parts[4]);


                Node node = new Node(custNo, xCoord, yCoord, serviceEnergy, serviceTime);
                nodes.add(node);
            }
        } catch (IOException e) {
            System.err.println("Something wrong in reading files:" + e.getMessage());
        } catch (NumberFormatException e) {
            System.err.println("Something wrong in getting data: " + e.getMessage());
        }

        return nodes;



    }

}
