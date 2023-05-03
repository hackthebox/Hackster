# Contributing guidelines

Thank you for your interest in this project!

If you are interested in contributing, **this page contains the golden rules to follow when contributing**. Do note that
failing to comply with our guidelines may lead to a rejection of the contribution.

***

## Guidelines

To contribute, please follow these guidelines:

* Look at the current Issues and/or discussions taking place in the #bot-dev channel on Discord for things that needs to
  be done.
* Please create an issue in Github. For feature requests wait the community moderators to approve the issue.
* Always create a feature branch for your work.
* Please use pull requests from feature branch to development once you are confident that the implementation is done.
* **Do not open a pull request if you aren't assigned to the issue**. If someone is already working on it, consider
  offering to collaborate with that person.

## Before creating a pull request

Please ensure that the following is fulfilled:

### Functionality and testing

* The code has been tested on your own machine and appears to work as intended.
* The code handles errors and malformed input gracefully.
* The command is implemented in slash commands using the same approach as all other places (if applicable).
* Permissions are set correctly.

### Code quality

* Follow PEP-8 style guidelines, except the maximum line width (which can exceed 80 chars in this repo - we're not in
  the 1970's anymore).
* **Lint before you push**. We have simple but strict style rules that are enforced through linting. You must always
  lint your code before committing or pushing.
* Try/except the actual error which is raised.
* Proofread the code and fix oddities.

***Always leave the campground cleaner than you found it.***

## Before commits

Install the project git hooks using [poetry]

```shell
poetry run task precommit
```

Now `pre-commit` will run automatically on `git commit`

```console
root@user:~$ git commit -m "some commit"
Check docstring is first.................................................Passed
Check for merge conflicts................................................Passed
Check Toml...............................................................Passed
Check Yaml...............................................................Passed
Detect Private Key.......................................................Passed
Fix End of Files.........................................................Passed
Tests should end in _test.py.............................................Passed
Trim Trailing Whitespace.................................................Passed
Flake8...................................................................Passed
```

Or you can run it manually

```shell
poetry run task lint
```

[flake8]: https://flake8.pycqa.org/en/latest/

[pre-commit]: https://pre-commit.com/

[poetry]: https://python-poetry.org/
