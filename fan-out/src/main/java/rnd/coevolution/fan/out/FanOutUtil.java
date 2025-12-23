package rnd.coevolution.fan.out;

import lombok.extern.slf4j.Slf4j;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

@Slf4j
public class FanOutUtil {
    public static List<String> expandPath(String repositoryPath, List<String> targetPaths) {
        List<String> files = new ArrayList<>();
        Path repoRoot = Paths.get(repositoryPath);

        for (String target : targetPaths) {
            Path path = repoRoot.resolve(target).normalize();
            if (Files.exists(path)) {
                try {
                    if (Files.isRegularFile(path) && path.toString().endsWith(".java")) {
                        files.add(path.toString());
                    } else if (Files.isDirectory(path)) {
                        Files.walk(path)
                                .filter(Files::isRegularFile)
                                .filter(p -> p.toString().endsWith(".java"))
                                .forEach(p -> files.add(p.toString()));
                    }
                } catch (IOException e) {
                    log.error("Failed to scan path {}", path, e);
                }
            }
        }
        Collections.sort(files);
        return files;
    }

    public static String toMethodUri(String file, Integer lineNumber) {
        return file + (lineNumber != null ? "#L" + lineNumber : "");
    }
}
