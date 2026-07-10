package rnd.method.parser.call.graph.model;

import lombok.Builder;
import lombok.Data;

@Data
@Builder
public class MethodMetadata {
    String repositoryName;
    String name;
    String url;
    String annotations;
    String annotationsFqn;
    String javadoc;
}
