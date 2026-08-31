from importlib.resources import files


def load_prompt(name: str) -> str:
    resource = files("app.agent.prompts").joinpath(f"{name}.txt")
    return resource.read_text(encoding="utf-8").strip()
