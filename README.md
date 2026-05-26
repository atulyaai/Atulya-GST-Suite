# Atulya GST Suite

Free GST preparation, reconciliation, e-invoice and e-way bill workflow toolkit for India.

## Features

- GSTR-1, GSTR-3B generation from Excel/ERP exports
- Auto-reconciliation (2A/2B with purchase register)
- E-invoice JSON generation & QR code
- E-way bill generation
- GST return filing helper
- Due date tracker & reminders

## Quick Start

```bash
pip install atulya-gst-suite
atulya-gst reconcile --purchases purchases.xlsx --gstr2b gstr2b.json
atulya-gst gstr1 --sales sales.xlsx --output gstr1.json
```

## Commands

| Command | Description |
|---------|-------------|
| `reconcile` | Match 2A/2B with purchase register |
| `gstr1` | Generate GSTR-1 JSON |
| `gstr3b` | Generate GSTR-3B summary |
| `einvoice` | Generate e-invoice JSON with IRN |
| `ewaybill` | Generate e-way bill |
| `track` | Show upcoming due dates |

## License

MIT
