package rnd.method.parser.call.graph.service;

import com.github.javaparser.JavaParser;
import com.github.javaparser.ParseResult;
import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.body.CallableDeclaration;
import com.github.javaparser.ast.body.ConstructorDeclaration;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.ast.expr.AnnotationExpr;
import com.google.gson.Gson;
import lombok.extern.slf4j.Slf4j;
import rnd.method.parser.call.graph.model.MethodMetadata;
import rnd.method.parser.call.graph.util.JavaParserContext;
import rnd.method.parser.call.graph.util.MethodParserUtil;

import java.io.File;
import java.io.FileNotFoundException;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

@Slf4j
public class MethodMetadataScannerImpl implements MethodMetadataScanner {
    private static final Gson GSON = new Gson();

    private String repoRoot;
    private String repoUrl;
    private String commitHash;
    private String repositoryName;
    private JavaParser parserWithSymbolResolver;

    private MethodMetadataScannerImpl() {
    }

    public static MethodMetadataScannerImpl getInstance() {
        return new MethodMetadataScannerImpl();
    }

    @Override
    public synchronized void init(
            String projectName,
            String repoRoot,
            String repoUrl,
            String commitHash,
            boolean checkoutRepository) {
        if (parserWithSymbolResolver != null) {
            throw new IllegalStateException("MethodMetadataScannerImpl.init must be called exactly once");
        }
        if (projectName == null || projectName.isBlank()) {
            throw new IllegalArgumentException("Project name is required");
        }
        if (checkoutRepository) {
            MethodParserUtil.prepareRepositoryForCommit(repoUrl, repoRoot, commitHash);
        }

        JavaParserContext parserContext = JavaParserContext.create(Path.of(repoRoot), commitHash);
        this.repoRoot = repoRoot;
        this.repoUrl = repoUrl;
        this.commitHash = commitHash;
        this.repositoryName = projectName.trim();
        this.parserWithSymbolResolver = parserContext.parser();
    }

    @Override
    public List<MethodMetadata> scanMethodMetadata(String file) {
        if (parserWithSymbolResolver == null) {
            throw new IllegalStateException(
                    "MethodMetadataScannerImpl.init must be called before scanMethodMetadata");
        }

        File javaFile = Path.of(repoRoot, file).toFile();
        ParseResult<CompilationUnit> parseResult;
        try {
            parseResult = parserWithSymbolResolver.parse(javaFile);
        } catch (FileNotFoundException error) {
            throw new IllegalStateException("Unable to read Java source file: " + file, error);
        }
        if (!parseResult.isSuccessful()) {
            throw new IllegalStateException(
                    "Unable to parse Java source file " + file + ": " + parseResult.getProblems());
        }
        CompilationUnit compilationUnit = parseResult.getResult().orElseThrow(
                () -> new IllegalStateException(
                        "Unable to parse Java source file " + file + ": " + parseResult.getProblems()));

        List<MethodMetadata> result = new ArrayList<>();
        compilationUnit.walk(node -> {
            if (node instanceof MethodDeclaration method) {
                result.add(buildMetadata(method, compilationUnit, file));
            } else if (node instanceof ConstructorDeclaration constructor) {
                result.add(buildMetadata(constructor, compilationUnit, file));
            }
        });
        return result;
    }

    private MethodMetadata buildMetadata(
            CallableDeclaration<?> declaration,
            CompilationUnit compilationUnit,
            String file) {
        List<String> annotations = new ArrayList<>();
        List<String> annotationsFqn = new ArrayList<>();
        for (AnnotationExpr annotation : declaration.getAnnotations()) {
            annotations.add(annotationSourceWithoutPrefix(annotation));
            annotationsFqn.add(resolveAnnotationFqn(annotation, compilationUnit));
        }

        int startLine = declaration.getName().getBegin().map(position -> position.line).orElse(-1);
        String url = MethodParserUtil.toMethodUrl(repoUrl, commitHash, file, startLine);
        String javadoc = declaration.getJavadocComment()
                .flatMap(comment -> comment.getTokenRange())
                .map(Object::toString)
                .orElse("");

        return MethodMetadata.builder()
                .repositoryName(repositoryName)
                .name(declaration.getNameAsString())
                .url(url)
                .annotations(GSON.toJson(annotations))
                .annotationsFqn(GSON.toJson(annotationsFqn))
                .javadoc(javadoc)
                .build();
    }

    private static String annotationSourceWithoutPrefix(AnnotationExpr annotation) {
        String source = annotation.getTokenRange()
                .map(Object::toString)
                .orElseGet(annotation::toString)
                .strip();
        return source.startsWith("@") ? source.substring(1) : source;
    }

    private static String resolveAnnotationFqn(
            AnnotationExpr annotation,
            CompilationUnit compilationUnit) {
        try {
            return annotation.resolve().getQualifiedName();
        } catch (RuntimeException error) {
            String simpleName = annotation.getNameAsString();
            String importedName = compilationUnit.getImports().stream()
                    .filter(importDeclaration -> !importDeclaration.isAsterisk())
                    .map(importDeclaration -> importDeclaration.getNameAsString())
                    .filter(name -> name.endsWith("." + simpleName))
                    .findFirst()
                    .orElse("");
            if (!importedName.isEmpty()) {
                return importedName;
            }
            log.debug(
                    "method-metadata annotation resolution failed annotation={} error={}",
                    simpleName,
                    error.toString());
            return "";
        }
    }
}
