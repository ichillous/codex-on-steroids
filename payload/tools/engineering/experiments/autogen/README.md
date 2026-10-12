# AutoGen Studio experiments

Use this lab to compare a single analyst with an analyst–reviewer team on the same small evidence packet. Studio is independent of the production engineering coordinator. It has a separate Python environment and local state.

## Start Studio

From the workspace root:

```powershell
.\tools\engineering\experiments\autogen\bootstrap.ps1
.\tools\engineering\experiments\autogen\studio.ps1
```

Open the reported localhost URL (default `http://127.0.0.1:8081`). Ctrl+C stops the foreground process. VS Code also has **Engineering: AutoGen Studio**.

The launcher uses one server process with reload disabled and `.engineering-state/studio` for its database and files. It avoids the upstream CLI's global temporary environment-file write. No model is called by launch or bootstrap. Installing Studio can download its declared dependencies; it does not install browser binaries.

## Choose a compatible model explicitly

This AutoGen version uses `OpenAIChatCompletionClient`. Pick a model supported by that API/client and your account; there is no default model in this lab. The Codex engineering model and reasoning settings remain independent.

Set `OPENAI_API_KEY` in the environment of the Studio process using your normal credential management. Do not put a key in a team export, task, source file, transcript, or checked-in `.env`. Exports omit `api_key`, so the client uses its runtime environment. No key is read by the offline generator.

Generate two importable component JSON files, replacing the model argument with the compatible model you selected:

```powershell
$studioPython = '.\tools\engineering\experiments\autogen\.venv-studio\Scripts\python.exe'
& $studioPython .\tools\engineering\experiments\autogen\generate_teams.py --model '<chosen-compatible-model>' --output .\.engineering-state\studio\teams\comparison-01
```

If the installed client does not recognize that model's metadata, pass `--model-info <path-to-json>`. The JSON must describe its actual capabilities: `vision`, `function_calling`, `json_output`, `structured_output`, and `family`. Supplying metadata does not make an incompatible model/API work. The generator makes no model request and rejects an output directory containing an existing export.

Import the generated component files through Studio's team interface:

- `single-agent.json`: one analyst response.
- `analyst-reviewer.json`: analyst and reviewer in fixed order, at most four agent turns (one revision cycle), with reviewer-only `REVIEW_COMPLETE` termination and a six-message ceiling.

Both teams have no tools or workbench attached. They operate on the supplied evidence text. Studio supports team JSON export/import; menu wording depends on the installed UI. [Studio usage](https://microsoft.github.io/autogen/stable/user-guide/autogenstudio-user-guide/usage.html)

## Run a controlled comparison

1. Use [the synthetic evidence packet](evidence-example.md) in a fresh session for each team.
2. Keep the selected model and packet identical. Save the two outputs and available usage records.
3. Check each answer against the five criteria in the packet.
4. Record which concrete mistake, unsupported claim, or missing limitation the reviewer corrected.
5. Compare added turns/tokens with the improvement. Unknown usage remains unknown.

The packet is synthetic and contains no application payload. For a real engineering comparison, prepare an approved packet with provenance and remove secrets. Studio/provider data flow is separate from the Codex worker data flow.

## Compare result records

`compare_runs.py` accepts AutoGen `TaskResult` JSON files containing `messages` and an optional `stop_reason`. Extract that object from a larger Studio export when necessary; unsupported wrappers are rejected rather than guessed.

```powershell
& $studioPython .\tools\engineering\experiments\autogen\compare_runs.py .\.engineering-state\studio\baseline-result.json .\.engineering-state\studio\team-result.json
```

The report includes file hashes, turns by source, termination reason, measured token totals when complete, and reviewer messages. It does not automatically score correctness or claim the extra agent helped. Compare those results against the packet's acceptance criteria.

## Offline and startup checks

```powershell
& $studioPython -B -m unittest discover -s .\tools\engineering\experiments\autogen -p test_experiments.py -v
& $studioPython .\tools\engineering\experiments\autogen\smoke_studio.py
```

The tests round-trip real AutoGen components, check the absence of serialized keys/tools, and preserve unknown token usage. The smoke check starts Studio on an available localhost port, verifies health/version/HTML responses, then stops its process. It writes `smoke-result.json` and `smoke.log` under `.engineering-state/studio`. These checks make no model request and do not prove a browser interaction or provider connection.

The tested environment is locked in `requirements.lock`; `requirements.txt` states the four intentional AutoGen package pins. Review changes to both when upgrading this experimental environment.
