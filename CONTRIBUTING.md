# How to contribute

Bug reports in the issue tracker and pull requests are welcome.

## Pull request

1. Fork the repository at github.
2. Clone your fork.

    ```sh
    git clone https://github.com/YOUR_GIT_USERNAME/pymysensors.git
    cd pymysensors
    ```

3. Add the main repository as upstream.

    ```sh
    git remote add upstream https://github.com/theolind/pymysensors.git
    ```

4. Create a feature branch based off master branch.

    ```sh
    git checkout -b cool_new_feature master
    ```

5. Make your changes in the new topic branch. New features should preferably be accompanied with new tests. PEP8 and PEP257 style should be followed. We use pylint and flake8 as code linters.
6. Test with tox and make sure existing tests don't fail. Linting will also be checked when tox is run.

    ```sh
    pip3 install -r requirements_dev.txt
    tox
    ```

7. Add and commit your work and describe the additions and or changes in the commit message. Use an editor for the commit message, not the command line. Try to keep the header of the commit message within 50 characters and the body within 72 characters per line. A blank line should separate the header from the body of the commit message. Markdown is cool.

    ```sh
    git add -A
    git commit
    ```

8. Push you local changes to your fork.

    ```sh
    git push origin HEAD
    ```

9. Create a pull request at github to the main pymysensors repository and target the master branch with your changes.
10. Watch build checks turn green :white_check_mark:, and get the :thumbsup: in the code review.
