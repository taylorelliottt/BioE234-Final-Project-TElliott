"""
OT-2 protocol generator (Taylor Elliott).

Takes a high-level parameters dict and returns a complete, syntactically
valid Opentrons API v2 Python script as a string.
"""


_PIPETTE_ALIASES = {
    "p20 single":    "p20_single_gen2",
    "p20single":     "p20_single_gen2",
    "p20_single":    "p20_single_gen2",
    "p50 single":    "p50_single",
    "p50single":     "p50_single",
    "p300 single":   "p300_single_gen2",
    "p300single":    "p300_single_gen2",
    "p300_single":   "p300_single_gen2",
    "p1000 single":  "p1000_single_gen2",
    "p1000single":   "p1000_single_gen2",
    "p1000_single":  "p1000_single_gen2",
    "p20 multi":     "p20_multi_gen2",
    "p20multi":      "p20_multi_gen2",
    "p20_multi":     "p20_multi_gen2",
    "p300 multi":    "p300_multi_gen2",
    "p300multi":     "p300_multi_gen2",
    "p300_multi":    "p300_multi_gen2",
}


def _normalize_pipette(name: str) -> str:
    """Map human-readable pipette names to valid Opentrons instrument IDs."""
    return _PIPETTE_ALIASES.get(name.lower().strip(), name)


def _apply_defaults(parameters: dict) -> dict:
    """Fill in labware_map, metadata, and traversal defaults when not supplied."""
    p = dict(parameters)
    task_type = p.get("task_type")

    p.setdefault("metadata", {})
    p["metadata"].setdefault("protocolName", task_type.replace("_", " ").title() if task_type else "BioAutomation Protocol")
    p["metadata"].setdefault("author", "BioE234 Team")
    p.setdefault("pipette_type", "p300_single_gen2")
    p["pipette_type"] = _normalize_pipette(p["pipette_type"])
    p.setdefault("mount", "left")
    p.setdefault("start_well", "A1")
    p.setdefault("traverse_direction", "row")

    if not p.get("labware_map"):
        if task_type == "serial_dilution":
            p["labware_map"] = [
                {"name": "tiprack",     "type": "opentrons_96_tiprack_300ul",   "slot": "1"},
                {"name": "dest_plate",  "type": "nest_96_wellplate_200ul_flat", "slot": "2"},
                {"name": "diluent_res", "type": "nest_96_wellplate_200ul_flat", "slot": "3"},
            ]
            p.setdefault("num_wells", p.get("num_dilutions", 8))
            p.setdefault("dilution_factor", 2)
            p.setdefault("total_well_volume", p.get("initial_volume", 200))
        elif task_type == "pcr_setup":
            p["labware_map"] = [
                {"name": "tiprack",      "type": "opentrons_96_tiprack_300ul",   "slot": "1"},
                {"name": "dest_plate",   "type": "nest_96_wellplate_200ul_flat", "slot": "4"},
                {"name": "mm_source",    "type": "nest_96_wellplate_200ul_flat", "slot": "2"},
                {"name": "sample_plate", "type": "nest_96_wellplate_200ul_flat", "slot": "3"},
            ]
            p.setdefault("num_wells", p.get("num_samples", 8))
            p.setdefault("mm_well", "A1")
            p.setdefault("mm_volume", p.get("master_mix_volume", 18.0))
            p.setdefault("template_volume", p.get("sample_volume", 2.0))
            p.setdefault("traverse_direction", "column")
        elif task_type == "rt_normalization":
            p["labware_map"] = [
                {"name": "tiprack",      "type": "opentrons_96_tiprack_300ul",                            "slot": "1"},
                {"name": "dest_plate",   "type": "nest_96_wellplate_200ul_flat",                          "slot": "2"},
                {"name": "rna_source",   "type": "nest_96_wellplate_200ul_flat",                          "slot": "3"},
                {"name": "water_source", "type": "nest_1_reservoir_195ml",                                "slot": "4"},
                {"name": "rt_mm_source", "type": "opentrons_24_tuberack_eppendorf_1.5ml_safelock_snapcap", "slot": "5"},
            ]
            concs = p.get("sample_concentrations", [])
            p.setdefault("num_wells", len(concs) if concs else p.get("num_samples", 8))
            p.setdefault("target_ng_ul", p.get("target_concentration", 50.0))
            p.setdefault("target_rna_vol", p.get("final_volume", 15.0))
            p.setdefault("rt_mm_vol", 5.0)
            if not concs:
                n = p["num_wells"]
                p["sample_concentrations"] = [100.0] * n
        # Unknown / custom task_type — caller should use generate_freeform_script instead
        pass

    return p


