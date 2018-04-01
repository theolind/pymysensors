# Release procedure
- Create [.pypirc](https://docs.python.org/3.6/distutils/packageindex.html#the-pypirc-file)
  if missing.

	```
	[distutils]
	index-servers=
			pypi
			test

	[testpypi]
	repository = https://test.pypi.org/legacy/
	username = username
	password = password

	[pypi]
	username = username
	password = password
	```
  There's a new API for PyPi, see this [page](https://packaging.python.org/guides/migrating-to-pypi-org/#uploading) for more info.
- Install the pypi requirements including `twine`.
  ```
  pip3 install -r requirements_pypi.txt
  ```
- Create a release branch from dev.
- Merge master into the release branch to make the PR mergeable.
- Update version in `mysensors/version.py` to the new version number, eg `'0.2.0'`.
- Update `CHANGELOG.md` by running `scripts/gen_changelog`.
- Commit and push the release branch.
- Create a pull request from release branch to master with the upcoming release number as the title. Put the changes for the new release from the updated changelog as the PR message.
- Merge the pull request into master, do not squash.
- Go to github releases and tag a new release on the master branch. Put the PR message as the description for the release.
- Fetch and checkout the master branch.
- Build source and wheel distributions:
  ```
  rm -rf build
  rm -rf dist
  python3 setup.py sdist bdist_wheel
  ```
- Stage release (upload distributions one at a time to avoid bug, see this [blog](https://dustingram.com/articles/2018/03/16/markdown-descriptions-on-pypi)):
  ```
  twine upload -r testpypi dist/*.tar.gz
  twine upload -r testpypi dist/*.whl
  ```
- Release:
  ```
  twine upload -r pypi dist/*.tar.gz
  twine upload -r pypi dist/*.whl
  ```
- Fetch and checkout the develop branch.
- Merge master into develop.
- Update version in `mysensors/version.py` to the new develop version number, eg `'0.3.0.dev0'`
- Commit the version bump and push to develop branch.
