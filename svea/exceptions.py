
class SveaException(Exception):
    pass


class MissingFiles(SveaException):
    pass


class DtypeError(SveaException):
    pass