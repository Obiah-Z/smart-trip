from __future__ import annotations


class GraphExpansionService:
    def __init__(self, graph_store) -> None:
        self._graph_store = graph_store

    def expand_excluded_attractions(self, *, attractions: list[str]) -> list[str]:
        expanded: list[str] = []
        for item in attractions:
            expanded.extend(self._graph_store.expand_entity(entity=item))
        return list(dict.fromkeys([str(item).strip() for item in expanded if str(item).strip()]))
