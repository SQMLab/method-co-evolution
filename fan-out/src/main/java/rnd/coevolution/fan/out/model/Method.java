package rnd.coevolution.fan.out.model;

import lombok.Builder;
import lombok.Data;

/**
 * @author Shahidul Islam
 * @since 2025-12-23
 */
@Data
@Builder
public class Method {
    String file;
    String name;
    Integer startLine;

    @Override
    public String toString() {
        return "Method{" +
                "file='" + file + '\'' +
                ", name='" + name + '\'' +
                ", startLine=" + startLine +
                '}';
    }
}
