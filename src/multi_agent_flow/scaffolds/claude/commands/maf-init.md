Initialize the `maf` multi-agent flow in a target project.

Usage: /maf-init <project-root>

If no project root is provided, use the current working directory.

Steps:
1. Check if `maf` is installed by running `maf --help`. If not installed, run `python -m pip install -e .` from this repo root.
2. Run `maf --project-root $ARGUMENTS init` to create a `.maf.yml` config file.
3. Read the generated `.maf.yml` and show the user the default configuration.
4. Ask the user if they want to customize agent commands, validation profiles, or research worker focuses.
