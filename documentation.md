# Generating docs

## Requirements

- sphinx
- recommonmark
- sphinx_rtd_theme

## Generating

Update version on `conf.py`, generate html and move the generated folder to docs

```
$ cd gendocs
$ make html
# cp _build/html/ ../docs/
```