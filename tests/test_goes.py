import dataclasses
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from swpc_kit.errors import ParseError, SourceNotReady, UnexpectedContent
from swpc_kit.models.goes import (
    FlareClass,
    GoesIntegralProtons,
    GoesXrays,
    ProtonSample,
    XrayBand,
    XraySample,
)
from swpc_kit.parse.goes import (
    GOES_INTEGRAL_PROTONS_1_DAY_URL,
    GOES_XRAYS_1_DAY_URL,
    parse_goes_integral_protons,
    parse_goes_xrays,
)

FIXTURES = Path(__file__).parent / "fixtures"
XRAYS = "goes-xrays-1-day/2026-10-15.json"
PROTONS = "goes-protons-1-day/2026-10-15.json"


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


def xray_record(**changes: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "time_tag": "2026-10-15T12:00:00Z",
        "satellite": 18,
        "flux": 2.5e-5,
        "observed_flux": 2.6e-5,
        "electron_correction": 1e-6,
        "electron_contaminaton": False,
        "energy": "0.1-0.8nm",
    }
    record.update(changes)
    return record


def proton_record(**changes: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "time_tag": "2026-10-15T12:00:00Z",
        "satellite": 18,
        "flux": 0.27,
        "energy": ">=10 MeV",
    }
    record.update(changes)
    return record


def dump(*records: dict[str, Any]) -> bytes:
    return json.dumps(list(records)).encode()


# --- Flare class ------------------------------------------------------------


@pytest.mark.parametrize(
    ("flux", "label"),
    [
        (9.999999717180685e-10, "A0.0"),
        (5e-8, "A5.0"),
        (9.99e-8, "A9.9"),
        (1e-7, "B1.0"),
        (7e-7, "B7.0"),
        (9.999e-7, "B9.9"),
        (1e-6, "C1.0"),
        (3e-6, "C3.0"),
        (3.952709903387586e-06, "C3.9"),
        (1e-5, "M1.0"),
        (2.3e-5, "M2.3"),
        (2.5e-5, "M2.5"),
        (9.96e-5, "M9.9"),
        (1e-4, "X1.0"),
        (9.0e-4, "X9.0"),
        (1.2e-3, "X12.0"),
        (2.8e-3, "X28.0"),
    ],
)
def test_flare_class_from_flux(flux: float, label: str) -> None:
    flare = FlareClass.from_flux(flux)
    assert str(flare) == label
    assert flare.letter == label[0]
    assert flare.multiplier == float(label[1:])


def test_flare_class_lower_bound_flux() -> None:
    assert FlareClass("M", 2.5).flux == pytest.approx(2.5e-5)
    assert FlareClass("X", 12.0).flux == pytest.approx(1.2e-3)


@pytest.mark.parametrize("flux", [0.0, -1e-6, math.nan, math.inf])
def test_flare_class_needs_a_positive_flux(flux: float) -> None:
    with pytest.raises(ValueError, match="flux"):
        FlareClass.from_flux(flux)


def test_flare_classes_order_by_flux() -> None:
    labels = ["A9.9", "B1.0", "C9.9", "M1.0", "M2.5", "X1.0", "X9.9", "X12.0"]
    classes = [FlareClass(label[0], float(label[1:])) for label in labels]
    shuffled = [classes[i] for i in (3, 7, 0, 5, 1, 6, 2, 4)]
    assert sorted(shuffled) == classes


@pytest.mark.parametrize(
    ("letter", "multiplier"),
    [("Z", 1.0), ("m", 1.0), ("C", 10.0), ("C", -1.0), ("X", math.inf)],
)
def test_flare_class_rejects_bad_values(letter: str, multiplier: float) -> None:
    with pytest.raises(ValueError, match="flare class"):
        FlareClass(letter, multiplier)


# --- X-rays: fixture --------------------------------------------------------


def test_xrays_fixture() -> None:
    xrays = parse_goes_xrays(fixture(XRAYS))
    assert isinstance(xrays, GoesXrays)
    assert len(xrays.values) == 258
    assert xrays.source_url == GOES_XRAYS_1_DAY_URL
    assert xrays.values[0] == XraySample(
        time=utc(2026, 10, 14, 17, 56),
        satellite=18,
        energy="0.05-0.4nm",
        flux=5.798543423196634e-09,
        observed_flux=2.4681435562001752e-08,
        electron_correction=1.888289169471591e-08,
        electron_contamination=True,
    )
    assert xrays.data_time == utc(2026, 10, 15, 17, 53)
    times = [v.time for v in xrays.values]
    assert times == sorted(times)


