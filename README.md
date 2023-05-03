# [Hackster](./README.md) &middot; [![GitHub license]](./LICENSE) ![CI](https://github.com/hackthebox/hackster/actions/workflows/test.yaml/badge.svg) [![codecov](https://codecov.io/gh/hackthebox/Hackster/branch/main/graph/badge.svg?token=DSQFU4YP2W)](https://codecov.io/gh/hackthebox/Hackster)

Welcome to the Hackster project! Its goal is to enhance the user experience for HTB's community members, and therefore
it is always going to be a work in progress. We've been inspired by the fantastic work of other projects,
particularly [Noahbot](https://github.com/HeckerBirb/NoahBot), and we're excited to contribute our own ideas and
features to the broader community.

<!-- Table of Contents -->

## Table of Contents

- [Features](#features)
- [Getting Started](#getting-started)
- [Contributing](#contributing)
- [License](#license)
- [Code of Conduct & Security](#code-of-conduct--security)
- [Special Thanks](#special-thanks)
- [Questions & Support](#questions--support)
- [Contributors](#contributors)

## Features

- Message moderation: filter, delete, or flag inappropriate content.
- User management: warn, mute, kick, or ban users based on customizable rules.
- CTF Events management: create and manage channels, roles, and permissions for CTF Events.
- And much more!

## Getting Started

To set up and deploy the Discord bot, follow these steps:

1. The first step will be to clone the repo
   ```shell
   git clone https://github.com/hackthebox/hackster.git
   ```
   The requirements are:
    * [Python](https://www.python.org/)
    * [Poetry](https://python-poetry.org/)

2. Install the dependencies
   ```shell
   poetry install
   ```

3. add the following environment variables.

   | Variable       | Description                | Default    |
      |----------------|----------------------------|------------|
   | BOT_NAME       | The name of the bot        | "Hackster" |
   | BOT_TOKEN      | The token of the bot       | *Required  |
   | CHANNEL_DEVLOG | The devlog channel id      | 0          |
   | DEBUG          | Toggles debug mode         | False      |
   | DEV_GUILD_IDS  | The dev servers of the bot | []         |
   | GUILD_IDS      | The servers of the bot     | *Required  |

4. Now you are done! You can run the project using

   ```shell
   poetry run task start
   ```

   or test the project using

   ```shell
   poetry run task test
   ```

## Contributing

We invite and encourage everyone to contribute to this open-source project! To ensure a smooth and efficient
collaboration process, please review our [CONTRIBUTING](CONTRIBUTING.md) guidelines before submitting any issues or pull
requests. This will help maintain a high-quality codebase and a welcoming environment for all contributors.

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for more information.

## Code of Conduct & Security

Please familiarize yourself with our [Code of Conduct](CODE_OF_CONDUCT.md) to ensure a welcoming and respectful
environment for all project participants. Additionally, review our [Security Policy](SECURITY.md) to understand how to
responsibly disclose security vulnerabilities in the project.

## Special Thanks

In developing our Discord bot, we have drawn inspiration from [Noahbot](https://github.com/HeckerBirb/NoahBot), an
outstanding open-source project that has already demonstrated great success and versatility. We would like to extend our
gratitude and acknowledgement to the creators and contributors of [Noahbot](https://github.com/HeckerBirb/NoahBot),
whose hard work and dedication have laid the groundwork for our project.

## Questions & Support

If you have any questions or need support, feel free to open an issue on the GitHub repository, and we'll be happy to
help you out.

## Contributors

Check [CONTRIBUTORS](CONTRIBUTORS) to see all project contributors.

[docker ce]: https://docs.docker.com/install/

[docker compose]: https://docs.docker.com/compose/install/

[poetry]: https://python-poetry.org/docs/

[python]: https://www.python.org/downloads/

<!-- Shields.io links -->

[gitHub license]: https://img.shields.io/badge/license-MIT-blue.svg
