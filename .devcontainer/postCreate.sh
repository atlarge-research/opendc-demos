#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

# Install uv (fast Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

# Create a project-local venv pinned to Python 3.12 and install requirements
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt

# Make the venv kernel discoverable by Jupyter/VS Code
.venv/bin/python -m ipykernel install --user --name opendc-demos --display-name "Python 3.12 (opendc-demos)"

# Make the OpenDC experiment runner executable
chmod +x OpenDCExperimentRunner/bin/OpenDCExperimentRunner || true

echo "Java version:"
java -version
