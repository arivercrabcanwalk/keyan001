package test1;
/** Transparent engineering wrapper; Main and its parameters remain unchanged. */
public final class FullSolveEntry {
    public static void main(String[] args) throws Exception {
        Main.main(args);
        System.out.println("FULL_MAIN_RETURNED=true");
        long delay = Long.getLong("engineering.postMainDelayMillis", 0L);
        if (delay > 0) {
            System.out.println("ENGINEERING_POST_MAIN_DELAY_MS=" + delay);
            System.out.flush();
            Thread.sleep(delay);
        }
    }
}
