import lombok.extern.slf4j.Slf4j;
import org.jspecify.annotations.NonNull;
import org.junit.jupiter.api.*;
import rnd.coevolution.fan.out.model.Fan;
import rnd.coevolution.fan.out.service.FanOutServiceImpl;

import java.util.Arrays;
import java.util.List;

/**
 * @author Shahidul Islam
 * @since 2025-12-23
 */
@Slf4j
public class FanOutTest {


    //TODO:
//    @TestFactory
//    public DynamicNode randomPathTest() {
//
//
//    }

    @TestFactory
    public DynamicNode testCheckStyle() {
        return createDynamicTest("../../repository/checkstyle", List.of("src/main/java/com/puppycrawl/tools/checkstyle/Checker.java"/*,
                "src/main/java/com/puppycrawl/tools/checkstyle/ModuleFactory.java",
                "src/main/java/com/puppycrawl/tools/checkstyle/ant",
                "src/main/java/com/puppycrawl/tools/checkstyle/utils"*/
        ));

    }


    @TestFactory
    public DynamicNode testFlink() {
        return createDynamicTest("../../repository/flink", List.of("flink-tests/src/test/java/org/apache/flink/test/accumulators/"));
    }

    private static @NonNull DynamicContainer createDynamicTest(String repositoryPath, List<String> targetPaths) {
        FanOutServiceImpl fanOutService = new FanOutServiceImpl(repositoryPath, List.of("."));
        return DynamicContainer.dynamicContainer(Arrays.stream(repositoryPath.split("/")).toList().getLast(),
                targetPaths
                        .stream()
                        .map(path -> DynamicTest.dynamicTest(path, () -> {
                            List<Fan> fanOut = fanOutService.findOut(repositoryPath, List.of(path));
                            fanOut.forEach(System.out::println);
                            Assertions.assertFalse(fanOut.isEmpty());
                        })));
    }
}
