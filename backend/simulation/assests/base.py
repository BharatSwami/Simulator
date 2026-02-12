from abc import ABC, abstractmethod

class AssetModel(ABC):

    def __init__(self, asset_id, params, rng):
        super().__init__()
        self.asset_id = asset_id
        self.params = self.params
        self.rng = rng

    @abstractmethod
    def step(self, state):
        pass



