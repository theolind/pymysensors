# Release procedure

- Install the pypi requirements including `twine`.

  ```sh
  pip3 install -r requirements_pypi.txt
  ```

- Create a release branch from dev.
- Merge master into the release branch to make the PR mergeable.
- Update version in `mysensors/VERSION` to the new version number, eg `'0.2.0'`.
- Commit with commit message `Bump version to 0.2.0` and push the release branch to origin.
- Create a pull request from release branch to `master` with the commit message as title.
- Merge the pull request into master, do not squash.
- Wait for all GitHub actions to have run successfully.
- Go to github releases and tag a new release on the master branch.
- Fetch and checkout the master branch.
- Stage release:

  ```sh
  make test-release
  ```

- Release:

  ```sh
  make release
  ```
