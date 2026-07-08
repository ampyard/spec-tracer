import json
import re
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from unified_test_tracer.models import Scenario, TestResult

REQUIRE_PREFIX = "@require:"


class ResultParser(ABC):

    @abstractmethod
    def parse(self, paths: List[Path], layer: str = "") -> List[TestResult]:
        ...


class FeatureParser:

    @staticmethod
    def parse(path: Path) -> List[Scenario]:
        scenarios: List[Scenario] = []
        feature_name = path.stem
        current_tags: List[str] = []
        current_scenario: Scenario | None = None

        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.rstrip()
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("Feature:"):
                feature_name = stripped.split(":", 1)[1].strip()
                current_tags = []
                continue
            if stripped.startswith("@"):
                current_tags.extend(stripped.split())
                continue
            if stripped.startswith(("Scenario:", "Scenario Outline:")):
                if current_scenario is not None:
                    scenarios.append(current_scenario)
                linking_tags = [t for t in current_tags if not t.lower().startswith(REQUIRE_PREFIX)]
                required_layers = [
                    t.split(":", 1)[1].strip().lower()
                    for t in current_tags
                    if t.lower().startswith(REQUIRE_PREFIX)
                ]
                current_scenario = Scenario(
                    feature=feature_name,
                    name=stripped.split(":", 1)[1].strip(),
                    tags=linking_tags,
                    required_layers=required_layers,
                    steps=[],
                )
                current_tags = []
                continue
            if current_scenario is not None:
                current_scenario.steps.append(stripped)

        if current_scenario is not None:
            scenarios.append(current_scenario)

        return scenarios


class JunitParser(ResultParser):

    _tag_pattern = re.compile(r"@[\w.-]+")

    def parse(self, paths: List[Path], layer: str = "unit") -> List[TestResult]:
        results: List[TestResult] = []
        for path in paths:
            try:
                tree = ET.parse(path)
            except ET.ParseError as exc:
                raise ValueError(f"Malformed JUnit XML in {path}: {exc}") from exc
            root = tree.getroot()
            suites = [root] if root.tag == "testsuite" else root.findall(".//testsuite")
            for suite in suites:
                for tc in suite.findall("testcase"):
                    name = tc.get("name", "")
                    classname = tc.get("classname", "")
                    time = float(tc.get("time", 0) or 0)
                    tags = self._tag_pattern.findall(name) + self._tag_pattern.findall(classname)
                    props = tc.find("properties")
                    if props is not None:
                        for prop in props.findall("property"):
                            val = prop.get("value", "")
                            if val.startswith("@"):
                                tags.append(val)
                            pname = prop.get("name", "")
                            if pname.startswith("@"):
                                tags.append(pname)
                    status = "passed"
                    if tc.find("failure") is not None or tc.find("error") is not None:
                        status = "failed"
                    elif tc.find("skipped") is not None:
                        status = "skipped"
                    results.append(
                        TestResult(
                            layer=layer,
                            name=name,
                            tags=sorted(set(tags)),
                            status=status,
                            duration=time,
                        )
                    )
        return results


class CucumberParser(ResultParser):

    def parse(self, paths: List[Path], layer: str = "e2e") -> List[TestResult]:
        results: List[TestResult] = []
        for path in paths:
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if isinstance(payload, dict):
                payload = [payload]
            for feature in payload:
                for element in feature.get("elements", []):
                    if not isinstance(element, dict):
                        continue
                    if element.get("keyword", "").lower() != "scenario":
                        continue
                    raw_tags = element.get("tags", [])
                    if raw_tags and isinstance(raw_tags[0], dict):
                        tags = [tag.get("name", "") for tag in raw_tags]
                    else:
                        tags = [f"@{tag}" if not tag.startswith("@") else tag for tag in raw_tags]
                    status = element.get("status", "passed")
                    if status == "undefined":
                        status = "skipped"
                    results.append(
                        TestResult(
                            layer=layer,
                            name=element.get("name", ""),
                            tags=tags,
                            status=status,
                        )
                    )
        return results
