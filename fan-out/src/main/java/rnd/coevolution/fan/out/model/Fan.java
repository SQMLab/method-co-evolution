package rnd.coevolution.fan.out.model;

import lombok.Builder;
import lombok.Data;

import java.util.List;
@Data
@Builder
public class Fan {
    Method method;
    List<Method> fanMethods;

    @Override
    public String toString() {
        return "{" +
                "methodUri='" + method + '\'' +
                ", calledMethodUris=" + fanMethods +
                '}';
    }
}
