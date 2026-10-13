# Reverse engineer anything module

This optional module distributes the REA skill for supplied native, managed, Electron/JavaScript, packaged, firmware, and browser targets. Use it when an answer needs shipped-artifact analysis, decompilation, version comparison, or requested runtime evidence. Ordinary source-repository architecture analysis uses Graphify and normal source tools.

Select the module with configuration-only setup:

```powershell
& 'C:\Toolkits\engineering-starter-kit\Setup.ps1' -ProjectRoot 'C:\Projects\MyApp' -Modules reverse-engineer-anything -Static -SkipDependencies -SkipStudio
```

Combine it with `-Modules claudely,reverse-engineer-anything` when both capabilities are useful. Setup copies instructions; it makes no REA connection, engine installation, provider request, target acquisition, or target execution. The base toolkit's installation/bootstrap behavior is separate, which is why the example explicitly skips dependency preparation.

Open a fresh Codex session in the destination and invoke `$reverse-engineer-anything` with the named artifact/path, question, and permitted observations. Start with [SKILL.md](payload/.agents/skills/reverse-engineer-anything/SKILL.md) and read only the relevant references. The active host's actual REA tool inventory and input schemas determine supported operations. Skill metadata, successful file installation, and a CLI package version do not prove a connected server or available engines. Follow the recovery reference only for an observed blocker, preserving native policy and the original task.

Analysis prerequisites depend on the requested evidence. Existing JavaScript/package tools may answer static questions without a native engine; decompilation, firmware, Android, and runtime observations have separate host/provider prerequisites. Acquisition, MCP registration, configuration repair, and runtime execution are deliberate task actions. This module does not supply or preapprove them.

## Source and attribution

The seven skill/reference files preserve the local source bytes. Six reference files match [morluto/rea release source a56f7bb668ab23fec8d33f7af353ac7ed2fe1895](https://github.com/morluto/rea/tree/a56f7bb668ab23fec8d33f7af353ac7ed2fe1895/.agents/skills/reverse-engineer-anything), the gitHead recorded for npm 6.4.0. Relative to its authored entrypoint, the local copy adds `tool_count: 170` metadata and pins its fallback CLI example to `rea-agents@6.4.0` instead of `@latest`. Those edits match the source's documented generation transformations. Neither changes the connected tool inventory or proves runtime compatibility.

The upstream source carries an MIT license, Copyright (c) 2026 morluto. Its exact [LICENSE](payload/.agents/skills/reverse-engineer-anything/LICENSE) accompanies the installed copies. [SOURCE.json](payload/.agents/skills/reverse-engineer-anything/SOURCE.json) records the source commit, file hashes, generation differences, and distinct version namespaces. The skill document version and CLI package version are separate. This source-and-transform match does not establish the local skill's installation origin or byte parity with an npm tarball.

## Preservation and removal

Reruns retain selected modules. A complete independently owned `reverse-engineer-anything` folder is preserved wholly, including its existing references; neither bundled support files nor attribution files are overlaid into it. Selecting the module therefore does not prove that the bundled copy replaced an existing skill. Modified kit-owned files stop installation rather than being overwritten.

Use the receipt from an incremental addition to remove just that addition:

```powershell
& 'C:\Toolkits\engineering-starter-kit\Setup.ps1' -ProjectRoot 'C:\Projects\MyApp' -Rollback 'C:\Projects\MyApp\.engineering-state\setup\<run>\receipt.json'
```

Receipt rollback restores previous configuration and removes files created by that receipt while preserving later edits through a conflict. A first whole-kit receipt covers the whole installation. Setup evidence/environments are retained; empty directories can remain. Package tests establish installation and recovery with synthetic destinations, not REA runtime readiness or analysis truth.
