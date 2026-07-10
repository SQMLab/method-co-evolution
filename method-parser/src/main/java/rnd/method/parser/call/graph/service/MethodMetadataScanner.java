package rnd.method.parser.call.graph.service;

import rnd.method.parser.call.graph.model.MethodMetadata;

import java.util.List;

public interface MethodMetadataScanner {
    void init(
            String projectName,
            String repoRoot,
            String repoUrl,
            String commitHash,
            boolean checkoutRepository);

    List<MethodMetadata> scanMethodMetadata(String file);
}
