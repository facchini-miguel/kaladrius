# Contributing to Kaladrius

Thank you for helping. Everything you need is on the documentation site, in
[Contributing](https://kaladrius-docs.facchini.eti.br/contributing); this is the short version.

- **Bugs and ideas:** open an [issue](https://github.com/facchini-miguel/kaladrius/issues)
  with what you did, what you expected and what happened. Security problems go to
  [SECURITY.md](SECURITY.md) instead.
- **Code:** fork, create a branch, and open a pull request. Run the tests and the linter
  first:

  ```bash
  cp .env.example .env            # fill in the passwords
  docker compose up --build -d
  docker compose exec app pytest  # coverage must stay at 90% or more
  docker compose exec app ruff check . && docker compose exec app ruff format --check .
  ```

- **Three languages:** the interface and the documentation are in Portuguese, English and
  Spanish. A change to a text changes the three (`locale/` for the system, `docs/` for the
  site).
- **Decisions:** an important technical or product choice gets a row in the
  [decision log](https://kaladrius-docs.facchini.eti.br/project/decisions).
- **License:** by contributing, you agree that your contribution is licensed under the
  [Apache License 2.0](LICENSE).

Everyone taking part follows the [Code of Conduct](CODE_OF_CONDUCT.md).
