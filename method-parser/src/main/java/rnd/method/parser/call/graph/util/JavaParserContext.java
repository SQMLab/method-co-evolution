package rnd.method.parser.call.graph.util;

import com.github.javaparser.JavaParser;
import com.github.javaparser.ParserConfiguration;
import com.github.javaparser.StaticJavaParser;
import com.github.javaparser.symbolsolver.JavaSymbolSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.CombinedTypeSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.JavaParserTypeSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.ReflectionTypeSolver;
import lombok.extern.slf4j.Slf4j;

import java.nio.file.Path;
import java.util.List;

@Slf4j
public final class JavaParserContext {
    private final JavaParser parser;
    private final CombinedTypeSolver typeSolver;
    private final ParserConfiguration configuration;

    private JavaParserContext(JavaParser parser, CombinedTypeSolver typeSolver, ParserConfiguration configuration) {
        this.parser = parser;
        this.typeSolver = typeSolver;
        this.configuration = configuration;
    }

    public static JavaParserContext create(Path repoRoot) {
        return create(repoRoot, null, false);
    }

    public static JavaParserContext create(Path repoRoot, String commitHash) {
        return create(repoRoot, commitHash, false);
    }

    public static JavaParserContext create(Path repoRoot, boolean reflectionTypeSolverJreOnly) {
        return create(repoRoot, null, reflectionTypeSolverJreOnly);
    }

    public static JavaParserContext create(Path repoRoot, String commitHash, boolean reflectionTypeSolverJreOnly) {
        long startedAt = System.nanoTime();
        CombinedTypeSolver typeSolver = new CombinedTypeSolver();
        typeSolver.add(new ReflectionTypeSolver(reflectionTypeSolverJreOnly));

        long sourceRootStartedAt = System.nanoTime();
        List<Path> javaSourceRoots = MethodParserUtil.findAllJavaSourceRoots(repoRoot, commitHash);
        log.info(
                "JavaParserContext source-root discovery repoRoot={} commit={} roots={} elapsed_seconds={}",
                repoRoot,
                commitHash,
                javaSourceRoots.size(),
                secondsSince(sourceRootStartedAt)
        );

        long typeSolverStartedAt = System.nanoTime();
        if (javaSourceRoots.isEmpty()) {
            typeSolver.add(new JavaParserTypeSolver(repoRoot.toFile()));
        } else {
            for (Path javaSourceRoot : javaSourceRoots) {
                typeSolver.add(new JavaParserTypeSolver(javaSourceRoot.toFile()));
            }
        }
        log.info(
                "JavaParserContext type-solver setup repoRoot={} roots_added={} elapsed_seconds={}",
                repoRoot,
                javaSourceRoots.isEmpty() ? 1 : javaSourceRoots.size(),
                secondsSince(typeSolverStartedAt)
        );

        long configurationStartedAt = System.nanoTime();
        ParserConfiguration configuration = new ParserConfiguration()
                .setSymbolResolver(new JavaSymbolSolver(typeSolver))
                .setLanguageLevel(ParserConfiguration.LanguageLevel.BLEEDING_EDGE);

        StaticJavaParser.setConfiguration(configuration);
        log.info(
                "JavaParserContext parser configuration repoRoot={} elapsed_seconds={} total_elapsed_seconds={}",
                repoRoot,
                secondsSince(configurationStartedAt),
                secondsSince(startedAt)
        );
        return new JavaParserContext(new JavaParser(configuration), typeSolver, configuration);
    }

    public static JavaParserContext createParserOnly(Path repoRoot) {
        long startedAt = System.nanoTime();
        CombinedTypeSolver typeSolver = new CombinedTypeSolver();
        ParserConfiguration configuration = new ParserConfiguration()
                .setLanguageLevel(ParserConfiguration.LanguageLevel.BLEEDING_EDGE);

        log.info(
                "JavaParserContext parser-only configuration repoRoot={} total_elapsed_seconds={}",
                repoRoot,
                secondsSince(startedAt)
        );
        return new JavaParserContext(new JavaParser(configuration), typeSolver, configuration);
    }

    public JavaParser parser() {
        return parser;
    }

    public CombinedTypeSolver typeSolver() {
        return typeSolver;
    }

    public ParserConfiguration configuration() {
        return configuration;
    }

    private static double secondsSince(long startedAt) {
        return (System.nanoTime() - startedAt) / 1_000_000_000.0;
    }
}
