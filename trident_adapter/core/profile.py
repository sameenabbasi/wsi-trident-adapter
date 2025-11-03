from __future__ import annotations

from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib

from trident_adapter.utils import adapter_state, paths


def get_active_profile() -> str:
    data = adapter_state.read_adapter_state()
    profile = data.get("profile")
    if not profile:
        raise RuntimeError(
            "No profile configured. Run: wsi-trident-adapter-install setup "
        )
    return str(profile)


def resolve_profile_dir(profile: str) -> Path:
    directory = paths.profile_dir(profile)
    if not directory.is_dir():
        raise RuntimeError(
            f"Profile directory not found for '{profile}'. This installation"
            " appears corrupted; reinstall the package or contact the"
            " developers."
        )
    return directory


def resolve_profile_toml(profile: str) -> Path:
    path = paths.profile_toml(profile)
    if not path.exists():
        raise RuntimeError(
            f"Profile '{profile}' is missing profile.toml. This installation"
            " appears corrupted; reinstall the package or contact the"
            " developers."
        )
    return path


def load_profile_data(profile: str) -> dict:
    path = resolve_profile_toml(profile)
    with path.open("rb") as handle:
        return tomllib.load(handle)


def get_profile_env(profile: str) -> dict[str, str]:
    data = load_profile_data(profile)
    env = data.get("env")
    if not isinstance(env, dict):
        raise RuntimeError(
            f"Profile '{profile}' is missing an [env] configuration section."
        )
    return {key: str(value) for key, value in env.items()}


def get_profile_modules(profile: str) -> list[str]:
    data = load_profile_data(profile)
    modules = data.get("modules", [])

    if modules is None:
        return []

    if not isinstance(modules, list):
        raise RuntimeError(
            f"Profile '{profile}' defines modules in an unexpected format."
        )

    values: list[str] = []
    for entry in modules:
        if not isinstance(entry, str):
            raise RuntimeError(
                f"Profile '{profile}' modules must be strings; got {entry!r}."
            )
        values.append(entry)
    return values


def get_profile_notes(profile: str) -> list[str]:
    data = load_profile_data(profile)
    notes = data.get("notes", [])

    if notes is None:
        return []

    if not isinstance(notes, list):
        raise RuntimeError(
            f"Profile '{profile}' defines notes in an unexpected format."
        )

    values: list[str] = []
    for entry in notes:
        if not isinstance(entry, str):
            raise RuntimeError(
                f"Profile '{profile}' notes must be strings; got {entry!r}."
            )
        values.append(entry)
    return values


def get_assets_root(profile: str) -> Path:
    env = get_profile_env(profile)
    root = env.get("ASSETS_ROOT")
    if not root:
        raise RuntimeError(
            f"Profile '{profile}' does not define env.ASSETS_ROOT"
        )
    return Path(root)


def resolve_example_path(profile: str) -> Path:
    root = get_assets_root(profile)
    return paths.assets_example_dir(root)
