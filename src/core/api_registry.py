"""API Registry for the Cisco Secure Firewall Management Center (FMC) API."""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class APIDefinition:
    """Definition of an FMC API."""

    name: str
    display_name: str
    spec_file: str
    base_path: str
    description: str
    enabled: bool = True


class APIRegistry:
    """Registry for FMC API definitions.

    FMC exposes two main REST API roots:
      - fmc_config  — objects, policy, devices, deployment, etc.
      - fmc_platform — authentication, system info, HA, licensing, updates
    Both are described in the single fmc_oas3.json specification.
    """

    APIS: Dict[str, APIDefinition] = {
        "fmc": APIDefinition(
            name="fmc",
            display_name="Cisco Secure Firewall Management Center",
            spec_file="fmc_oas3.json",
            base_path="",
            description=(
                "Full FMC REST API — objects, policy, devices, deployment, "
                "chassis, integration, health, backup, users, and more"
            ),
            enabled=True,
        ),
    }

    @classmethod
    def get_api(cls, name: str) -> Optional[APIDefinition]:
        return cls.APIS.get(name)

    @classmethod
    def get_enabled_apis(cls) -> List[APIDefinition]:
        return [api for api in cls.APIS.values() if api.enabled]

    @classmethod
    def get_all_apis(cls) -> List[APIDefinition]:
        return list(cls.APIS.values())

    @classmethod
    def enable_api(cls, name: str) -> bool:
        api = cls.get_api(name)
        if api:
            api.enabled = True
            return True
        return False

    @classmethod
    def disable_api(cls, name: str) -> bool:
        api = cls.get_api(name)
        if api:
            api.enabled = False
            return True
        return False

    @classmethod
    def get_base_path_for_api(cls, api_name: str) -> Optional[str]:
        api = cls.get_api(api_name)
        return api.base_path if api else None
