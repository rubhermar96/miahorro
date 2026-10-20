"""Starting values of the reference tables (RF-PLT-02), checked on 20/10/2026.

`python -m app.cli sync-reference-values` (run on every start, after the migrations) adds the
rows that are missing; it never changes a row already there, so what the administrator edits
in /admin stays. To ship a new value, add a row with its own `valid_from` and keep the old one.

Rates are percentages and costs are euros. A scale goes in `extra` as tranches with their upper
limit; `marginal: false` means the rate of the band applies to the whole amount.
"""

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

REGIONS: dict[str, str] = {
    "andalucia": "Andalucía",
    "aragon": "Aragón",
    "asturias": "Asturias",
    "baleares": "Illes Balears",
    "canarias": "Canarias",
    "cantabria": "Cantabria",
    "castilla_la_mancha": "Castilla-La Mancha",
    "castilla_y_leon": "Castilla y León",
    "cataluna": "Cataluña",
    "valencia": "Comunitat Valenciana",
    "extremadura": "Extremadura",
    "galicia": "Galicia",
    "madrid": "Comunidad de Madrid",
    "murcia": "Región de Murcia",
    "navarra": "Navarra",
    "pais_vasco": "País Vasco",
    "la_rioja": "La Rioja",
}

TABLES: dict[str, str] = {
    "itp": "ITP por comunidad (vivienda usada)",
    "ajd": "AJD por comunidad (vivienda nueva)",
    "vat": "IVA o IGIC de la vivienda nueva",
    "savings_tax": "Escala del ahorro (IRPF)",
    "car_registration": "Impuesto de matriculación",
    "home_costs": "Gastos de compraventa (estimados)",
}

CHECKED = "Comprobado el 20/10/2026."
START = dt.date(2026, 1, 1)

_GUIAFISCAL_ITP = "guiafiscal.es: ITP por comunidad 2026 (https://guiafiscal.es/patrimonio/itp/)"
_GUIAFISCAL_AJD = (
    "guiafiscal.es: AJD por comunidad 2026, act. 30/08/2026 "
    "(https://guiafiscal.es/patrimonio/ajd-por-ccaa-2026/)"
)


@dataclass(frozen=True)
class Seed:
    table: str
    key: str
    value: str
    source: str
    note: str | None = None
    valid_from: dt.date = START
    extra: dict[str, Any] | None = field(default=None)

    @property
    def amount(self) -> Decimal:
        return Decimal(self.value)


def _scale(*tranches: tuple[int | None, str], marginal: bool = True) -> dict[str, Any]:
    return {
        "brackets": [
            {"up_to": None if up_to is None else str(up_to), "rate": rate}
            for up_to, rate in tranches
        ],
        "marginal": marginal,
    }


def _itp(key: str, value: str, note: str | None = None, **kwargs: Any) -> Seed:
    source = kwargs.pop("source", _GUIAFISCAL_ITP)
    return Seed("itp", key, value, source, " ".join(filter(None, [note, CHECKED])), **kwargs)


def _ajd(key: str, value: str, note: str | None = None, **kwargs: Any) -> Seed:
    return Seed(
        "ajd", key, value, _GUIAFISCAL_AJD, " ".join(filter(None, [note, CHECKED])), **kwargs
    )


_DEEDS = "Notaría y registro suman unos 660-1.085 € para precios de 100.000 a 500.000 €."
_PROGRESSIVE = (
    "Tarifa progresiva por tramos según guiafiscal.es; la página no deja claro si se aplica "
    "por tramos o al total por encima del primer umbral."
)

