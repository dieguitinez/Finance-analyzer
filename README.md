# Finance Analyzer - Project Guidelines

This document outlines the project structure and development best practices for the Finance Analyzer.

## Project Structure

- `src/`: Core logic and data engines.
- `quantum_engine/`: Quantum-inspired algorithms and scoring models.
- `tmp/`: Temporary test scripts and experiments.
- `app.py`: Main entry point for the Streamlit dashboard.

## Best Practices

### 1. Package Structure
Always include an `__init__.py` file in every directory containing Python modules (e.g., `src/`, `quantum_engine/`). This ensures they are recognized as packages by Python and development tools.

### 2. Import Resolution
The project uses `.vscode/settings.json` to configure Pylance extra paths. Ensure the workspace root is always included in `python.analysis.extraPaths` to resolve internal packages like `quantum_engine`.

### 3. Testing
For temporary tests in `tmp/`, maintain the standard of adding the parent directory to `sys.path`. For long-term testing, consider migrating to a root `tests/` directory using `pytest`.

### 4. Dependency Management
Keep `requirements.txt` updated with any new libraries. This is critical for deployments and environment replication.

### 5. Virtual Environments
Always use the local `.venv`. Execute scripts using the interpreter within the virtual environment (e.g., `.\.venv\Scripts\python.exe`).

---
*Created by Antigravity AI Assistant.*
