from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Entity:
    name: str
    entity_type: str
    aliases: list[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


SEED_ENTITIES = [
    Entity("Steve Roth", "PERSON", ["steve", "steven roth"], "Founder, CEO & Chief Architect of Claire Systems."),
    Entity("Claire", "PERSON", ["claire the person"], "Founding Business / Equine Stewardship Member when referring to the person."),
    Entity("Brisa", "PERSON", ["brisa"], "Founding Launch Capital / Equine Stewardship Member."),
    Entity("Jason", "PERSON", ["jason"], "Potential officer/member if confirmed."),
    Entity("Claire Systems LLC", "COMPANY", ["claire systems", "clairesystems"], "Technology plus horse stewardship company structure."),
    Entity("Seahorse", "COMPANY", ["seahorse equestrian", "seahorse"], "Horse-related history/entity; lane-gated."),
    Entity("CLAIRE", "SYSTEM", ["cognizant lucid autonomous iterative recall environment"], "Governed AI runtime, not merely a chatbot."),
    Entity("ARE", "SYSTEM", ["analog recall engine", "original are"], "Chronological memory substrate."),
    Entity("Veritas", "SYSTEM", ["veritas trading", "financial intelligence station"], "Financial intelligence station / pressure chamber."),
    Entity("NVIDIA", "COMPANY", ["nvidia"], "NVIDIA pathway and evaluation target."),
    Entity("Nemotron", "SYSTEM", ["nvidia nemotron", "nemotron"], "Replaceable model brain downstream of CLAIRE runtime."),
    Entity("Kraken OHLCV data", "ASSET", ["kraken", "ohlcv", "kraken candles"], "Market data source for backtest/live feed validation."),
    Entity("the horses", "HORSE", ["horses", "the herd"], "Central mission assets, not a side project."),
    Entity("Pedro", "HORSE", ["pedro"], "Named horse and stewardship entity."),
]


class EntityRegistry:
    def __init__(self, entities: list[Entity] | None = None):
        self.entities = entities or list(SEED_ENTITIES)

    def identify(self, text: str) -> list[dict[str, Any]]:
        lowered = str(text or "").lower()
        found: list[dict[str, Any]] = []
        for entity in self.entities:
            terms = [entity.name.lower(), *[alias.lower() for alias in entity.aliases]]
            if any(term and term in lowered for term in terms):
                found.append(entity.to_dict())
        return found

    def all_entities(self) -> list[dict[str, Any]]:
        return [entity.to_dict() for entity in self.entities]


DEFAULT_REGISTRY = EntityRegistry()


def identify_entities(text: str) -> list[dict[str, Any]]:
    return DEFAULT_REGISTRY.identify(text)
