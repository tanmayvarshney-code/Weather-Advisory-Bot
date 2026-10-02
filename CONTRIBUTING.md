# Contributing

Thank you for your interest in contributing to the Weather Advisory Bot!

## Getting Started

1. Fork the repository and clone your fork.
2. Create a new branch for your feature or bug fix:
   `git checkout -b feat/your-feature-name`
3. Install dependencies:
   `pip install -r requirements.txt`
4. Copy .env.example to .env and add your Groq API key.
5. Make your changes, and run the evaluation suite to verify:
   `python eval_suite.py`

## Adding a New SOP

No code changes are needed to add a new SOP! Simply:

1. Open sops.json.
2. Add a new JSON object to the "sops" array following the existing schema.
3. Save the file — the SOP engine loads rules dynamically on every query.

## Code Style

- Follow PEP 8 for Python code.
- Add docstrings to all new functions and classes.
- Keep SOP logic in sops.json and engine logic in sop_engine.py — do not hard-code policies in gent.py.

## Pull Requests

- Ensure eval_suite.py passes with 100% before submitting.
- Write a clear PR description explaining the change and motivation.
- Reference any related issues in the PR description.