def generate_ot2_script(parameters: dict) -> str:
    """
    Takes high-level lab instructions and returns a valid Opentrons Python script.
    Supports dynamic labware maps and flexible traversal directions.
    """
    parameters = _apply_defaults(parameters)
    meta = parameters.get("metadata", {})
    task_type = parameters.get("task_type")
    pipette_type = parameters.get("pipette_type", "p300_single_gen2")
    mount = parameters.get("mount", "left")

    num_wells = parameters.get("num_wells", 8)
    start_well = parameters.get("start_well", "A1")
    traverse_direction = parameters.get("traverse_direction", "column")

    protocol_name = meta.get("protocolName", "BioAutomation Protocol")
    script_content = f"""# PROTOCOL: {protocol_name}
from opentrons import protocol_api

metadata = {{
    'protocolName': '{meta.get("protocolName", "BioAutomation Protocol")}',
    'author': '{meta.get("author", "BioE234 Team")}',
    'apiLevel': '2.15'
}}

def run(protocol: protocol_api.ProtocolContext):
    # --- Hardware Setup ---
"""

    for item in parameters.get("labware_map", []):
        script_content += f"    {item['name']} = protocol.load_labware('{item['type']}', '{item['slot']}')\n"

    script_content += f"    pipette = protocol.load_instrument('{pipette_type}', '{mount}', tip_racks=[tiprack])\n\n"

    script_content += f"""    # --- Define Target Wells ---
    if '{traverse_direction}' == 'row':
        row_letter = '{start_well}'[0]
        row_wells = dest_plate.rows_by_name()[row_letter]
        start_idx = [w.well_name for w in row_wells].index('{start_well}')
        targets = row_wells[start_idx : start_idx + {num_wells}]
    else:
        all_wells = dest_plate.wells()
        start_idx = [w.well_name for w in all_wells].index('{start_well}')
        targets = all_wells[start_idx : start_idx + {num_wells}]

"""

    if task_type == "serial_dilution":
        total_vol = parameters.get("total_well_volume", 200)
        trans_vol = total_vol / parameters.get("dilution_factor", 2)
        buff_vol = total_vol - trans_vol

        script_content += f"""    # --- Serial Dilution Logic ---
    # Fill with buffer (1 tip)
    pipette.pick_up_tip()
    for well in targets[1:]:
        pipette.transfer({buff_vol}, diluent_res.wells()[0], well, new_tip='never')
    pipette.drop_tip()

    # Dilution chain (1 tip)
    pipette.pick_up_tip()
    for i in range(len(targets) - 1):
        pipette.transfer({trans_vol}, targets[i], targets[i+1], new_tip='never')
        pipette.mix(3, {trans_vol}, targets[i+1])
    pipette.drop_tip()
"""

    elif task_type == "pcr_setup":
        script_content += f"""    # --- PCR Setup Logic ---
    # Distribute Master Mix (one tip for all dispenses)
    pipette.pick_up_tip()
    for well in targets:
        pipette.transfer({parameters.get("mm_volume", 18.0)}, mm_source.wells_by_name()['{parameters.get("mm_well", "A1")}'], well, new_tip='never')
    pipette.drop_tip()

    # Add Templates (new tip per well to prevent contamination)
    for i, well in enumerate(targets):
        pipette.pick_up_tip()
        pipette.transfer({parameters.get("template_volume", 2.0)}, sample_plate.wells()[i], well, new_tip='never')
        pipette.drop_tip()
"""

    elif task_type == "rt_normalization":
        target_conc = parameters.get("target_ng_ul", 50.0)
        target_vol = parameters.get("target_rna_vol", 15.0)
        rt_vol = parameters.get("rt_mm_vol", 5.0)
        concs = parameters.get("sample_concentrations", [])

        script_content += f"""    # --- RT Normalization Logic ---
    target_conc = {target_conc}
    target_vol = {target_vol}
    concentrations = {concs}

    rna_vols = [(target_conc * target_vol) / c for c in concentrations]
    water_vols = [target_vol - rv for rv in rna_vols]

    # 1. Distribute Water (one tip for all dispenses)
    pipette.pick_up_tip()
    for i, well in enumerate(targets[:len(concentrations)]):
        if water_vols[i] > 0:
            pipette.transfer(water_vols[i], water_source.wells()[0], well, new_tip='never')
    pipette.drop_tip()

    # 2. Transfer RNA (change tip for every sample)
    for i, well in enumerate(targets[:len(concentrations)]):
        pipette.pick_up_tip()
        pipette.transfer(rna_vols[i], rna_source.wells()[i], well, new_tip='never')
        pipette.mix(3, target_vol / 2, well)
        pipette.drop_tip()

    # 3. Distribute RT Master Mix
    pipette.pick_up_tip()
    for well in targets[:len(concentrations)]:
        pipette.transfer({rt_vol}, rt_mm_source.wells()[0], well, new_tip='never')
    pipette.drop_tip()
"""

    else:
        raise ValueError(
            f"Unknown task_type '{task_type}'. "
            "Use generate_freeform_script() for custom protocols."
        )

    return script_content


