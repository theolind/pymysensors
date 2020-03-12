# Release procedure

- Install the pypi requirements including `twine`.

  ```sh
  pip3 install -r requirements_pypi.txt
  ```

- Create a release branch from `master`.
- Update version in `mysensors/VERSION` to the new version number, eg `'0.2.0'`.
- Commit with commit message `Bump version to 0.2.0` and push the release branch to origin.
- Create a pull request from release branch to `master` with the commit message as title.
- Squash merge the pull request into `master`.
- Wait for all GitHub actions to have run successfully.
- Go to GitHub releases page and publish the current draft release, setting the correct title and tag version from `master` branch. Do not use a `v` prefix for the tag.
- Fetch and checkout the `master` branch.
- Stage release:

  ```sh
  make test-release
  ```

- Release:

  ```sh
  make release
  ```
