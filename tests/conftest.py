import pytest

from parcialfinal.config import Almacen, Config
from parcialfinal.nucleo import Nucleo


@pytest.fixture
def nucleo(tmp_path):
    return Nucleo(Config(almacen=Almacen(carpeta=str(tmp_path / "data"))))


def filas(nucleo, archivo):
    import csv
    with open(nucleo.almacen.carpeta / archivo, newline="") as f:
        return list(csv.DictReader(f))