SEED: list[Seed] = [
    # --- ITP: second-hand homes ---------------------------------------------------------------
    _itp("andalucia", "7"),
    _itp(
        "aragon",
        "8",
        _PROGRESSIVE,
        extra=_scale((400000, "8"), (450000, "8.5"), (500000, "9"), (750000, "9.5"), (None, "10")),
        source=f"{_GUIAFISCAL_ITP}; DLeg 1/2005 de Aragón, art. 121-1",
    ),
    _itp(
        "asturias",
        "8",
        _PROGRESSIVE,
        extra=_scale((300000, "8"), (500000, "9"), (None, "10")),
        source=f"{_GUIAFISCAL_ITP}; DLeg 2/2014 de Asturias, art. 26",
    ),
    _itp(
        "baleares",
        "8",
        "Por tramos (ejemplo de guiafiscal.es).",
        extra=_scale((400000, "8"), (600000, "9"), (1000000, "10"), (2000000, "12"), (None, "13")),
        source=f"{_GUIAFISCAL_ITP}; DLeg 1/2014 de Illes Balears, art. 10.a",
    ),
    _itp("canarias", "6.5"),
    _itp(
        "cantabria",
        "7",
        "Escala de la vivienda habitual (7 % hasta 300.000 € y 9 % el exceso); el resto de "
        "inmuebles paga un 9 %.",
        extra=_scale((300000, "7"), (None, "9")),
        valid_from=dt.date(2026, 5, 1),
        source=f"{_GUIAFISCAL_ITP}; Ley de Cantabria 5/2026 (BOE-A-2026-10431)",
    ),
    _itp("castilla_la_mancha", "9"),
    _itp(
        "castilla_y_leon",
        "8",
        _PROGRESSIVE,
        extra=_scale((250000, "8"), (None, "10")),
        source=f"{_GUIAFISCAL_ITP}; DLeg 1/2013 de Castilla y León, arts. 24.1 y 25.1",
    ),
    _itp(
        "cataluna",
        "10",
        "Las fuentes no coinciden en la fecha de entrada en vigor de esta escala.",
        extra=_scale((600000, "10"), (900000, "11"), (1500000, "12"), (None, "13")),
        source=(
            "inmofiscal.com: ITP por comunidad 2026 (https://www.inmofiscal.com/itp-comunidades"
            "-autonomas); rankia.com"
        ),
    ),
    _itp(
        "valencia",
        "9",
        "Hasta el 31/05/2026 era el 10 %.",
        extra=_scale((1000000, "9"), (None, "11")),
        valid_from=dt.date(2026, 6, 1),
        source=f"{_GUIAFISCAL_ITP}; Ley 5/2025 de la Generalitat",
    ),
    _itp(
        "extremadura",
        "8",
        _PROGRESSIVE,
        extra=_scale((360000, "8"), (600000, "10"), (None, "11")),
        source=f"{_GUIAFISCAL_ITP}; DLeg 1/2018 de Extremadura, art. 36",
    ),
    _itp("galicia", "8", "Tipo único desde 2026; algunas webs aún dan el 9 o el 10 %."),
    _itp("madrid", "6"),
    _itp("murcia", "7.75"),
    _itp("navarra", "6", "Régimen foral."),
    _itp("pais_vasco", "4", "Régimen foral: 4 % la vivienda; el resto de inmuebles, 7 %."),
    _itp("la_rioja", "7"),
    # --- AJD: new homes ----------------------------------------------------------------------
    _ajd("andalucia", "1.2"),
    _ajd("aragon", "1.5"),
    _ajd("asturias", "1.2"),
    _ajd(
        "baleares",
        "1.5",
        "1 % en la primera vivienda hasta 270.151,20 €; 2 % desde 1.000.000 €.",
    ),
    _ajd("canarias", "0.75"),
    _ajd("cantabria", "1.5"),
    _ajd("castilla_la_mancha", "1.5"),
    _ajd("castilla_y_leon", "1.5"),
    _ajd("cataluna", "1.5"),
    _ajd("valencia", "1.4", "Desde el 01/06/2026.", valid_from=dt.date(2026, 6, 1)),
    _ajd("extremadura", "1.5"),
    _ajd("galicia", "1.5"),
    _ajd("madrid", "0.75"),
    _ajd("murcia", "1.5"),
    _ajd("navarra", "0.5"),
    _ajd("pais_vasco", "0.5"),
    _ajd("la_rioja", "1"),
    # --- VAT / IGIC: new homes ----------------------------------------------------------------
    Seed(
        "vat",
        "new_home",
        "10",
        "Ley 37/1992 del IVA, art. 91.Uno.1.7º (tipo reducido de las viviendas)",
        f"La vivienda protegida de régimen especial paga un 4 %. {CHECKED}",
    ),
    Seed(
        "vat",
        "new_home_canarias",
        "3",
        "PwC Periscopio fiscal: Ley de Presupuestos de Canarias para 2026 "
        "(https://periscopiofiscalylegal.pwc.es/modificaciones-fiscales-implementadas-por-la-ley-"
        "de-presupuestos-generales-de-canarias-para-2026/)",
        "IGIC: 3 % si la base no pasa de 200.000 € y tipo general (7 %) por encima. Hay casos "
        f"al 0 %; compruébalo. {CHECKED}",
        extra=_scale((200000, "3"), (None, "7"), marginal=False),
    ),
    # --- Savings scale of IRPF ---------------------------------------------------------------
    Seed(
        "savings_tax",
        "general",
        "19",
        "guiafiscal.es: tramos IRPF 2026 (https://guiafiscal.es/irpf/tramos-irpf-2026/); "
        "vidacaixa.es; Wolters Kluwer",
        f"Igual en todo el territorio común. {CHECKED}",
        extra=_scale((6000, "19"), (50000, "21"), (200000, "23"), (300000, "27"), (None, "30")),
    ),
    # --- Registration tax --------------------------------------------------------------------
    Seed(
        "car_registration",
        "general",
        "0",
        "Ley 38/1992, art. 70; race.es (https://www.race.es/impuesto-matriculacion-coche); "
        "bankinter.com",
        "Por emisiones WLTP de CO₂ (g/km), sobre el precio sin IVA: hasta 120 exento, 121-159 "
        "4,75 %, 160-199 9,75 %, desde 200 14,75 %. Canarias tiene tipos propios y las "
        f"comunidades pueden subirlos hasta un 15 %. {CHECKED}",
        extra=_scale((120, "0"), (159, "4.75"), (199, "9.75"), (None, "14.75"), marginal=False),
    ),
    # --- Purchase costs (estimates) ----------------------------------------------------------
    *(
        Seed(
            "home_costs",
            key,
            value,
            "rastreator.com (https://www.rastreator.com/hipotecas/guias/coste-tramites-para-"
            "comprar-casa); iahorro.com",
            f"{note} Estimación orientativa: pide presupuesto. {CHECKED}",
        )
        for key, value, note in [
            ("notary", "600", f"Notaría de la compraventa. {_DEEDS}"),
            ("registry", "400", f"Registro de la compraventa. {_DEEDS}"),
            ("gestoria", "350", "Gestoría: unos 300 €, hasta 1.000 € según cuál."),
            ("appraisal", "400", "Tasación (solo con hipoteca): unos 250-600 €."),
        ]
    ),
]
