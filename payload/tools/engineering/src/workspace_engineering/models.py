"""Validated task input. A saved task describes scope; it is not an approval token."""

from __future__ import annotations

import json
import re
from pathlib import Path, PureWindowsPath
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Task(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    request: str = Field(min_length=1, max_length=100_000)
    acceptance_criteria: list[str] = Field(min_length=1)
    repositories: list[str] = Field(min_length=1)
    graph_terms: list[str] = Field(min_length=1, max_length=12)
    scope: dict[str, list[str]] = Field(default_factory=dict)
    checks: list[str] = Field(default_factory=list)
    specialists: list[Literal["oracle-specialist", "ui-specialist", "integration-specialist"]] = Field(default_factory=list)
    checkouts: dict[str, str] = Field(default_factory=dict)
    implementation_groups: list[list[str]] = Field(default_factory=list)
    mode: Literal["investigate", "implement"] = "investigate"
    max_workers: int = Field(default=4, ge=1, le=8)
    max_revisions: int = Field(default=2, ge=0, le=8)
    worker_timeout_seconds: int = Field(default=1800, ge=30, le=7200)
    graph_exception: str | None = None
    id: str | None = None

    @field_validator("acceptance_criteria", "graph_terms", "checks")
    @classmethod
    def nonempty_items(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("Criteria, graph terms and check IDs cannot be blank")
        if len(value) != len(set(value)):
            raise ValueError("List entries must be unique")
        return value

    @field_validator("repositories")
    @classmethod
    def repositories_valid(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)) or any(not re.fullmatch(r"[a-zA-Z0-9_.-]+", x) for x in value):
            raise ValueError("Repository IDs must be unique simple names from the registry")
        return value

    @field_validator("scope")
    @classmethod
    def scope_valid(cls, value: dict[str, list[str]]) -> dict[str, list[str]]:
        for paths in value.values():
            for path in paths:
                normalized = path.replace("\\", "/")
                if not normalized or Path(normalized).is_absolute() or PureWindowsPath(path).drive or ".." in Path(normalized).parts:
                    raise ValueError("Scope paths must be repository-relative and cannot escape the root")
                if any(part.lower() == ".git" for part in Path(normalized).parts):
                    raise ValueError("Git metadata cannot be an implementation scope")
        return value

    @model_validator(mode="after")
    def check_scope(self) -> Task:
        if set(self.scope) - set(self.repositories) or set(self.checkouts) - set(self.repositories):
            raise ValueError("Scope and checkout bindings must reference selected repositories")
        if self.implementation_groups:
            flattened = [repo for group in self.implementation_groups for repo in group]
            if any(not group for group in self.implementation_groups) or sorted(flattened) != sorted(self.repositories):
                raise ValueError("Implementation groups must contain each selected repository exactly once")
            if any(len(group) > 1 and any(repo not in self.checkouts for repo in group) for group in self.implementation_groups):
                raise ValueError("Concurrent implementers need explicit isolated checkout bindings for every group member")
        if self.mode == "implement":
            if any(not self.scope.get(repo) for repo in self.repositories):
                raise ValueError("Implementation needs an explicit path scope for each repository")
            if not self.checks:
                raise ValueError("Implementation needs at least one registered validation check")
        return self


def load_task(path: Path, mode: str | None = None) -> Task:
    text = path.read_text(encoding="utf-8-sig")
    raw = json.loads(text) if path.suffix.lower() == ".json" else yaml.safe_load(text)
    if not isinstance(raw, dict):
        raise ValueError("Task must be a JSON/YAML mapping")
    if mode is not None:
        raw["mode"] = mode
    return Task.model_validate(raw)
