"""scripts/fetch_voice.py: the step between a deploy and the Piper voice. Its exit code is what the deployment
tool and the Docker build rely on: 0 = the voice is ready (or not needed), 1 = it could not be fetched.

The script is not a package, so it is loaded from its file. No network, no real model, no .env: ``load_dotenv`` is
replaced (the script would read the real ``.env`` of the service folder), the download and the voice loader are fakes.
"""

import importlib.util
import os
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "fetch_voice.py"
VOICE = "en_GB-alan-medium"
HINT = "The service will start with the pyttsx3 voice until it is there."


@pytest.fixture
def script():
    spec = importlib.util.spec_from_file_location("fetch_voice_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.load_dotenv = lambda *args, **kwargs: False  # never read the real .env
    return module


@pytest.fixture
def run(script, monkeypatch, tmp_path):
    """Runs ``main()`` with a clean environment and a model folder inside ``tmp_path``."""
    model_dir = tmp_path / "models"

    def go(*argv: str, engine: str | None = None) -> int:
        for name in ("TTS_ENGINE", "TTS_PIPER_VOICE", "TTS_PIPER_MODEL_DIR"):
            monkeypatch.delenv(name, raising=False)
        monkeypatch.setenv("TTS_PIPER_MODEL_DIR", str(model_dir))
        if engine is not None:
            monkeypatch.setenv("TTS_ENGINE", engine)
        monkeypatch.setattr(sys, "argv", ["fetch_voice.py", *argv])
        return script.main()

    go.model_dir = model_dir  # type: ignore[attr-defined]
    return go


class Calls:
    """Fakes for ``voice_is_usable`` and ``fetch`` that remember how they were called."""

    def __init__(self, script, monkeypatch, *, usable: bool = False, fetch_error: Exception | None = None) -> None:
        self.usable_calls: list[tuple[Path, str]] = []
        self.fetch_calls: list[tuple[Path, str]] = []
        self._usable = usable
        self._fetch_error = fetch_error
        monkeypatch.setattr(script, "voice_is_usable", self._voice_is_usable)
        monkeypatch.setattr(script, "fetch", self._fetch)

    def _voice_is_usable(self, model_dir: Path, voice: str) -> bool:
        self.usable_calls.append((model_dir, voice))
        return self._usable

    def _fetch(self, model_dir: Path, voice: str) -> None:
        self.fetch_calls.append((model_dir, voice))
        if self._fetch_error is not None:
            raise self._fetch_error


# 1 -------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("engine", ["espeak", "pyttsx3"])
def test_another_engine_needs_no_voice_and_exits_0(script, run, monkeypatch, capsys, engine):
    calls = Calls(script, monkeypatch)

    code = run(engine=engine)

    assert code == 0
    assert f"TTS_ENGINE is {engine}: no Piper voice needed" in capsys.readouterr().out
    assert calls.usable_calls == [] and calls.fetch_calls == []


# 2 -------------------------------------------------------------------------------------------------------------


def test_a_usable_voice_exits_0_without_fetching(script, run, monkeypatch, capsys):
    calls = Calls(script, monkeypatch, usable=True)

    code = run(engine="piper")

    assert code == 0
    assert f"Piper voice {VOICE} is ready in {run.model_dir}" in capsys.readouterr().out
    assert calls.usable_calls == [(run.model_dir, VOICE)]
    assert calls.fetch_calls == []


def test_the_default_engine_is_piper(script, run, monkeypatch):
    calls = Calls(script, monkeypatch, usable=True)

    assert run() == 0

    assert calls.usable_calls == [(run.model_dir, VOICE)]


# 3 -------------------------------------------------------------------------------------------------------------


def test_an_explicit_voice_is_fetched_even_when_the_engine_is_not_piper(script, run, monkeypatch, capsys):
    calls = Calls(script, monkeypatch, usable=False)

    code = run("--voice", "en_US-other-low", engine="espeak")

    assert code == 0
    assert calls.usable_calls == [(run.model_dir, "en_US-other-low")]
    assert calls.fetch_calls == [(run.model_dir, "en_US-other-low")]
    assert "Piper voice en_US-other-low is ready" in capsys.readouterr().out


# 4 -------------------------------------------------------------------------------------------------------------


def test_a_missing_voice_is_fetched_and_the_script_exits_0(script, run, monkeypatch, capsys):
    calls = Calls(script, monkeypatch, usable=False)

    code = run(engine="piper")

    out = capsys.readouterr()
    assert code == 0
    assert calls.fetch_calls == [(run.model_dir, VOICE)]
    assert f"Fetching Piper voice {VOICE} into {run.model_dir} (about 60 MB)" in out.out
    assert f"Piper voice {VOICE} is ready\n" in out.out
    assert out.err == ""


# 5 -------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "error",
    [OSError("no network"), ValueError("unknown voice"), OSError(28, "No space left on device")],
)
def test_a_failed_fetch_exits_1_and_says_so_on_stderr(script, run, monkeypatch, capsys, error):
    Calls(script, monkeypatch, usable=False, fetch_error=error)

    code = run(engine="piper")

    out = capsys.readouterr()
    assert code == 1  # the one failure code the deployment tool and the Docker build rely on
    assert f"Could not fetch Piper voice {VOICE}: {error}" in out.err
    assert HINT in out.err
    assert "is ready" not in out.out  # no success line after a failure
    assert HINT not in out.out


