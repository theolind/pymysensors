# Release procedure
- Create [.pypirc](https://docs.python.org/3.6/distutils/packageindex.html#the-pypirc-file)
  if missing.

	```
	[distutils]
	index-servers=
			pypi
			test

	[test]
	repository = https://testpypi.python.org/pypi
	username = username
	password = password

	[pypi]
	repository = https://pypi.python.org/pypi
	username = username
	password = password
	```

- Create a release branch from dev.
- Merge master into the release branch to make the PR mergeable.
- Update `CHANGELOG.md` by running `scripts/gen_changelog`.
- Replace the unreleased header in the changelog with the new release number.
- Update version in `setup.py`.
- Commit and push the release branch.
- Create a pull request from release branch to master with the upcoming release number as the title. Put the changes for the new release from the updated changelog as the PR message.
- Merge the pull request into master, do not squash.
- Go to github releases and tag a new release on the master branch.
- Fetch and checkout the master branch.
- Generate `README.rst` by running `scripts/gen_rst` (pandoc needed).
- Build source and wheel distributions:
  ```
  rm -rf build
  rm -rf dist
  python3 setup.py sdist bdist_wheel
  ```
- Stage release: `twine upload -r test dist/*`
- Release: `twine upload -r pypi dist/*`
