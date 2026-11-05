# Fixtures

The parser tests (`test_cpopg.py`, `test_tjsp.py`, `test_pastadigital.py`) run
against real e-SAJ pages (TJSP). Those pages contain the names of parties and
lawyers, so they are **not versioned**; the tests skip when the files are
absent. The remaining tests use synthetic data (`tests/conftest.py`).

To run the parser tests locally, save the pages here (see the test files for the
expected names) and set `JUDGE_NAME` in `.env`.
