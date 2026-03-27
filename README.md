# Ollama Exec Shim

A lightweight FastAPI-based shim that mimics the Ollama API but executes local scripts instead of LLMs. This allows any tool that supports Ollama (like OpenClaw, the Ollama CLI, or other UI wrappers) to be used as a task scheduler or script runner.

## Features

- **Ollama API Compatible:** Implements `tags`, `show`, `pull`, `chat`, and `generate` endpoints.
- **Streaming Support:** Real-time stdout/stderr streaming in the standard Ollama NDJSON format.
- **Model "exec":** Specifically handles the `exec` model to run any executable file.
- **CLI Ready:** Works seamlessly with the official `ollama` CLI.

## Installation

```bash
pip install .
```

Or for development:

```bash
pip install -e .
```

## Usage

### 1. Start the Shim
By default, the shim listens on `http://localhost:11434` (the default Ollama port).

```bash
ollama-exec-shim
```

### 2. Run a Script via Ollama CLI
Once the shim is running, you can use the official `ollama` command to execute any script:

```bash
ollama run exec "/path/to/your/script.sh"
```

### 3. Use with OpenClaw or other tools
Simply point your tool's Ollama provider to `http://localhost:11434`. The `exec` model will be available for selection.

## Security Note

This tool is designed to execute local scripts. **Do not expose it to the public internet.** It should only be used on `localhost` or in a secured, private network environment. It only executes files that already exist and have the executable bit set.

## License

MIT
