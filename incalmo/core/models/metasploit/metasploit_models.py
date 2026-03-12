from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ExploitModuleInfo(BaseModel):
    """
    A candidate exploit module returned by a CVE search.
    Passed to the LLM agent to pick the best one.
    """

    name: str = Field(..., description="The module's short name")
    fullname: str = Field(
        ...,
        description="The full module path",
    )
    rank: str = Field(..., description="Metasploit's internal rank")
    disclosure_date: Optional[str] = Field(default=None)


class ExploitModuleOptions(BaseModel):
    """
    Live snapshot of a loaded module's option state.
    Passed to the LLM agent so it can decide what to fill in.
    """

    fullname: str
    all_options: list[str] = Field(
        ..., description="All option names the module accepts"
    )
    required_options: list[str] = Field(
        ...,
        description="Options that are required",
    )
    missing_required: list[str] = Field(
        ...,
        description="Required options that are not yet set",
    )
    current_values: dict[str, Any] = Field(..., description="Current run options")
    targets: dict[int, str] = Field(
        ...,
        description="Available targets for the module",
    )
    available_payloads: list[str] = Field(
        ...,
        description="Payloads compatible with this module",
    )


class PayloadModuleOptions(BaseModel):
    """
    Live snapshot of a loaded payload module's option state.
    Passed to the LLM agent so it can decide what to fill in.
    """

    fullname: str
    all_options: list[str] = Field(
        ..., description="All option names the module accepts"
    )
    required_options: list[str] = Field(
        ...,
        description="Options that are required",
    )
    missing_required: list[str] = Field(
        ...,
        description="Required options that are not yet set",
    )
    current_values: dict[str, Any] = Field(..., description="Current run options")


class MetasploitExploitResult(BaseModel):
    """Returned by MetasploitService.run_exploit()"""

    cve_id: str
    console_cid: str
    console_output: str = Field(default="")
