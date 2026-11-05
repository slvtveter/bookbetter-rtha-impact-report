PY ?= .venv/bin/python

.PHONY: all setup data report notebook clean

all: data report notebook

setup:
	uv venv .venv --python 3.12
	uv pip install --python $(PY) -r requirements.txt

data:
	$(PY) src/generate_data.py

report:
	$(PY) src/build_report.py

notebook:
	$(PY) src/make_notebook.py

clean:
	rm -rf build docs/index.html docs/report.pdf docs/report.png notebooks/analysis.ipynb
