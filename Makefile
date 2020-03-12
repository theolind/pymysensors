.PHONY: help black black-format build clean clean-build clean-pyc coverage lint release test-release test test-all

help:
	@echo "black - run black code formatter check"
	@echo "black-format - run black code formatter format"
	@echo "build - build a distribution"
	@echo "clean - run all clean operations"
	@echo "clean-build - remove build artifacts"
	@echo "clean-pyc - remove Python file artifacts"
	@echo "coverage - check code coverage with pytest-cov plugin"
	@echo "lint - check style with flake8, pylint and pydocstyle"
	@echo "release - package and upload a release to PyPI"
	@echo "test-release - package and upload a release to test PyPI"
	@echo "test - run tests quickly with the default Python"
	@echo "test-all - run tests on every Python version with tox"

black:
	black --check ./

black-format:
	black ./

build:
	python setup.py sdist bdist_wheel

clean: clean-build clean-pyc

clean-build:
	rm -fr build/
	rm -fr dist/
	rm -fr *.egg-info

clean-pyc:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +

coverage:
	pytest --cov-report term-missing --cov=mysensors tests/

lint:
	tox -e lint

release: clean build
	twine upload dist/*

test-release: clean build
	twine upload --repository-url https://test.pypi.org/legacy/ dist/*

test:
	pytest tests/

test-all:
	tox
