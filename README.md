# [Hackster](./README.md) &middot; [![GitHub license]](./LICENSE) ![CI](https://github.com/hackthebox/hackster/actions/workflows/test.yaml/badge.svg) [![codecov](https://codecov.io/gh/hackthebox/Hackster/branch/main/graph/badge.svg?token=DSQFU4YP2W)](https://codecov.io/gh/hackthebox/Hackster)

<!-- Table of Contents -->

- [Installation](#installation)
- [Environment Variables](#environment-variables)
- [Usage](#usage)
- [License](#license)

## Installation

The first step will be to clone the repo

```shell
git clone https://github.com/dimoschi/hackster.git
```

The requirements are:

* [Python] and [Poetry]

1. Install the dependencies
   ```shell
   poetry install
   ```

## Environment Variables

To run this project, you will need to add the following environment variables.

| Variable       | Description                | Default    |
|----------------|----------------------------|------------|
| BOT_NAME       | The name of the bot        | "Hackster" |
| BOT_TOKEN      | The token of the bot       | * Required |
| CHANNEL_DEVLOG | The devlog channel id      | 0          |
| DEBUG          | Toggles debug mode         | False      |
| DEV_GUILD_IDS  | The dev servers of the bot | []         |
| GUILD_IDS      | The servers of the bot     | * Required |

## Usage

Now you are done! You can run the project using

```shell
poetry run task start
```

or test the project using

```shell
poetry run task test
```

## License

Distributed under the MIT License. See [LICENSE](./LICENSE) for more information.

<!-- Packages Links -->

[docker ce]: https://docs.docker.com/install/

[docker compose]: https://docs.docker.com/compose/install/

[poetry]: https://python-poetry.org/docs/

[python]: https://www.python.org/downloads/

<!-- Shields.io links -->

[gitHub license]: https://img.shields.io/badge/license-MIT-blue.svg

[test action]: https://github.com/dimoschi/hackster/actions/workflows/test.yaml/badge.svg
