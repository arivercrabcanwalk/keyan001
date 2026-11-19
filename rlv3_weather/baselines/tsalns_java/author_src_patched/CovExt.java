package test1;
import java.util.*;
import java.io.*;

/** v3 reviewer-requested ADAPTATION of the author's TSALNS to the strict-emergency scenario (Liu et al. code otherwise
 *  unchanged). -Dcovfile=<file with "x y" per line>: extra emergency-support points that the siting must cover
 *  (hard constraint added to LocationOperator.isFeasible, same radii as the author's target-coverage constraint);
 *  infeasible initial sitings are repaired greedily (author-style greedy: open/upgrade the station covering most
 *  uncovered points). -Dfixtypes=2,2,0,...: siting fixed (routing stage of TSALNS only, used for site-parity arms). */
public class CovExt {
    static double[][] pts = null;
    static int[] fix = null;
    static {
        String f = System.getProperty("covfile", "");
        if (!f.isEmpty()) {
            List<double[]> l = new ArrayList<>();
            try (BufferedReader br = new BufferedReader(new FileReader(f))) {
                String s;
                while ((s = br.readLine()) != null) {
                    s = s.trim(); if (s.isEmpty()) continue;
                    String[] a = s.split("\\s+");
                    l.add(new double[]{Double.parseDouble(a[0]), Double.parseDouble(a[1])});
                }
            } catch (IOException e) { throw new RuntimeException("covfile: " + e); }
            pts = l.toArray(new double[0][]);
        }
        String t = System.getProperty("fixtypes", "");
        if (!t.isEmpty()) {
            String[] a = t.split(",");
            fix = new int[a.length];
            for (int i = 0; i < a.length; i++) fix[i] = Integer.parseInt(a[i].trim());
        }
    }
    static boolean covered(Node[] st, int[] ty, double rs, double rl) {
        if (pts == null) return true;
        for (double[] p : pts) {
            boolean ok = false;
            for (int i = 0; i < st.length && !ok; i++) {
                if (ty[i] == 0) continue;
                double r = (ty[i] == 1) ? rs : rl;
                double dx = st[i].getX() - p[0], dy = st[i].getY() - p[1];
                if (Math.sqrt(dx * dx + dy * dy) <= r + 1e-6) ok = true;
            }
            if (!ok) return false;
        }
        return true;
    }
    static int[] repair(Node[] st, int[] ty0, double rs, double rl) {
        int[] ty = ty0.clone();
        int guard = 0;
        while (!covered(st, ty, rs, rl) && guard++ < 4 * st.length) {
            int best = -1, bestc = -1;
            for (int i = 0; i < st.length; i++) {
                if (ty[i] == 2) continue;
                int c = 0;
                for (double[] p : pts) {
                    boolean cov = false;
                    for (int k = 0; k < st.length && !cov; k++) {
                        if (ty[k] == 0) continue;
                        double r = (ty[k] == 1) ? rs : rl;
                        double dx = st[k].getX() - p[0], dy = st[k].getY() - p[1];
                        if (Math.sqrt(dx * dx + dy * dy) <= r + 1e-6) cov = true;
                    }
                    if (cov) continue;
                    double dx = st[i].getX() - p[0], dy = st[i].getY() - p[1];
                    if (Math.sqrt(dx * dx + dy * dy) <= rl + 1e-6) c++;
                }
                if (c > bestc) { bestc = c; best = i; }
            }
            if (best < 0) break;
            ty[best] = 2;
        }
        return ty;
    }
}
