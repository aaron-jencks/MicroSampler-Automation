
class UnknownSuiteError(Exception):
    def __init__(self, suite: str):
        self.suite = suite
        super().__init__(f'Unknown suite "{suite}"')
