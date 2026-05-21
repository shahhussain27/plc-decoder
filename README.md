# PLC Decoder Pro

## Industrial-Grade PLC Binary/Hex Data Decoder

> Decode LiraNET / Mitsubishi FX5U PLC hex data into clean Excel reports with a professional dark-mode desktop GUI.

---

## Features

| Feature | Description |
|---|---|
| 🔍 Auto-detection | Detects packet boundaries, timestamps, and field patterns automatically |
| 📋 Live preview | Searchable, sortable decoded records table |
| 🔢 Hex viewer | Paged hex dump with offset ruler and ASCII sidebar |
| 📊 Statistics | Visual parse metrics with success rate gauge |
| 💾 Excel export | 5-sheet workbook: Records, Registers, Stats, Errors, Raw Hex |
| ⚙️ Config system | JSON-based PLC format templates (editable in-app) |
| 🔄 Batch mode | Process entire folders of data files |
| 🖥️ CLI mode | Headless parsing + export via command line |

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Launch GUI

```bash
python main.py
```

### 3. CLI mode

```bash
# Parse and export to Excel
python main.py --cli Python.txt --output decoded.xlsx

# Auto-analyze structure (unknown format)
python main.py --analyze Python.txt

# Use custom config template
python main.py --cli data.txt --config configs/plc_templates/liranet_fx5u.json
```

---

## Project Structure

```
PLC-Decoder/
├── main.py                          # Entry point (GUI + CLI)
├── requirements.txt
├── README.md
│
├── parser/                          # Core parsing engine
│   ├── base_parser.py               # Abstract base + ParsedRecord dataclass
│   ├── hex_parser.py                # Main HexParser implementation
│   ├── packet_detector.py           # Marker/fixed-length/timestamp packet finder
│   └── field_extractor.py           # Config-driven field extraction
│
├── analyzer/                        # Reverse engineering tools
│   ├── pattern_detector.py          # Autocorrelation pattern finder
│   ├── timestamp_detector.py        # Heuristic timestamp locator
│   ├── structure_analyzer.py        # Orchestrates all analyzers
│   └── crc_validator.py             # CRC-16/Modbus, CCITT, XOR, byte-sum
│
├── exporters/                       # Output generators
│   ├── excel_exporter.py            # 5-sheet formatted Excel workbook
│   └── csv_exporter.py              # Simple CSV export
│
├── ui/                              # PySide6 GUI components
│   ├── main_window.py               # Root window + workflow orchestration
│   ├── file_panel.py                # Drag-and-drop file selector
│   ├── config_panel.py              # Quick settings + JSON editor
│   ├── preview_table.py             # Filterable decoded records table
│   ├── hex_viewer.py                # Paged hex dump viewer
│   ├── stats_panel.py               # Parse metrics cards
│   └── log_panel.py                 # Error log viewer
│
├── configs/                         # Configuration system
│   ├── config_loader.py             # JSON config loader + validator
│   └── plc_templates/
│       ├── liranet_fx5u.json        # LiraNET/Mitsubishi FX5U (default)
│       └── modbus_template.json     # Generic Modbus RTU
│
└── utils/                           # Shared utilities
    ├── logger.py                    # Singleton logger (file + console + GUI)
    ├── file_reader.py               # Multi-format file reader (txt/csv/bin)
    └── helpers.py                   # Hex/binary utility functions
```

---

## Data Format: LiraNET Protocol (Mitsubishi FX5U)

Based on the reference Excel file, each packet contains:

| Word Offset | Bytes | Field | Example | Decimal |
|---|---|---|---|---|
| 0 | 0–1 | Sub-Client ID | `03E9` | 1001 |
| 1 | 2–3 | Year | `07E8` | 2024 |
| 2 | 4–5 | Month | `000B` | 11 |
| 3 | 6–7 | Day | `000B` | 11 |
| 4 | 8–9 | Hour | `000A` | 10 |
| 5 | 10–11 | Minute | `0037` | 55 |
| 6 | 12–13 | Second | `0011` | 17 |
| 7 | 14–15 | Millisecond | `001E` | 30 |
| 8–19 | 16–39 | Registers D1600–D1710 | `0000` | 0 |

**Note:** FX5U uses Little-Endian byte order internally. The sub-client ID `03E9` identifies packet start.

---

## Config Templates

### LiraNET FX5U (default)

`configs/plc_templates/liranet_fx5u.json`

- Packet size: 40 bytes
- Start marker: `03E9`
- 20 fields: Sub-Client ID + 7 timestamp + 12 data registers

### Modbus RTU (generic)

`configs/plc_templates/modbus_template.json`

- Packet size: 20 bytes
- Fixed-length detection
- CRC-16/Modbus validation enabled

### Creating Custom Templates

```json
{
  "format_name": "my_plc",
  "protocol": "Custom",
  "endianness": "big",
  "packet_definition": {
    "packet_size_bytes": 32,
    "start_markers": ["AABB"]
  },
  "timestamp": { "word_offset": 0 },
  "fields": [
    { "name": "device_id", "word_offset": 0, "size_words": 1, 
      "byteorder": "big", "data_type": "uint16", "register": "D100" },
    { "name": "year", "word_offset": 1, "size_words": 1, 
      "byteorder": "big", "data_type": "uint16" }
  ],
  "parser_options": { "skip_padding": true }
}
```

---

## Excel Output Sheets

| Sheet | Contents |
|---|---|
| **Records** | Main decoded table — one row per packet, all fields |
| **Registers** | Pivoted view — each register as a column |
| **Packet Stats** | Parse summary (total/valid/invalid, timestamps, errors) |
| **Error Log** | Corrupt or invalid packets with raw hex |
| **Raw Hex** | Per-record raw hex dump |

---

## Requirements

- Python 3.11+
- PySide6 ≥ 6.6
- pandas ≥ 2.0
- openpyxl ≥ 3.1
- numpy ≥ 1.24

---

## License

© 2024 PLC Decoder Pro. Production build.
