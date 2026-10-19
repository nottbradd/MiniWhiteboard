"""One owner for both creation workflows, including pending capture callbacks."""


class CreationSession:
    def __init__(self):
        self.owner = None

    def claim(self, owner):
        if self.owner is not None:
            return False
        self.owner = owner
        return True

    def finish(self, owner):
        if self.owner == owner:
            self.owner = None