_FREEFORM_SYSTEM = """\
You are an expert Opentrons OT-2 Python programmer. Write complete, valid Opentrons API v2 Python scripts.

STRICT RULES — violating any causes a simulation error:
1. Return ONLY Python code. No markdown, no code fences (```), no explanations.
   NEVER use the µ character anywhere — write 'uL' not 'µL'. Non-ASCII characters cause a UTF-8 decode error.
2. First line must be: # PROTOCOL: <name>
3. Include a module-level metadata dict with apiLevel '2.15'.
4. Define exactly: def run(protocol: protocol_api.ProtocolContext):
5. Use ONLY these labware names (exact strings) and respect their well layouts:
     opentrons_96_tiprack_20ul          — 96 wells, 8 rows (A-H) × 12 cols (1-12)
     opentrons_96_tiprack_300ul         — 96 wells, 8 rows (A-H) × 12 cols (1-12)
     opentrons_96_tiprack_1000ul        — 96 wells, 8 rows (A-H) × 12 cols (1-12)
     nest_96_wellplate_200ul_flat       — 96 wells, 8 rows (A-H) × 12 cols (1-12)
     nest_96_wellplate_100ul_pcr_full_skirt — 96 wells, 8 rows (A-H) × 12 cols (1-12)
     nest_12_reservoir_15ml             — 12 wells, 1 row, cols A1–A12 only
     nest_1_reservoir_195ml             — 1 well, A1 only
     opentrons_24_tuberack_eppendorf_1.5ml_safelock_snapcap — 24 wells, 4 rows (A-D) × 6 cols (1-6), positions A1–D6 ONLY
     opentrons_24_tuberack_nest_2ml_snapcap                 — 24 wells, 4 rows (A-D) × 6 cols (1-6), positions A1–D6 ONLY
6. Use ONLY these pipette names (exact strings):
     p20_single_gen2   (2–20 µL)
     p300_single_gen2  (20–300 µL)
     p1000_single_gen2 (100–1000 µL)
     p20_multi_gen2    (2–20 µL, 8-channel)
     p300_multi_gen2   (20–300 µL, 8-channel)
7. Deck slots are strings '1' through '11'.
8. Always pass tip_racks=[...] when loading a pipette.
9. Choose pipette by volume: ≤20 µL → p20, 21–300 µL → p300, >300 µL → p1000.
10. Never exceed 300 µL per transfer with p300; split into multiple aspirate/dispense if needed.
11. CRITICAL — tube rack well access: a 24-tube rack has only 4 rows × 6 columns.
    Valid positions: A1,A2,A3,A4,A5,A6, B1–B6, C1–C6, D1–D6. A7 through A12 do NOT exist.
    If you need 12 individual collection tubes (one per plate column), use nest_12_reservoir_15ml (A1–A12) instead.
12. Use labware.columns()[n] (0-indexed) or labware.rows()[n] to select entire columns/rows.
    Use labware.wells_by_name()['A1'] or labware['A1'] for individual wells.

EXAMPLE STRUCTURE:
# PROTOCOL: Example Protocol
from opentrons import protocol_api

metadata = {
    'protocolName': 'Example Protocol',
    'author': 'BioE234 Team',
    'apiLevel': '2.15'
}

def run(protocol: protocol_api.ProtocolContext):
    tiprack = protocol.load_labware('opentrons_96_tiprack_300ul', '1')
    plate   = protocol.load_labware('nest_96_wellplate_200ul_flat', '2')
    pipette = protocol.load_instrument('p300_single_gen2', 'left', tip_racks=[tiprack])

    for well in plate.wells()[:8]:
        pipette.pick_up_tip()
        pipette.aspirate(50, plate['A1'])
        pipette.dispense(50, well)
        pipette.drop_tip()
"""


