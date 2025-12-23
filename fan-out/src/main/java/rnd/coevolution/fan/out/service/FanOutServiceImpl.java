package rnd.coevolution.fan.out.service;

import com.github.javaparser.JavaParser;
import com.github.javaparser.ParserConfiguration;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.ast.expr.MethodCallExpr;
import com.github.javaparser.ast.nodeTypes.NodeWithRange;
import com.github.javaparser.resolution.declarations.ResolvedMethodDeclaration;
import com.github.javaparser.symbolsolver.JavaSymbolSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.CombinedTypeSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.JavaParserTypeSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.ReflectionTypeSolver;
import lombok.extern.slf4j.Slf4j;
import org.apache.commons.io.FileUtils;
import rnd.coevolution.fan.out.FanOutUtil;
import rnd.coevolution.fan.out.model.Fan;
import rnd.coevolution.fan.out.model.Method;

import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;
import java.util.Optional;
import java.util.stream.Stream;

@Slf4j
public class FanOutServiceImpl implements FanOutService {
    private JavaParser javaParser;

    public FanOutServiceImpl(String repositoryPath, List<String> symbolResolverPaths) {
        CombinedTypeSolver typeSolver = new CombinedTypeSolver();
        typeSolver.add(new ReflectionTypeSolver(true));
        for (String symbolResolverPath : symbolResolverPaths) {
            Path repoRoot = Paths.get(repositoryPath);
            Path path = repoRoot.resolve(symbolResolverPath).normalize();
            if (Files.exists(path)) {
                typeSolver.add(new JavaParserTypeSolver(path.toFile()));
            }
        }
        JavaSymbolSolver symbolSolver = new JavaSymbolSolver(typeSolver);
        ParserConfiguration config = new ParserConfiguration()
                .setSymbolResolver(symbolSolver);
        this.javaParser = new JavaParser(config);
//        StaticJavaParser.setConfiguration(config);
//        StaticJavaParser.getConfiguration().setSymbolResolver(new JavaSymbolSolver(typeSolver));
    }

    @Override
    public List<Fan> findOut(String repositoryPath, List<String> targetPaths) {
        List<String> files = FanOutUtil.expandPath(repositoryPath, targetPaths);


        return files.stream()
                .flatMap(file -> {
                    try {
                        var result = javaParser.parse(FileUtils.readFileToString(new File(file), StandardCharsets.UTF_8));
                        if (result.isSuccessful()) {
                            return result.getResult().get()
                                    .findAll(MethodDeclaration.class)
                                    .stream()
                                    .flatMap(method -> {

                                        List<Method> calledMethods =
                                                method.findAll(MethodCallExpr.class).stream()
                                                        .flatMap(call -> {
                                                            try {
                                                                ResolvedMethodDeclaration resolved = call.resolve();

                                                                Optional<MethodDeclaration> ast = resolved.toAst()
                                                                        .filter(MethodDeclaration.class::isInstance)
                                                                        .map(MethodDeclaration.class::cast);

                                                                String methodName = resolved.getName();

                                                                String filePath = ast
                                                                        .flatMap(md -> md.findCompilationUnit())
                                                                        .flatMap(cu -> cu.getStorage())
                                                                        .map(storage -> storage.getPath().toString())
                                                                        .orElse("<external>");

                                                                int startLine = ast
                                                                        .flatMap(NodeWithRange::getBegin)
                                                                        .map(p -> p.line)
                                                                        .orElse(-1);

                                                                return Stream.of(
                                                                        Method.builder()
                                                                                .name(methodName)
                                                                                .file(filePath)
                                                                                .startLine(startLine)
                                                                                .build()
                                                                );

                                                            } catch (Exception e) {
                                                                return Stream.empty(); // unresolved or external
                                                            }
                                                        })
                                                        .toList();

                                        Fan fan = Fan.builder()
                                                .method(Method.builder()
                                                        .file(file)
                                                        .name(method.getSignature().getName())
                                                        .startLine(method.getName().getBegin().get().line)
                                                        .build())
                                                .fanMethods(calledMethods)
                                                .build();

                                        return Stream.of(fan);
                                    });
                        } else {
                            log.error("Failed to parse file {}", file);
                            log.error("Problems {}", result.getProblems());
                            return Stream.empty();
                        }
                    } catch (Exception e) {
                        return Stream.empty(); // skip file completely
                    }
                })
                .toList();
    }


}
