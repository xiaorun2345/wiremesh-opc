from abc import ABC, abstractmethod


class BaseSkill(ABC):
    name: str = "base_skill"
    version: str = "1.0"

    @abstractmethod
    def execute(self, input_data: dict) -> dict:
        ...