def _extract_python(text: str) -> str:
    """
    Pull Python source out of a Gemini response that may contain prose, markdown
    fences, or both.  Priority order:
      1. Content inside ```python ... ``` fences
      2. Content inside any ``` ... ``` fences
      3. Everything from the first 'from opentrons' / '# PROTOCOL:' line onward
      4. Raw text as a last resort
    """
    import re
    text = text.strip()

    # 1 & 2 — fenced code block (with or without language tag)
    m = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()

    # 3 — find where the actual Python starts (first recognisable line)
    lines = text.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("# PROTOCOL:") or stripped.startswith("from opentrons"):
            return "\n".join(lines[i:]).strip()

    # 4 — give up and return as-is; simulation will surface the real error
    return text


def _sanitize_script(script: str) -> str:
    """Replace non-ASCII characters that break opentrons_simulate's UTF-8 reader."""
    return (
        script
        .replace('µ', 'u')   # µ (micro sign, Latin-1 0xb5)
        .replace('μ', 'u')   # μ (Greek small mu)
        .replace('’', "'")   # right single quote
        .replace('‘', "'")   # left single quote
        .replace('“', '"')   # left double quote
        .replace('”', '"')   # right double quote
        .replace('–', '-')   # en dash
        .replace('—', '-')   # em dash
    )


def generate_freeform_script(
    description: str,
    metadata: dict = None,
    previous_script: str = None,
    error_message: str = None,
) -> str:
    """
    Use Gemini to write an arbitrary OT-2 protocol from a natural-language description.
    Supply previous_script + error_message on retry for self-correction.
    """
    import os
    try:
        from google import genai
        from google.genai import types as gtypes
    except ImportError:
        raise ImportError("google-genai not installed. Run: pip install google-genai")

    api_key = os.environ.get("GEMINI_API_KEY", "")
    client = genai.Client(api_key=api_key)

    meta = metadata or {}
    protocol_name = meta.get("protocolName", "Custom Protocol")
    author = meta.get("author", "BioE234 Team")

    if previous_script and error_message:
        user_msg = (
            f"The following OT-2 script produced this simulation error:\n\n"
            f"ERROR:\n{error_message}\n\n"
            f"SCRIPT THAT FAILED:\n{previous_script}\n\n"
            f"Fix the error. Original protocol description:\n{description}\n\n"
            f"Return only the corrected Python script."
        )
    else:
        user_msg = (
            f"Write an OT-2 protocol script for the following:\n\n"
            f"{description}\n\n"
            f"Use protocolName: '{protocol_name}' and author: '{author}'."
        )

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[gtypes.Content(role="user", parts=[gtypes.Part(text=user_msg)])],
        config=gtypes.GenerateContentConfig(
            system_instruction=_FREEFORM_SYSTEM,
            temperature=0.1,
        ),
    )

    return _sanitize_script(_extract_python(response.text))
