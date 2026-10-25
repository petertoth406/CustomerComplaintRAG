"""Load and resolve versioned chunking configurations."""

from pathlib import Path

import yaml

from app.core.config import CHUNK_CONFIG_DIR, DEFAULT_CHUNK_CONFIG_ID
from app.schemas.chunking import ChunkConfig


class ChunkConfigRegistry:
    def __init__(self, config_dir: Path = CHUNK_CONFIG_DIR) -> None:
        self.config_dir = config_dir
        self._configs: dict[str, ChunkConfig] | None = None

    def all(self) -> list[ChunkConfig]:
        if self._configs is None:
            self._configs = self._load()
        return list(self._configs.values())

    def get(self, config_id: str) -> ChunkConfig:
        configs = {config.id: config for config in self.all()}
        try:
            return configs[config_id]
        except KeyError as error:
            available = ", ".join(configs)
            raise ValueError(
                f"Ismeretlen chunkkonfiguráció: {config_id}. Elérhető: {available}."
            ) from error

    def resolve(self, config_ids: list[str] | None) -> list[ChunkConfig]:
        requested_ids = config_ids or [DEFAULT_CHUNK_CONFIG_ID]
        unique_ids = list(dict.fromkeys(requested_ids))
        return [self.get(config_id) for config_id in unique_ids]

    def _load(self) -> dict[str, ChunkConfig]:
        if not self.config_dir.is_dir():
            raise ValueError(
                f"A chunkkonfigurációs könyvtár nem található: {self.config_dir}"
            )

        configs: dict[str, ChunkConfig] = {}
        for path in sorted(self.config_dir.glob("*.yaml")):
            raw_config = yaml.safe_load(path.read_text(encoding="utf-8"))
            if not isinstance(raw_config, dict):
                raise ValueError(f"A chunkkonfiguráció nem YAML objektum: {path}")
            config = ChunkConfig.model_validate(raw_config)
            if config.id in configs:
                raise ValueError(f"Duplikált chunkkonfiguráció-azonosító: {config.id}")
            configs[config.id] = config

        if not configs:
            raise ValueError(
                f"Nem található chunkkonfiguráció a könyvtárban: {self.config_dir}"
            )
        return configs
