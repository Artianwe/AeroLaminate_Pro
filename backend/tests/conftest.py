"""Shared fixtures for the AeroLaminate Pro verification suite. Author: Anwesh Ajitabh Dash."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aerolaminate.clt import Laminate, Ply  # noqa: E402
from aerolaminate.materials import MaterialDatabase, validate_material_dict  # noqa: E402


@pytest.fixture(scope="session")
def db():
    return MaterialDatabase(None)


@pytest.fixture(scope="session")
def t300(db):
    return db.get("T300_5208")


@pytest.fixture(scope="session")
def im7(db):
    return db.get("IM7_8552")


def make_material(mid="ISO", E1=70000.0, E2=None, G12=None, nu12=0.3, **extra):
    E2 = E1 if E2 is None else E2
    G12 = E1 / (2 * (1 + nu12)) if G12 is None else G12
    props = {"E1": E1, "E2": E2, "G12": G12, "nu12": nu12, "Xt": 500, "Xc": 500, "Yt": 500, "Yc": 500, "S12": 300,
             "density": 2700, "t_ply": 1.0}
    props.update(extra)
    return validate_material_dict({"id": mid, "name": mid, "properties": {k: {"value": v, "status": "literature"} for k, v in props.items()}})


def lam_of(mat, angles, t=0.125):
    return Laminate([Ply(mat, a, t) for a in angles])
