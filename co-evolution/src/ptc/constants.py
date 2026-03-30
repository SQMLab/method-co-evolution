from enum import Enum
class MethodChangeType(str, Enum):
    INTRODUCTION = "Yintroduced"
    MOVE = "Ymovefromfile"
    BODY = "Ybodychange"
    DOCUMENTATION = "Ydocumentationchange"
    FILE_MOVE = "Yfilerename"
    RENAME = "Yrename"
    MODIFIER = "Ymodifierchange"
    RETURN_TYPE = "Yreturntypechange"
    EXCEPTION = "Yexceptionschange"
    PARAMETER = "Yparameterchange"
    PARAMETER_META = "Yparametermetachange" # find out what this is
    ANNOTATION = "Yannotationchnage"
    FORMAT = "Yformatchange"
    MULTI = "Ymultichange"

CODE_SHOVEL_UNSUPPORTED_CHANGES = [MethodChangeType.DOCUMENTATION, MethodChangeType.ANNOTATION, MethodChangeType.FORMAT]
# DIFF_CHANGE_TYPES = [MethodChangeType.INTRODUCTION, MethodChangeType.BODY, MethodChangeType.RENAME, MethodChangeType.MODIFIER, MethodChangeType.RETURN_TYPE, MethodChangeType.EXCEPTION, MethodChangeType.PARAMETER, MethodChangeType.PARAMETER_META, MethodChangeType.ANNOTATION]
ALL_REPOSITORY = "all"