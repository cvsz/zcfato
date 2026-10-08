# Camfrog Status 2009 executable: static reverse-engineering notes

## Scope and artifact identity

This note records a static analysis of the supplied legacy utility at [`Camfrog Status 2009.exe`](Camfrog%20Status%202009.exe). The executable was inspected as data and was **not run**.

| Property | Observed value | Evidence |
|---|---|---|
| SHA-256 | `2d96ec1721d28a08ae9aae5827701e581b9ab19161a0b6842898a57ec0f4f820` | `sha256sum` |
| File size | 32,768 bytes | `stat` |
| Format | PE32, 32-bit x86, Windows GUI; three sections (`.text`, `.data`, `.rsrc`) | `file`, `objdump -x` |
| PE timestamp | 2008-12-11 21:33:51 UTC | PE COFF header |
| Version resource | Product label contains `Camfrog Change_Status Inc. 2009`; file/product version `1.00` | `objdump -s -j .rsrc`, wide strings |
| CLR header | Absent | PE data directory |
| Imported runtime | `MSVBVM60.DLL` | PE import table |
| Authenticode certificate table | Absent in this file | PE security directory is empty |

The filename and version resource say 2009, while the PE header timestamp is from 2008 and the inspected copy's filesystem modification time was 2011-07-14. These are distinct metadata fields; none proves when or where this copy was distributed.

## Recovered UI evidence

Embedded VB form/control metadata and strings identify a main form titled **Camfrog Status 2009** with:

- `Start`, `Stop`, and `Exit` controls and corresponding menu items;
- a text field named `Text1` whose embedded default text is `1000`, a `Status Time` label, and `Timer1` / `Timer2` controls;
- an `Online To ..` status group with `Privacy`, `Invisible`, `Busy`, and `Away` options;
- a second form with an About-style title.

The executable contains the message text **“The lowest number is 250”**. A native-code path converts a form value, compares it with the embedded floating-point constant `250.0`, and takes the warning path when the value is lower (`0x00403cf7`–`0x00403da1`). This supports a 250 minimum check, but the exact field/unit, timer behavior, and whether every input path enforces the check were not confirmed in a running copy.

These are embedded resource observations. They do not establish how the controls look or behave on a particular Windows version.

## Camfrog interaction recovered from native code

The PE imports the Visual Basic runtime rather than importing Windows APIs directly. Its embedded declarations include `user32`, `FindWindowA`, `PostMessageA`, and `SendMessageA`. In disassembly, the code path around `0x004049f0` converts the strings `#32770` and `camfrog video chat`, calls the `FindWindowA` declaration, and, when it has a nonzero window handle, posts `WM_COMMAND` (`0x0111`) with command ID `0x0464`. A related path around `0x00404c10` posts `WM_COMMAND` with command ID `0x0467`.

The binary does not include the target application's command map. The meaning of `0x0464` and `0x0467`, and the status selected by either path, therefore remain unknown. The strings and disassembly support local window-message automation; they do not establish that these message IDs work on a particular Camfrog release.

### Relevance to the current Camfrog 8.5 findings

This executable is a separate legacy utility, not `Camfrog Video Chat.exe` 8.5.0.51219. Its `#32770` / title lookup and command IDs are not UI Automation selectors and must not be copied into the 8.5 configuration. The current-version selectors and room-control findings remain scoped to the evidence in [CAMFROG-8.5-FINDINGS.md](CAMFROG-8.5-FINDINGS.md).

## Evidence states and limits

- **`VERIFIED` — static artifact and call-path facts:** supported directly by the inspected PE headers, imports, resources, strings, and disassembly. The native code constructs the observed window lookup and message calls.
- **`PARTIALLY VERIFIED` — status-automation behavior:** the UI and code support that intent, but the command IDs' meanings and the target application's response are unknown.
- **`UNVERIFIED` — runtime effects:** this executable was not run, and no matching legacy Camfrog installation was examined for behavior confirmation. Status changes, timer cadence, compatibility, and side effects are not established here.

This is a bounded static reverse-engineering note, not recovered VB source. The PE has no symbols, and the available analysis used `file`, `strings`, and GNU `objdump`; event-procedure names and parts of the compiled VB6 control flow remain inferred or unresolved. No network protocol, licensing mechanism, or Camfrog internals were analyzed.

## Reproduction commands

Run these read-only commands from the repository root to confirm the artifact identity and repeat the inspected views:

```sh
sha256sum 'docs/Camfrog Status 2009.exe'
file 'docs/Camfrog Status 2009.exe'
objdump -x 'docs/Camfrog Status 2009.exe'
strings -a -n 3 'docs/Camfrog Status 2009.exe'
strings -el -n 3 'docs/Camfrog Status 2009.exe'
objdump -D -Mintel -j .text --start-address=0x403c60 --stop-address=0x403da6 'docs/Camfrog Status 2009.exe'
objdump -D -Mintel -j .text --start-address=0x4049f0 --stop-address=0x404d30 'docs/Camfrog Status 2009.exe'
```

The first disassembly range includes the 250 comparison and warning path; the second includes both observed command-message paths. Do not use these results as a substitute for version-matched testing before changing current Camfrog selectors or behavior.
