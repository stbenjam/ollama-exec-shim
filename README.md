# Ollama Exec Shim

> [!WARNING]
> **This is probably a really stupid thing to do.** This tool is essentially **"Backdoor-as-a-Service"** by design. It turns unauthenticated (by default) web requests into shell commands on your machine. **Do not ever expose this to the public internet.** Use at your own risk, preferably behind a very sturdy firewall, on a machine you don't care about, while wearing a tinfoil hat.

A lightweight FastAPI-based shim that mimics the Ollama API but executes local scripts instead of LLMs. This allows any tool that supports Ollama (like OpenClaw, the Ollama CLI, or other UI wrappers) to be used as a task scheduler or script runner.

## Features

- **Ollama API Compatible:** Implements `tags`, `show`, `pull`, `chat`, and `generate` endpoints.
- **Streaming Support:** Real-time stdout/stderr streaming in the standard Ollama NDJSON format.
- **Model "exec":** Specifically handles the `exec` model to run any executable file.
- **CLI Ready:** Works seamlessly with the official `ollama` CLI.
- **Robust Path Extraction:** Supports extracting paths wrapped in `EXEC[/path/to/script]`.
- **Optional Authentication:** Support for Bearer token authentication.
- **Directory Allowlist:** Restrict execution to specific approved directories.

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

### 2. Running in a Container

You can run the shim in a container and bind-mount your scripts or workspaces. This is especially useful for integration with tools like OpenClaw.

#### Example: OpenClaw Workspace Integration
The following command runs the shim, mounts the OpenClaw workspace, and restricts execution to that directory:

```bash
docker run -d \
  --name ollama-exec-shim \
  -p 11434:11434 \
  -v /home/user/.openclaw/workspaces:/workspaces:ro \
  -e OLLAMA_EXEC_ALLOWLIST="/workspaces" \
  -e OLLAMA_EXEC_TOKEN="your-secure-token" \
  ghcr.io/stbenjam/ollama-exec-shim:main
```

### 3. Security Configuration (Optional)

#### API Token
To protect the shim with an API token, set the `OLLAMA_EXEC_TOKEN` environment variable:
```bash
export OLLAMA_EXEC_TOKEN="your-secure-token"
```

#### Directory Allowlist
To restrict execution to specific directories, set the `OLLAMA_EXEC_ALLOWLIST` environment variable (colon-separated):
```bash
export OLLAMA_EXEC_ALLOWLIST="/home/user/scripts:/opt/tools/bin"
```
The shim uses `os.path.realpath` to resolve all paths, preventing bypasses via symbolic links or relative path traversals.

### 4. Run a Script via Ollama CLI
Once the shim is running, you can use the official `ollama` command to execute any script:

```bash
ollama run exec "/path/to/your/script.sh"
```

### 5. Usage with OpenClaw

To use `ollama-exec-shim` as a task scheduler in OpenClaw:

1.  **Provider Setup:** Add a new Ollama provider pointing to `http://localhost:11434`.
2.  **Model Selection:** Select the `exec` model for your task or cron job.
3.  **Job Configuration:**
    *   **Context:** You **must** select **"Light context"** (or minimal context) to ensure the message sent to the shim is clean and focused.
    *   **Command Syntax:** Use the `EXEC[...]` syntax in your prompt to clearly define the script to run, especially if there is other surrounding text:
        ```text
        EXEC[/workspaces/my-project/scripts/daily_report.py]
        ```

## License

MIT
