# Security

`ccmigrate` reads local agent chat archives. These archives may contain sensitive code, terminal output, credentials, private prompts, and file paths.

## Supported model

- All sync/export commands are local-only.
- Provider adapters are read-only.
- Generated archives are written to the selected `--store` directory.

## Reporting

For now, open a private security advisory or contact the maintainers before publishing details for vulnerabilities involving data exposure, unsafe writes, or provider-store corruption.