def test_xrays_bands() -> None:
    xrays = parse_goes_xrays(fixture(XRAYS))
    assert xrays.energies == ("0.05-0.4nm", "0.1-0.8nm")
    long = xrays.band(XrayBand.LONG)
    short = xrays.band(XrayBand.SHORT)
    assert len(long) == len(short) == 129
    assert all(v.energy == "0.1-0.8nm" for v in long)
    assert xrays.band("0.5-4nm") == ()
    assert not any(v.electron_contamination for v in long)


def test_xrays_flare_class_only_on_the_long_band() -> None:
    xrays = parse_goes_xrays(fixture(XRAYS))
    assert all(v.flare_class is None for v in xrays.band(XrayBand.SHORT))
    assert all(v.flare_class is not None for v in xrays.band(XrayBand.LONG))


def test_xrays_peak_and_latest() -> None:
    xrays = parse_goes_xrays(fixture(XRAYS))
    peak = xrays.peak()
    assert peak is not None
    assert peak.time == utc(2026, 10, 15, 15, 57)
    assert str(peak.flare_class) == "C3.9"
    latest = xrays.latest()
    assert latest is not None
    assert latest.time == utc(2026, 10, 15, 17, 53)
    assert latest.energy == XrayBand.LONG
    short = xrays.latest(XrayBand.SHORT)
    assert short is not None
    assert short.energy == XrayBand.SHORT
    assert xrays.latest("0.5-4nm") is None
    assert xrays.peak("0.5-4nm") is None


# --- X-rays: hand-built cases -----------------------------------------------


def test_xrays_nulls_become_none() -> None:
    xrays = parse_goes_xrays(
        dump(
            xray_record(
                flux=None,
                observed_flux=None,
                electron_correction=None,
                electron_contaminaton=None,
            )
        )
    )
    sample = xrays.values[0]
    assert sample.flux is None
    assert sample.electron_contamination is None
    assert sample.flare_class is None
    assert xrays.peak() is None


def test_xrays_flare_class_of_a_sample() -> None:
    sample = parse_goes_xrays(dump(xray_record(flux=2.5e-5))).values[0]
    assert sample.flare_class == FlareClass("M", 2.5)
    for flux in (0.0, -1e-9):
        sample = parse_goes_xrays(dump(xray_record(flux=flux))).values[0]
        assert sample.flare_class is None


def test_xrays_unknown_band_is_kept() -> None:
    xrays = parse_goes_xrays(dump(xray_record(energy="0.5-4nm")))
    assert xrays.energies == ("0.5-4nm",)
    assert xrays.values[0].flare_class is None


def test_xrays_are_sorted_oldest_first() -> None:
    xrays = parse_goes_xrays(
        dump(
            xray_record(time_tag="2026-10-15T12:01:00Z"),
            xray_record(time_tag="2026-10-15T12:00:00Z", energy="0.05-0.4nm"),
            xray_record(time_tag="2026-10-15T12:00:00Z"),
        )
    )
    assert [(v.time.minute, v.energy) for v in xrays.values] == [
        (0, "0.05-0.4nm"),
        (0, "0.1-0.8nm"),
        (1, "0.1-0.8nm"),
    ]


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"flux": "x"}, "flux"),
        ({"observed_flux": True}, "observed_flux"),
        ({"electron_contaminaton": "no"}, "electron_contaminaton"),
        ({"satellite": None}, "satellite"),
        ({"satellite": -18}, "satellite"),
        ({"energy": None}, "energy"),
        ({"time_tag": "2026-10-15"}, "time_tag"),
    ],
)
def test_xrays_inconsistent_values(changes: dict[str, Any], field: str) -> None:
    xrays = parse_goes_xrays(dump(xray_record(), xray_record(**changes)))
    assert [(s.index, s.field) for s in xrays.skipped] == [(1, field)]
    with pytest.raises(ParseError) as info:
        parse_goes_xrays(dump(xray_record(**changes)))
    assert info.value.field == field


def test_xrays_missing_misspelled_field() -> None:
    record = xray_record()
    del record["electron_contaminaton"]
    # Missing from every record: SWPC fixed the spelling, a new format.
    with pytest.raises(UnexpectedContent, match="'electron_contaminaton' missing"):
        parse_goes_xrays(dump(record))
    # Missing from one record only: that record is skipped.
    xrays = parse_goes_xrays(dump(xray_record(), record))
    assert [(s.index, s.field) for s in xrays.skipped] == [(1, "electron_contaminaton")]


