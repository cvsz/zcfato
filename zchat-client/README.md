# ZChat Agent Chat Client

`zchat-client` is a Windows desktop client for the internal chat endpoints in `control-server`. It uses an agent token and the account currently assigned to that agent. It does not automate Camfrog, connect to Camfrog's network, or implement a Camfrog-compatible protocol.

## Run from source

Use 64-bit Python 3.12 on Windows. Install the client dependencies and launch the UI:

```powershell
python -m pip install -r zchat-client/requirements.txt
python zchat-client/main.py
```

The launcher adds the local `control-server/src` package to the import path. The server must be reachable and expose the agent chat routes listed in [`control-server/README.md`](../control-server/README.md).

## Build the Windows executable

Run the repository build first to create `.venv`, then build the standalone executable:

```cmd
build.bat
zchat-client\build.bat
```

Or use `full-build.bat` to build the repository applications and this client together. The output is `dist\zchat-client\zchat-client.exe`.

## Connect

1. Create or assign an agent in the control server. The agent token is shown only when it is issued or rotated.
2. Start the client, enter the HTTPS URL of your deployed control server, and enter the one-time-issued agent token.
3. The client reads the current account assignment without updating command-agent presence.
4. Send messages with the **Send** button or `Ctrl+Enter`.

HTTP is accepted only for loopback development URLs. The token is masked and kept in process memory; the client does not save credentials, fetch server-side message history, or persist conversation history. Closing the application clears the visible conversation. Messages that have not reached the server before closing are lost. A successful send means the control server accepted the message; it does not confirm that an operator read it. Incoming messages are acknowledged after the UI displays them; if the client closes before acknowledgement, the server may deliver them again.

The agent token is a credential. Issue it through the control server and do not place it in command-line arguments, source files, screenshots, or logs. Revoke or rotate it if exposed.

The client accepts up to 100 unsent messages per session and keeps a bounded in-memory window of message IDs for duplicate suppression.

## Protocol and reverse-engineering boundary

The transport shares the documented ZChat control-server agent protocol: read-only account assignment lookup, idempotent agent-to-operator sends, and leased operator-to-agent messages with acknowledgement. It deliberately does not update command-agent presence, use command polling, or execute Camfrog provider operations.

REA static inspection of the supplied Camfrog executable identified a native PE binary without managed/.NET metadata. No application source or managed assemblies were available to generate a client from, and native decompilation providers were not configured. The client therefore targets the control-server protocol, not Camfrog's proprietary protocol.
