package test1;
import java.util.Random;
public final class ReplayRandom {
 public static final Random RNG=new Random(Long.getLong("repro.seed",0L));
 private static long start=System.nanoTime();
 public static void start(){start=System.nanoTime();}
 public static boolean inBudget(){double seconds=Double.parseDouble(System.getProperty("repro.seconds","0"));return seconds<=0 || (System.nanoTime()-start)/1e9<seconds;}
}
