
class SveaException(Exception):
    pass


class MissingFiles(SveaException):
    pass


class DtypeError(SveaException):
    pass


class PathError(SveaException):
    pass


class PermissionError(SveaException):
    pass


class MissingSharkModules(SveaException):
    pass

