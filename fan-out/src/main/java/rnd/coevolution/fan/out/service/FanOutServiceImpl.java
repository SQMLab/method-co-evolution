package rnd.coevolution.fan.out.service;

import com.github.javaparser.JavaParser;
import com.github.javaparser.ParserConfiguration;
import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.ast.expr.MethodCallExpr;
import com.github.javaparser.resolution.declarations.ResolvedMethodDeclaration;
import com.github.javaparser.symbolsolver.JavaSymbolSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.CombinedTypeSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.JavaParserTypeSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.ReflectionTypeSolver;
import lombok.extern.slf4j.Slf4j;
import rnd.coevolution.fan.out.FanOutUtil;
import rnd.coevolution.fan.out.model.Fan;

import java.io.File;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;

@Slf4j
public class FanOutServiceImpl implements FanOutService {
    private JavaSymbolSolver symbolSolver;
    private JavaParser javaParser;

    public FanOutServiceImpl(String repositoryPath, List<String> symbolResolverPaths) {
        CombinedTypeSolver typeSolver = new CombinedTypeSolver();
        typeSolver.add(new ReflectionTypeSolver());
        for (String symbolResolverPath : symbolResolverPaths) {
            Path repoRoot = Paths.get(repositoryPath);
            Path path = repoRoot.resolve(symbolResolverPath).normalize();
            if (Files.exists(path)){
                typeSolver.add(new JavaParserTypeSolver(path.toFile()));
            }
        }
        JavaSymbolSolver symbolSolver = new JavaSymbolSolver(typeSolver);
        ParserConfiguration config = new ParserConfiguration()
                .setSymbolResolver(symbolSolver);
        this.symbolSolver = symbolSolver;
        this.javaParser = new JavaParser(config);
    }

    @Override
    public List<Fan> findOut(String repositoryPath, List<String> targetPaths) {
        List<String> files = FanOutUtil.expandPath(repositoryPath, targetPaths);
        files.forEach(file -> {
            CompilationUnit cu = this.javaParser.parse(file).getResult().get();
            cu.findAll(MethodDeclaration.class).forEach(method -> {
                    method.findAll(MethodCallExpr.class).forEach(call -> {
                        try {
                            ResolvedMethodDeclaration resolved = call.resolve();

                            System.out.println("Called method: " +
                                    resolved.getQualifiedSignature());

                        } catch (Exception e) {
                            System.out.println("Unresolved call: " + call);
                        }
                    });
            });

        });


        return List.of();
    }



}
