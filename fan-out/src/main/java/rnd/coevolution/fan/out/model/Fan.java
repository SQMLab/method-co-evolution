package rnd.coevolution.fan.out.model;

import lombok.Data;

import java.util.List;
@Data
public class Fan {
    String methodUri;
    List<String> calledMethodUris;

}