# 6 -------------------------------------------------------------------------------------------------------------


class _FakeDownload:
    """Stands for ``piper.download_voices.download_voice``: writes a voice into the folder it is given."""

    def __init__(self) -> None:
        self.folders: list[Path] = []

    def __call__(self, voice: str, download_dir: Path) -> None:
        self.folders.append(Path(download_dir))
        (Path(download_dir) / f"{voice}.onnx").write_bytes(b"model")
        (Path(download_dir) / f"{voice}.onnx.json").write_text("{}")


@pytest.fixture
def download(monkeypatch):
    download_voices = pytest.importorskip("piper.download_voices")
    fake = _FakeDownload()
    monkeypatch.setattr(download_voices, "download_voice", fake)
    return fake


def test_a_download_that_does_not_load_leaves_nothing_in_the_model_folder(script, monkeypatch, tmp_path, download):
    model_dir = tmp_path / "models"
    monkeypatch.setattr(script, "voice_is_usable", lambda folder, voice: False)

    with pytest.raises(RuntimeError, match=f"the downloaded voice {VOICE} does not load"):
        script.fetch(model_dir, VOICE)

    assert list(model_dir.iterdir()) == []  # neither the model, nor its config, nor the scratch folder
    assert not (model_dir / f"{VOICE}.onnx").exists() and not (model_dir / f"{VOICE}.onnx.json").exists()
    assert len(download.folders) == 1 and not download.folders[0].exists()


def test_a_download_that_fails_leaves_nothing_in_the_model_folder(script, tmp_path, monkeypatch):
    download_voices = pytest.importorskip("piper.download_voices")

    def broken(voice: str, download_dir: Path) -> None:
        (Path(download_dir) / f"{voice}.onnx").write_bytes(b"half a model")
        raise OSError("connection reset")

    monkeypatch.setattr(download_voices, "download_voice", broken)
    model_dir = tmp_path / "models"

    with pytest.raises(OSError, match="connection reset"):
        script.fetch(model_dir, VOICE)

    assert list(model_dir.iterdir()) == []


def test_a_good_download_is_moved_into_place_model_first_and_config_last(script, monkeypatch, tmp_path, download):
    model_dir = tmp_path / "models"
    monkeypatch.setattr(script, "voice_is_usable", lambda folder, voice: True)
    moved: list[str] = []
    real_replace = os.replace

    def spy(source, destination):
        moved.append(Path(destination).name)
        real_replace(source, destination)

    monkeypatch.setattr(script.os, "replace", spy)

    script.fetch(model_dir, VOICE)

    assert moved == [f"{VOICE}.onnx", f"{VOICE}.onnx.json"]  # the config last: a model without it is "not there"
    assert sorted(path.name for path in model_dir.iterdir()) == [f"{VOICE}.onnx", f"{VOICE}.onnx.json"]
    assert (model_dir / f"{VOICE}.onnx").read_bytes() == b"model"
    assert not download.folders[0].exists()  # the temporary folder is gone
    # downloaded inside the model folder: the move into place stays on one filesystem, so it is atomic
    assert download.folders[0].parent == model_dir and download.folders[0].name.startswith(".fetch-")


# 7 -------------------------------------------------------------------------------------------------------------


class _FakePiperVoice:
    loaded: list[Path] = []
    error: Exception | None = None

    @classmethod
    def load(cls, model: Path) -> object:
        cls.loaded.append(Path(model))
        if cls.error is not None:
            raise cls.error
        return object()


@pytest.fixture
def piper_voice(monkeypatch):
    piper = pytest.importorskip("piper")
    _FakePiperVoice.loaded = []
    _FakePiperVoice.error = None
    monkeypatch.setattr(piper, "PiperVoice", _FakePiperVoice)
    return _FakePiperVoice


def test_a_model_without_its_config_counts_as_not_there(script, tmp_path, piper_voice):
    (tmp_path / f"{VOICE}.onnx").write_bytes(b"model")

    assert script.voice_is_usable(tmp_path, VOICE) is False
    assert piper_voice.loaded == []  # decided from the files, the voice was not even loaded


def test_a_config_without_its_model_counts_as_not_there(script, tmp_path, piper_voice):
    (tmp_path / f"{VOICE}.onnx.json").write_text("{}")

    assert script.voice_is_usable(tmp_path, VOICE) is False
    assert piper_voice.loaded == []


def test_both_files_that_load_are_usable(script, tmp_path, piper_voice):
    (tmp_path / f"{VOICE}.onnx").write_bytes(b"model")
    (tmp_path / f"{VOICE}.onnx.json").write_text("{}")

    assert script.voice_is_usable(tmp_path, VOICE) is True
    assert piper_voice.loaded == [tmp_path / f"{VOICE}.onnx"]


def test_both_files_that_do_not_load_are_not_usable(script, tmp_path, piper_voice):
    (tmp_path / f"{VOICE}.onnx").write_bytes(b"not a model")
    (tmp_path / f"{VOICE}.onnx.json").write_text("{}")
    piper_voice.error = RuntimeError("invalid model")

    assert script.voice_is_usable(tmp_path, VOICE) is False
    assert piper_voice.loaded == [tmp_path / f"{VOICE}.onnx"]
