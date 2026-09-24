# Model B

Model B is an agent-harness workflow system for the Pi coding agent: skill bundles, generated
sub-agent definitions, portable lifecycle hooks and workflow scripts, delivered by one
installer and project scaffolder.

To install it, follow the [install guide](docs/install-guide.md). The guide is the single
source of install instructions; nothing here repeats it.

What is in this repository:

- `modelb_axi/` — the installer and project scaffolder;
- `skills-src/` — the skill bundles;
- `generator/` — the sub-agent definitions and the templates they are rendered from;
- `hooks-src/` — the lifecycle hooks;
- `scripts/` — the workflow scripts;
- `contracts/` — the interfaces to the projects Model B works with;
- `tests/` — the test suite (`python3 -m unittest discover -s tests -t .`).
