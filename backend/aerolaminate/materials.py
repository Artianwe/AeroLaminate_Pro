"""Material records with per-property provenance.

Author: Anwesh Ajitabh Dash.

A material property is stored as {value, unit, status, source, note}. The engine never fills a missing value
silently: ``Material.get`` raises ``MissingPropertyError``. The only fallbacks are explicit ``derived`` values
(e.g. ultimate strain = strength / modulus), and these are recorded in ``Material.flags`` so the API can report them.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

STATUSES = ("datasheet", "literature", "calculated", "estimated", "illustrative", "unavailable")
CAUTION_STATUSES = ("estimated", "illustrative", "unavailable")
# Independent of the data-source status: whether the stored value was checked against a source.
#   primary    - checked against the primary document (datasheet, report, paper)
#   secondary  - matched in an independent secondary source; primary not checked
#   unverified - could not be confirmed by any accessible source
VERIFICATION_LEVELS = ("primary", "secondary", "unverified")

# Plausible ranges for continuous-fibre polymer laminae in the app's unit system. Values outside raise a WARNING
# (not an error): the usual cause is a unit slip, e.g. GPa entered where MPa is expected.
PLAUSIBLE: dict[str, tuple[float, float]] = {
    "E1": (2.0e3, 1.0e6), "E2": (5.0e2, 1.0e5), "G12": (2.0e2, 5.0e4), "nu12": (0.05, 0.6),
    "Xt": (50, 1.0e4), "Xc": (50, 1.0e4), "Yt": (5, 2.0e3), "Yc": (5, 2.0e3), "S12": (5, 2.0e3), "S23": (5, 2.0e3),
    "ILSS": (5, 2.0e3), "eps1t": (1e-4, 0.2), "eps1c": (1e-4, 0.2), "eps2t": (1e-4, 0.2), "eps2c": (1e-4, 0.2),
    "gamma12u": (1e-4, 0.5), "GIc": (0.01, 10), "GIIc": (0.01, 20), "t_ply": (0.01, 2.0), "density": (500, 4000),
    "alpha1": (-1e-4, 1e-4), "alpha2": (-1e-4, 2e-4), "beta1": (-0.05, 0.05), "beta2": (-0.05, 0.05), "Tg_dry": (20, 450),
}

# Canonical property names, units and physical admissibility checks.
PROPERTY_SPEC: dict[str, tuple[str, str]] = {
    "E1": ("MPa", "positive"), "E2": ("MPa", "positive"), "G12": ("MPa", "positive"),
    "nu12": ("-", "poisson"),
    "Xt": ("MPa", "positive"), "Xc": ("MPa", "positive"), "Yt": ("MPa", "positive"),
    "Yc": ("MPa", "positive"), "S12": ("MPa", "positive"), "S23": ("MPa", "positive"),
    "ILSS": ("MPa", "positive"),
    "eps1t": ("-", "positive"), "eps1c": ("-", "positive"), "eps2t": ("-", "positive"),
    "eps2c": ("-", "positive"), "gamma12u": ("-", "positive"),
    "GIc": ("N/mm", "positive"), "GIIc": ("N/mm", "positive"),
    "t_ply": ("mm", "positive"), "density": ("kg/m3", "positive"),
    "alpha1": ("1/C", "any"), "alpha2": ("1/C", "any"), "beta1": ("1/%", "any"), "beta2": ("1/%", "any"),
    "Tg_dry": ("C", "any"), "Vf": ("-", "fraction"),
}
REQUIRED_FOR_CLT = ("E1", "E2", "G12", "nu12")

DATA_DIR = Path(__file__).parent / "data"


class MissingPropertyError(KeyError):
    """Raised when an analysis needs a property whose status is 'unavailable'."""

    def __init__(self, material: str, prop: str, purpose: str = ""):
        self.material, self.prop, self.purpose = material, prop, purpose
        msg = f"Material '{material}' has no value for '{prop}'"
        super().__init__(msg + (f" (required for {purpose})" if purpose else ""))

    def __str__(self) -> str:  # KeyError quotes its message otherwise
        return self.args[0]


class MaterialValidationError(ValueError):
    pass


@dataclass
class Material:
    id: str
    name: str
    properties: dict[str, dict[str, Any]]
    meta: dict[str, Any] = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)

    # ---------------------------------------------------------------- access
    def has(self, prop: str) -> bool:
        p = self.properties.get(prop)
        return bool(p) and p.get("status") != "unavailable" and p.get("value") is not None

    def get(self, prop: str, purpose: str = "") -> float:
        if not self.has(prop):
            raise MissingPropertyError(self.name, prop, purpose)
        return float(self.properties[prop]["value"])

    def get_or_derived(self, prop: str, numerator: str, denominator: str) -> float:
        """Return the property or the explicitly derived linear-elastic value numerator/denominator (flagged)."""
        if self.has(prop):
            return self.get(prop)
        val = self.get(numerator) / self.get(denominator)
        self._flag(f"{self.name}: {prop} not available; derived as {numerator}/{denominator} = {val:.5g} (linear-elastic assumption)")
        return val

    def status(self, prop: str) -> str:
        return self.properties.get(prop, {}).get("status", "unavailable")

    def _flag(self, msg: str) -> None:
        if msg not in self.flags:
            self.flags.append(msg)

    # ---------------------------------------------------------------- reporting
    def caution_list(self, used: tuple[str, ...] | list[str]) -> list[str]:
        out = []
        for p in used:
            s = self.status(p)
            if s in CAUTION_STATUSES:
                out.append(f"{self.name}: {p} is '{s}'")
        return out

    def verification(self, prop: str) -> str:
        return self.properties.get(prop, {}).get("verification", "unverified")

    def unverified_list(self, used) -> list[str]:
        return [p for p in used if self.has(p) and self.verification(p) == "unverified"]

    def plausibility_warnings(self) -> list[str]:
        out = []
        for k, (lo, hi) in PLAUSIBLE.items():
            if self.has(k):
                v = self.get(k)
                if not (lo <= v <= hi):
                    unit = PROPERTY_SPEC[k][0]
                    out.append(f"{self.name}: {k} = {v:g} {unit} is outside the plausible range [{lo:g}, {hi:g}] {unit} - check units")
        if self.has("E1") and self.has("E2") and self.get("E2") > self.get("E1"):
            out.append(f"{self.name}: E2 > E1 - check the material direction convention (1 = fibre)")
        return out

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, **self.meta, "properties": self.properties}

    def with_overrides(self, values: dict[str, float], status: str = "estimated", note: str = "") -> "Material":
        """Copy with selected property values replaced (used by environmental knockdown and Monte Carlo)."""
        props = {k: dict(v) for k, v in self.properties.items()}
        for k, v in values.items():
            base = props.get(k, {"unit": PROPERTY_SPEC.get(k, ("-",))[0]})
            base.update({"value": float(v), "status": status if base.get("status") != "illustrative" else "illustrative"})
            if note:
                base["note"] = note
            props[k] = base
        return Material(self.id, self.name, props, dict(self.meta), list(self.flags))


def validate_material_dict(d: dict[str, Any]) -> Material:
    """Validate a material record (shipped or user-supplied) and return a Material."""
    if not isinstance(d, dict):
        raise MaterialValidationError("Material must be an object")
    mid = str(d.get("id", "")).strip()
    if not re.fullmatch(r"[A-Za-z0-9_.\-]{1,64}", mid):
        raise MaterialValidationError("Material id must be 1-64 characters of letters, digits, '_', '-', '.'")
    name = str(d.get("name", "")).strip() or mid
    props_in = d.get("properties")
    if not isinstance(props_in, dict):
        raise MaterialValidationError("'properties' must be an object")
    props: dict[str, dict[str, Any]] = {}
    for key, (unit, kind) in PROPERTY_SPEC.items():
        p = props_in.get(key)
        if p is None:
            props[key] = {"value": None, "unit": unit, "status": "unavailable"}
            continue
        if not isinstance(p, dict):
            p = {"value": p, "status": "estimated"}
        status = p.get("status", "estimated")
        if status not in STATUSES:
            raise MaterialValidationError(f"{key}: status '{status}' not in {STATUSES}")
        val = p.get("value")
        if status == "unavailable" or val is None or val == "":
            props[key] = {"value": None, "unit": unit, "status": "unavailable",
                          **{x: str(p[x])[:500] for x in ("note", "verification_note") if p.get(x)}}
            continue
        try:
            val = float(val)
        except (TypeError, ValueError):
            raise MaterialValidationError(f"{key}: value must be a number") from None
        if not math.isfinite(val):
            raise MaterialValidationError(f"{key}: value must be finite")
        if kind == "positive" and val <= 0:
            raise MaterialValidationError(f"{key} must be > 0 ({unit})")
        if kind == "fraction" and not (0 < val < 1):
            raise MaterialValidationError(f"{key} must be in (0, 1)")
        entry = {"value": val, "unit": unit, "status": status}
        ver = p.get("verification", "unverified")
        if ver not in VERIFICATION_LEVELS:
            raise MaterialValidationError(f"{key}: verification '{ver}' not in {VERIFICATION_LEVELS}")
        entry["verification"] = ver
        for extra in ("source", "note", "verification_note"):
            if p.get(extra):
                entry[extra] = str(p[extra])[:500]
        props[key] = entry
    for key in REQUIRED_FOR_CLT:
        if props[key]["status"] == "unavailable":
            raise MaterialValidationError(f"{key} is required for laminate analysis")
    # Thermodynamic admissibility of the orthotropic lamina: |nu12| < sqrt(E1/E2)
    E1, E2, nu12 = props["E1"]["value"], props["E2"]["value"], props["nu12"]["value"]
    if not (abs(nu12) < math.sqrt(E1 / E2)) or nu12 <= -1:
        raise MaterialValidationError("nu12 violates positive-definiteness: require |nu12| < sqrt(E1/E2)")
    meta = {k: d[k] for k in ("manufacturer", "form", "cure", "condition", "direction_convention", "applicability", "verification_log")
            if k in d}
    return Material(mid, name, props, meta)


class MaterialDatabase:
    """Shipped (read-only) materials plus user materials persisted in a separate JSON file."""

    def __init__(self, user_path: Path | None = None):
        shipped = json.loads((DATA_DIR / "materials.json").read_text(encoding="utf-8"))
        self.references: dict[str, str] = shipped.get("references", {})
        self.shipped: dict[str, Material] = {}
        for m in shipped["materials"]:
            mat = validate_material_dict(m)
            mat.meta["origin"] = "shipped"
            self.shipped[mat.id] = mat
        self.user_path = user_path
        self.user: dict[str, Material] = {}
        if user_path and user_path.exists():
            try:
                for m in json.loads(user_path.read_text(encoding="utf-8")).get("materials", []):
                    mat = validate_material_dict(m)
                    mat.meta["origin"] = "user"
                    self.user[mat.id] = mat
            except (json.JSONDecodeError, MaterialValidationError):
                # A corrupt user file must not stop the application; it is reported by the API.
                self.user_error = f"User material file {user_path} could not be read and was ignored."

    def all(self) -> list[Material]:
        merged = dict(self.shipped)
        merged.update(self.user)  # a user record with the same id overrides (and is labelled as user)
        return list(merged.values())

    def get(self, mid: str) -> Material:
        if mid in self.user:
            return self.user[mid]
        if mid in self.shipped:
            return self.shipped[mid]
        raise KeyError(f"Unknown material id '{mid}'")

    def save_user(self, d: dict[str, Any]) -> Material:
        mat = validate_material_dict(d)
        mat.meta["origin"] = "user"
        self.user[mat.id] = mat
        self._persist()
        return mat

    def delete_user(self, mid: str) -> None:
        if mid not in self.user:
            raise KeyError(f"'{mid}' is not a user material (shipped records are read-only)")
        del self.user[mid]
        self._persist()

    def _persist(self) -> None:
        if not self.user_path:
            return
        self.user_path.parent.mkdir(parents=True, exist_ok=True)
        data = {"schema_version": 1, "materials": [m.to_dict() for m in self.user.values()]}
        tmp = self.user_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
        tmp.replace(self.user_path)