def test_xrays_errors() -> None:
    raw = fixture(XRAYS)
    with pytest.raises(SourceNotReady):
        parse_goes_xrays(raw[: len(raw) // 2])
    with pytest.raises(SourceNotReady):
        parse_goes_xrays(b"[]")
    with pytest.raises(UnexpectedContent):
        parse_goes_xrays(b"<html><head><title>404</title></head></html>")


def test_xrays_accepts_str_and_source_url() -> None:
    raw = fixture(XRAYS)
    assert parse_goes_xrays(raw.decode()) == parse_goes_xrays(raw)
    secondary = "https://services.swpc.noaa.gov/json/goes/secondary/xrays-1-day.json"
    assert parse_goes_xrays(raw, source_url=secondary).source_url == secondary


# --- Integral protons -------------------------------------------------------


def test_protons_fixture() -> None:
    protons = parse_goes_integral_protons(fixture(PROTONS))
    assert isinstance(protons, GoesIntegralProtons)
    assert len(protons.values) == 368
    assert protons.source_url == GOES_INTEGRAL_PROTONS_1_DAY_URL
    assert protons.values[0] == ProtonSample(
        time=utc(2026, 10, 14, 18, 0),
        satellite=18,
        energy=">=1 MeV",
        threshold_mev=1.0,
        flux=4.691866874694824,
    )
    assert protons.data_time == utc(2026, 10, 15, 17, 45)


def test_protons_thresholds_and_series() -> None:
    protons = parse_goes_integral_protons(fixture(PROTONS))
    assert protons.thresholds == (1.0, 5.0, 10.0, 30.0, 50.0, 60.0, 100.0, 500.0)
    for threshold in protons.thresholds:
        series = protons.series(threshold)
        assert len(series) == 46
        assert all(v.threshold_mev == threshold for v in series)
        times = [v.time for v in series]
        assert times == sorted(set(times))
    assert protons.series(7) == ()
    latest = protons.latest(10)
    assert latest is not None
    assert latest.time == utc(2026, 10, 15, 17, 45)
    assert latest.energy == ">=10 MeV"
    assert protons.latest(7) is None


@pytest.mark.parametrize(
    ("energy", "threshold"),
    [(">=10 MeV", 10.0), (">=1 MeV", 1.0), (">= 2.5 MeV", 2.5), (">=500MeV", 500.0)],
)
def test_protons_energy_labels(energy: str, threshold: float) -> None:
    sample = parse_goes_integral_protons(dump(proton_record(energy=energy))).values[0]
    assert sample.threshold_mev == threshold
    assert sample.energy == energy


def test_protons_null_flux_becomes_none() -> None:
    sample = parse_goes_integral_protons(dump(proton_record(flux=None))).values[0]
    assert sample.flux is None


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"energy": "10-50 MeV"}, "energy"),
        ({"energy": ">=10 keV"}, "energy"),
        ({"energy": 10}, "energy"),
        ({"flux": "high"}, "flux"),
        ({"satellite": "18a"}, "satellite"),
        ({"time_tag": None}, "time_tag"),
    ],
)
def test_protons_inconsistent_values(changes: dict[str, Any], field: str) -> None:
    with pytest.raises(ParseError) as info:
        parse_goes_integral_protons(dump(proton_record(**changes)))
    assert info.value.field == field
    assert info.value.index == 0


def test_protons_errors() -> None:
    raw = fixture(PROTONS)
    with pytest.raises(SourceNotReady):
        parse_goes_integral_protons(raw[:-2])
    with pytest.raises(UnexpectedContent):
        parse_goes_integral_protons(b"<html></html>")


# --- Models -----------------------------------------------------------------


def test_models_are_frozen() -> None:
    xrays = parse_goes_xrays(fixture(XRAYS))
    with pytest.raises(dataclasses.FrozenInstanceError):
        xrays.source_url = "x"  # type: ignore[misc]
    assert not hasattr(xrays, "__dict__")


def test_empty_series_cannot_be_built() -> None:
    with pytest.raises(ValueError, match="empty"):
        GoesXrays(values=(), source_url=GOES_XRAYS_1_DAY_URL)
    with pytest.raises(ValueError, match="empty"):
        GoesIntegralProtons(values=(), source_url=GOES_INTEGRAL_PROTONS_1_DAY_URL)


def test_naive_time_cannot_be_built() -> None:
    naive = datetime(2026, 10, 15)  # noqa: DTZ001
    with pytest.raises(ValueError, match="UTC"):
        ProtonSample(
            time=naive, satellite=18, energy=">=10 MeV", threshold_mev=10.0, flux=1.0
        )
