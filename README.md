# Taylor Elliott — Protocol Generation

**BIOE 234 Final Project · Spring 2026**

## Role

I built the **protocol generation layer** — the component that translates high-level lab instructions (volumes, sample counts, dilution factors) into syntactically valid Opentrons API v2 Python scripts that can be executed on an OT-2 robot.

---

## How it fits into the pipeline

```
User prompt (natural language)
        ↓
    Gemini LLM  ←─── decides task type + extracts parameters
        ↓
[ generator.py ]  ←─── Taylor's component
        ↓
  OT-2 Python script
        ↓
  opentrons_simulate  (Adriann)
        ↓
  heuristic analysis  (Alex)
        ↓
  visualization       (Christian)
```

The generator is the first stage in the pipeline. Without a valid script it produces, nothing downstream can run.

---

## Files

| File | Description |
|------|-------------|
| `generator.py` | Core generation logic — template engine + freeform LLM generation |
| `generate_protocol.py` | MCP tool wrapper (Function Object pattern) |
| `generate_protocol.json` | C9 JSON schema declaring the tool's inputs, outputs, and description |

---

## What was built

### Template-based generation (`generate_ot2_script`)

Three production-ready protocol templates, each producing a complete, runnable OT-2 script:

| Template | Key parameters |
|----------|---------------|
| `serial_dilution` | `num_dilutions`, `dilution_factor`, `initial_volume` |
| `pcr_setup` | `num_samples`, `master_mix_volume`, `sample_volume` |
| `rt_normalization` | `num_samples`, `target_concentration`, `final_volume`, `rt_mm_vol` |

Each template:
- Loads labware onto specific deck slots
- Loads the correct pipette and tip rack
- Generates the full pipetting logic (aspirate, dispense, mix, tip management)
- Embeds a `# PROTOCOL: <name>` header that the visualizer uses downstream

### Defaults system (`_apply_defaults`)

A preprocessing step that fills in missing parameters so users don't need to provide every field. For example, a serial dilution only requires `num_dilutions` and `dilution_factor` — labware slot assignments, traversal direction, and metadata all fill in automatically.

### Pipette name normalisation (`_normalize_pipette`)

Maps human-readable pipette names (`"p300 single"`, `"P300 single-channel"`) to valid Opentrons instrument IDs (`"p300_single_gen2"`), preventing the most common user-facing simulation error.

### Freeform generation (`generate_freeform_script`)

For protocols that don't fit any template, the generator calls the Gemini API directly with a strict system prompt that specifies:
- Exact valid labware names and their well layouts
- Valid pipette names and volume ranges
- Deck slot constraints
- Unicode restrictions (no µ character — causes UTF-8 errors in `opentrons_simulate`)

Includes a self-correction path: if the first attempt fails simulation, the error message is fed back to Gemini for one retry.

### Output sanitisation (`_sanitize_script`, `_extract_python`)

- `_extract_python`: robustly strips markdown code fences and prose preamble from Gemini responses before passing to the simulator
- `_sanitize_script`: replaces non-ASCII characters (µ, smart quotes, em dashes) that cause UTF-8 decode errors in `opentrons_simulate`

---

## Key technical decisions

- **String templates over AST manipulation**: The generated scripts are built by string formatting rather than manipulating a Python AST. This keeps the code readable and the output predictable.
- **`_apply_defaults` before generation**: Separating default-filling from generation logic means the templates themselves are clean and only handle the happy path.
- **Freeform as an extension, not a replacement**: Template protocols are always preferred since they're deterministic. Freeform is only invoked when `task_type == "custom"`.
