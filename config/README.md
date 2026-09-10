# Config (slim fork)

- `reader.yaml` — `oskh_data` reader mode (`parquet` / `duckdb` / …)
- `chip_diagnosis.yaml` — chip diagnosis tooling

Live runtime YAML files were removed.

## Runtime YAML in CI

This standalone repository does not contain `config/runtime.ci.yaml`. If a CI
job inherits a relative setting such as
`MINIQMT_CONFIG_PATH=config/runtime.ci.yaml`, the path is resolved in this
repository, reported as missing, and skipped. Configuration keys not supplied
by another YAML file or a non-empty environment variable then use their caller
defaults. This is the current fail-open behavior.

Consequently, a green R2 run with that inherited setting only proves that a
missing parent-repository path no longer breaks imports or tests. It does not
mean that the parent repository's runtime configuration was found or applied.
Any future CI job that requires YAML values must provide the file explicitly
and validate its presence instead of treating the current R2 result as a
configuration-effectiveness check.
