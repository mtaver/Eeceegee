# ECG Learning Coach

## Problem statement

Medical students need practice interpreting ECGs, but tools that simply return a diagnosis do not reveal or improve the learner's reasoning process.

## Proposed solution

ECG Learning Coach is an educational application that helps students build ECG interpretation skills by working through structured cases and improving their reasoning with targeted feedback. The student remains the primary reasoner; the system is not built around an ECG diagnosis model.

## Learning philosophy

The application focuses on how a learner reaches an interpretation: what they observed, how they connected findings, and where their reasoning can improve. Future feedback is intended to favor hints and guiding questions before explanations.

## Core learning loop

1. The student observes an ECG case.
2. The student reasons through the findings step by step.
3. The student explains their reasoning.
4. The system evaluates the reasoning and provides targeted feedback.
5. The student tries again and progress is tracked.

## Technology stack

- Python
- Streamlit
- pytest
- JSON case data

## Project structure

```text
.
├── app.py
├── assets/ecg/
├── components/
├── data/cases.json
├── services/
├── tests/test_cases.py
├── .gitignore
├── README.md
└── requirements.txt
```

## Installation

Use Python 3.10 or later. From the project directory, create and activate a virtual environment, then install dependencies:

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Run the application

```bash
streamlit run app.py
```

The initial page lets the learner choose a level. Starting a case displays a placeholder message while the case engine is planned.

## Run tests

```bash
pytest
```

## Git and GitHub workflow

Check the current repository and remote before making changes:

```bash
git status
git branch --show-current
git remote -v
```

Review changes with `git diff` and `git status` before committing. Preserve existing remotes and branches. Create or configure a GitHub repository only when explicitly requested. Do not commit or push until the project owner instructs you to do so.

## Educational use

This application is an educational tool and does not replace professional clinical judgment, medical education, or clinical decision-making.
