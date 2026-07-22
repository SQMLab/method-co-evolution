package rnd.method.parser.call.graph.service;

import com.github.javaparser.JavaParser;
import com.github.javaparser.ParseResult;
import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.body.CallableDeclaration;
import com.github.javaparser.ast.body.ClassOrInterfaceDeclaration;
import com.github.javaparser.ast.body.ConstructorDeclaration;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.ast.expr.AnnotationExpr;
import com.github.javaparser.ast.expr.Expression;
import com.github.javaparser.ast.expr.MethodCallExpr;
import com.github.javaparser.ast.expr.NameExpr;
import com.google.gson.Gson;
import lombok.extern.slf4j.Slf4j;
import rnd.method.parser.call.graph.model.MethodMetadata;
import rnd.method.parser.call.graph.util.JavaParserContext;
import rnd.method.parser.call.graph.util.MethodParserUtil;

import java.io.File;
import java.io.FileNotFoundException;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Optional;
import java.util.Set;

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
        String frameworks = detectFrameworks(declaration, compilationUnit, annotationsFqn);

        return MethodMetadata.builder()
                .repositoryName(repositoryName)
                .name(declaration.getNameAsString())
                .url(url)
                .annotations(GSON.toJson(annotations))
                .annotationsFqn(GSON.toJson(annotationsFqn))
                .frameworks(frameworks)
                .javadoc(javadoc)
                .build();
    }

    private static String detectFrameworks(
            CallableDeclaration<?> declaration,
            CompilationUnit compilationUnit,
            List<String> annotationsFqn) {
        Set<String> detected = new LinkedHashSet<>();
        for (String annotation : annotationsFqn) {
            if (annotation.startsWith("org.junit.") || annotation.startsWith("org.junit.jupiter.")) {
                detected.add("junit");
            } else if (annotation.startsWith("org.testng.")) {
                detected.add("testng");
            }
            if (annotation.equals("net.jqwik.api.Property") || annotation.equals("net.jqwik.api.Example")) {
                detected.add("jqwik");
            }
            if (annotation.equals("com.pholser.junit.quickcheck.Property")) {
                detected.add("junit");
                detected.add("quickcheck");
            }
        }
        if (isJUnit3Callable(declaration, compilationUnit)) {
            detected.add("junit");
        }
        if (usesQuickTheories(declaration, compilationUnit)) {
            detected.add("quicktheories");
        }

        List<String> order = List.of("junit", "testng", "jqwik", "quickcheck", "quicktheories");
        return order.stream()
                .filter(detected::contains)
                .map(value -> "#" + value)
                .reduce((left, right) -> left + " " + right)
                .orElse("");
    }

    private static boolean isJUnit3Callable(
            CallableDeclaration<?> declaration,
            CompilationUnit compilationUnit) {
        Optional<ClassOrInterfaceDeclaration> enclosing = declaration.findAncestor(ClassOrInterfaceDeclaration.class);
        if (enclosing.isEmpty()) {
            return false;
        }
        ClassOrInterfaceDeclaration type = enclosing.get();
        try {
            return type.resolve().getAllAncestors().stream()
                    .anyMatch(ancestor -> ancestor.getQualifiedName().equals("junit.framework.TestCase"));
        } catch (RuntimeException ignored) {
            return type.getExtendedTypes().stream().anyMatch(parent -> {
                String name = parent.getNameWithScope();
                return name.equals("junit.framework.TestCase")
                        || (name.equals("TestCase") && hasImport(compilationUnit, "junit.framework.TestCase"));
            });
        }
    }

    private static boolean usesQuickTheories(
            CallableDeclaration<?> declaration,
            CompilationUnit compilationUnit) {
        for (MethodCallExpr forAll : declaration.findAll(MethodCallExpr.class)) {
            if (!forAll.getNameAsString().equals("forAll") || !belongsToCallable(forAll, declaration)) {
                continue;
            }
            Optional<Expression> scope = forAll.getScope();
            while (scope.isPresent() && scope.get().isMethodCallExpr()) {
                MethodCallExpr call = scope.get().asMethodCallExpr();
                if (call.getNameAsString().equals("qt") && isQuickTheoriesQt(call, declaration, compilationUnit)) {
                    return true;
                }
                scope = call.getScope();
            }
        }
        return false;
    }

    private static boolean belongsToCallable(MethodCallExpr call, CallableDeclaration<?> declaration) {
        return call.findAncestor(CallableDeclaration.class)
                .map(owner -> owner == declaration)
                .orElse(false);
    }

    private static boolean isQuickTheoriesQt(
            MethodCallExpr call,
            CallableDeclaration<?> declaration,
            CompilationUnit compilationUnit) {
        try {
            String owner = call.resolve().declaringType().getQualifiedName();
            if (owner.startsWith("org.quicktheories.")) {
                return true;
            }
        } catch (RuntimeException ignored) {
            // Fall through to import and implemented-interface checks.
        }

        boolean staticImport = compilationUnit.getImports().stream()
                .filter(imported -> imported.isStatic())
                .map(imported -> imported.getNameAsString())
                .anyMatch(name -> name.equals("org.quicktheories.QuickTheory.qt")
                        || name.equals("org.quicktheories.QuickTheory"));
        if (staticImport && call.getScope().isEmpty()) {
            return true;
        }

        if (call.getScope().filter(Expression::isNameExpr).map(Expression::asNameExpr)
                .map(NameExpr::getNameAsString).filter("QuickTheory"::equals).isPresent()
                && hasImport(compilationUnit, "org.quicktheories.QuickTheory")) {
            return true;
        }

        return declaration.findAncestor(ClassOrInterfaceDeclaration.class)
                .map(type -> implementsWithQuickTheories(type, compilationUnit))
                .orElse(false);
    }

    private static boolean implementsWithQuickTheories(
            ClassOrInterfaceDeclaration type,
            CompilationUnit compilationUnit) {
        try {
            return type.resolve().getAllAncestors().stream()
                    .anyMatch(ancestor -> ancestor.getQualifiedName().equals("org.quicktheories.WithQuickTheories"));
        } catch (RuntimeException ignored) {
            return type.getImplementedTypes().stream().anyMatch(parent -> {
                String name = parent.getNameWithScope();
                return name.equals("org.quicktheories.WithQuickTheories")
                        || (name.equals("WithQuickTheories")
                        && hasImport(compilationUnit, "org.quicktheories.WithQuickTheories"));
            });
        }
    }

    private static boolean hasImport(CompilationUnit compilationUnit, String qualifiedName) {
        return compilationUnit.getImports().stream()
                .filter(imported -> !imported.isAsterisk())
                .map(imported -> imported.getNameAsString())
                .anyMatch(qualifiedName::equals);
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
            if (simpleName.contains(".")) {
                return simpleName;
            }
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
