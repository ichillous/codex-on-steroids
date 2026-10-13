# Claudely module

Apply selected, officially documented Claude Code working practices in Codex: establish an observable result, investigate and plan in proportion to the task, choose meaningful completion checks, use bounded delegation and review when useful, and retain concise continuation notes for long work. The skill includes its source-backed rationale and Codex compatibility limits. The research supports these as workflow recommendations; a measured productivity improvement has not been established.

Select `-Modules claudely` in the starter kit's `Setup.ps1`. The entire skill folder is installed in the destination's `.agents/skills/claudely/`. For configuration and skills only, without model calls, downloads or environment bootstrap:

```powershell
& 'C:\Toolkits\engineering-starter-kit\Setup.ps1' -ProjectRoot 'C:\Projects\MyApp' -Modules claudely -Static -SkipDependencies
```

Open a fresh Codex session in the destination and use `$claudely`, for example:

```text
Use $claudely to fix the reported defect. Keep the change scoped, choose a
meaningful check, and report what the evidence establishes and what remains open.
```

Start with [SKILL.md](payload/.agents/skills/claudely/SKILL.md); read its references only when relevant. The skill has no additional executable dependency. It works with the capabilities actually available in the destination and preserves existing instructions, permissions, models, Git state, and task authorization. This installation does not enable native hooks, register new agent roles, install Claude, or start a durable runner. Native skills and delegation remain subject to the destination client's discovery and runtime controls.

Reruns retain the module selection. A complete independently owned `claudely` skill is preserved as a whole instead of receiving bundled supporting files; selecting the module does not prove that the packaged version replaced it. Unmodified kit-owned files can be updated, while local edits cause an installation conflict and remain intact.

The installer saves a configuration receipt under `.engineering-state/setup/<run>/receipt.json`. To remove the module added to an existing kit installation, use the receipt from that incremental addition:

```powershell
& 'C:\Toolkits\engineering-starter-kit\Setup.ps1' -ProjectRoot 'C:\Projects\MyApp' -Rollback 'C:\Projects\MyApp\.engineering-state\setup\<run>\receipt.json'
```

Rollback restores the prior configuration and removes files newly installed by that receipt; later edits cause a preservation conflict. A receipt from the first complete toolkit installation covers the whole installation. Setup evidence and environments are retained, and empty skill directories may remain. There is no separate module-uninstall switch. Review the actual receipt before choosing it.
