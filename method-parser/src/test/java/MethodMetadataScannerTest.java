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

    @Test
    void classifiesTestFrameworkCandidatesAndQuickTheoriesChains() throws Exception {
        Path sourceFile = tempDir.resolve("src/test/java/demo/Frameworks.java");
        Files.createDirectories(sourceFile.getParent());
        Files.writeString(
                sourceFile,
                """
                        package demo;

                        import org.junit.jupiter.api.Test;
                        import static org.quicktheories.QuickTheory.qt;

                        class Frameworks {
                            @Test void quickTheories() {
                                qt().withFixedSeed(0).withExamples(5).forAll(source());
                            }

                            @Test void missingForAll() {
                                qt().withFixedSeed(0);
                            }

                            @net.jqwik.api.Property void jqwikProperty() {}
                            @net.jqwik.api.Example void jqwikExample() {}
                            @com.pholser.junit.quickcheck.Property void quickcheck() {}
                            @org.testng.annotations.Test void testNg() {}

                            Object source() { return null; }
                        }

                        class Legacy extends junit.framework.TestCase {
                            public void testLegacy() {}
                        }
                        """);

        MethodMetadataScannerImpl scanner = MethodMetadataScannerImpl.getInstance();
        scanner.init(
                "demo-project",
                tempDir.toString(),
                "https://github.com/example/demo",
                "abc123",
                false);

        List<MethodMetadata> metadata = scanner.scanMethodMetadata("src/test/java/demo/Frameworks.java");
        assertFrameworks(metadata, "quickTheories", "#junit #quicktheories");
        assertFrameworks(metadata, "missingForAll", "#junit");
        assertFrameworks(metadata, "jqwikProperty", "#jqwik");
        assertFrameworks(metadata, "jqwikExample", "#jqwik");
        assertFrameworks(metadata, "quickcheck", "#junit #quickcheck");
        assertFrameworks(metadata, "testNg", "#testng");
        assertFrameworks(metadata, "testLegacy", "#junit");
    }

    @Test
    void doesNotTreatUnrelatedQtAsQuickTheories() throws Exception {
        Path sourceFile = tempDir.resolve("LocalQt.java");
        Files.writeString(
                sourceFile,
                """
                        class LocalQt {
                            Chain qt() { return new Chain(); }
                            void property() { qt().forAll(); }
                        }
                        class Chain { void forAll() {} }
                        """);

        MethodMetadataScannerImpl scanner = MethodMetadataScannerImpl.getInstance();
        scanner.init(
                "demo-project",
                tempDir.toString(),
                "https://github.com/example/demo",
                "abc123",
                false);

        List<MethodMetadata> metadata = scanner.scanMethodMetadata("LocalQt.java");
        assertFrameworks(metadata, "property", "");
    }

    private static void assertFrameworks(List<MethodMetadata> metadata, String name, String expected) {
        MethodMetadata row = metadata.stream()
                .filter(value -> value.getName().equals(name))
                .findFirst()
                .orElseThrow();
        assertEquals(expected, row.getFrameworks());
    }

    private static List<String> parseJsonArray(String value) {
        return List.of(GSON.fromJson(value, String[].class));
    }
}
