import com.google.gson.Gson;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import rnd.method.parser.call.graph.model.MethodMetadata;
import rnd.method.parser.call.graph.service.MethodMetadataScannerImpl;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

public class MethodMetadataScannerTest {
    private static final Gson GSON = new Gson();

    @TempDir
    Path tempDir;

    @Test
    void extractsMethodAndConstructorMetadata() throws Exception {
        Path sourceFile = tempDir.resolve("src/main/java/demo/Demo.java");
        Files.createDirectories(sourceFile.getParent());
        Files.writeString(
                sourceFile,
                """
                        package demo;

                        import org.junit.jupiter.api.Test;

                        @interface Tag {
                            String value();
                        }

                        class Demo {
                            /**
                             * Runs quickly.
                             * @return nothing
                            */
                            @Test
                            @Deprecated
                            @Tag(
                                value = "fast"
                            )
                            void run() {
                            }

                            @Missing
                            Demo() {
                            }

                            void plain() {
                            }
                        }
                        """);

        MethodMetadataScannerImpl scanner = MethodMetadataScannerImpl.getInstance();
        scanner.init(
                "demo-project",
                tempDir.toString(),
                "https://github.com/example/demo",
                "abc123",
                false);

        List<MethodMetadata> metadata = scanner.scanMethodMetadata("src/main/java/demo/Demo.java");
        MethodMetadata run = metadata.stream()
                .filter(row -> row.getName().equals("run"))
                .findFirst()
                .orElseThrow();
        MethodMetadata constructor = metadata.stream()
                .filter(row -> row.getName().equals("Demo"))
                .findFirst()
                .orElseThrow();
        MethodMetadata plain = metadata.stream()
                .filter(row -> row.getName().equals("plain"))
                .findFirst()
                .orElseThrow();

        assertEquals(
                List.of("Test", "Deprecated", "Tag(\n        value = \"fast\"\n    )"),
                parseJsonArray(run.getAnnotations()));
        assertEquals(
                List.of("org.junit.jupiter.api.Test", "java.lang.Deprecated", "demo.Tag"),
                parseJsonArray(run.getAnnotationsFqn()));
        assertEquals(
                "/**\n     * Runs quickly.\n     * @return nothing\n    */",
                run.getJavadoc());
        assertTrue(run.getUrl().startsWith(
                "https://github.com/example/demo/blob/abc123/src/main/java/demo/Demo.java#L"));

        assertEquals(List.of("Missing"), parseJsonArray(constructor.getAnnotations()));
        assertEquals(List.of(""), parseJsonArray(constructor.getAnnotationsFqn()));
        assertEquals("", constructor.getJavadoc());

        assertEquals(List.of(), parseJsonArray(plain.getAnnotations()));
        assertEquals(List.of(), parseJsonArray(plain.getAnnotationsFqn()));
        assertEquals("", plain.getJavadoc());
    }

    @Test
    void reportsParseFailures() throws Exception {
        Path sourceFile = tempDir.resolve("Broken.java");
        Files.writeString(sourceFile, "class Broken { void run( {");

        MethodMetadataScannerImpl scanner = MethodMetadataScannerImpl.getInstance();
        scanner.init(
                "demo-project",
                tempDir.toString(),
                "https://github.com/example/demo",
                "abc123",
                false);

        assertThrows(
                IllegalStateException.class,
                () -> scanner.scanMethodMetadata("Broken.java"));
    }

    private static List<String> parseJsonArray(String value) {
        return List.of(GSON.fromJson(value, String[].class));
    }
}
