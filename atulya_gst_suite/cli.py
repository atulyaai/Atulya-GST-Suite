import json
import sys
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from atulya_gst_suite import __version__
from atulya_gst_suite.core import (
    reconcile_gstr2a,
    reconcile_gstr2b,
    generate_reconciliation_summary,
    generate_gstr1_json,
    validate_gstr1_json,
    generate_gstr1_summary,
    generate_gstr3b,
    validate_gstr3b,
    generate_einvoice_json,
    generate_einvoice_qr,
    generate_ewaybill_json,
    get_upcoming_due_dates,
    pretty_due_dates,
)
from atulya_gst_suite.utils import (
    validate_gstin,
    format_inr,
    lookup_hsn,
    lookup_sac,
    split_tax,
    format_gstin,
)


console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="Atulya GST Suite")
def main():
    pass


@main.group()
def reconcile():
    """Reconciliation commands for GSTR-2A and GSTR-2B."""


@reconcile.command("gstr2a")
@click.option("--purchase-file", "-p", required=True, help="Path to purchase register JSON file")
@click.option("--gstr2a-file", "-g", required=True, help="Path to GSTR-2A JSON file")
@click.option("--output", "-o", help="Output file for reconciliation report")
def reconcile_gstr2a_cmd(purchase_file, gstr2a_file, output):
    """Reconcile purchase register with GSTR-2A."""
    try:
        with open(purchase_file, "r") as f:
            purchase_data = json.load(f)
        with open(gstr2a_file, "r") as f:
            gstr2a_data = json.load(f)
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] File not found: {e.filename}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        console.print(f"[red]Error:[/red] Invalid JSON: {e}")
        sys.exit(1)
    result = reconcile_gstr2a(purchase_data, gstr2a_data)
    summary = generate_reconciliation_summary(result)
    console.print(Panel(summary, title="GSTR-2A Reconciliation"))
    if output:
        try:
            with open(output, "w") as f:
                json.dump(result, f, indent=2, default=str)
            console.print(f"[green]Report saved to {output}[/green]")
        except IOError as e:
            console.print(f"[red]Error writing output:[/red] {e}")
            sys.exit(1)


@reconcile.command("gstr2b")
@click.option("--purchase-file", "-p", required=True, help="Path to purchase register JSON file")
@click.option("--gstr2b-file", "-g", required=True, help="Path to GSTR-2B JSON file")
@click.option("--output", "-o", help="Output file for reconciliation report")
def reconcile_gstr2b_cmd(purchase_file, gstr2b_file, output):
    """Reconcile purchase register with GSTR-2B."""
    try:
        with open(purchase_file, "r") as f:
            purchase_data = json.load(f)
        with open(gstr2b_file, "r") as f:
            gstr2b_data = json.load(f)
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] File not found: {e.filename}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        console.print(f"[red]Error:[/red] Invalid JSON: {e}")
        sys.exit(1)
    result = reconcile_gstr2b(purchase_data, gstr2b_data)
    summary = generate_reconciliation_summary(result)
    console.print(Panel(summary, title="GSTR-2B Reconciliation"))
    if output:
        try:
            with open(output, "w") as f:
                json.dump(result, f, indent=2, default=str)
            console.print(f"[green]Report saved to {output}[/green]")
        except IOError as e:
            console.print(f"[red]Error writing output:[/red] {e}")
            sys.exit(1)


@reconcile.command("summary")
@click.option("--reconciliation-file", "-r", required=True, help="Path to reconciliation result JSON")
def reconciliation_summary_cmd(reconciliation_file):
    """Show reconciliation summary report."""
    try:
        with open(reconciliation_file, "r") as f:
            data = json.load(f)
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] File not found: {e.filename}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        console.print(f"[red]Error:[/red] Invalid JSON: {e}")
        sys.exit(1)
    summary = generate_reconciliation_summary(data)
    console.print(Panel(summary, title="Reconciliation Summary"))


@main.group()
def gstr1():
    """GSTR-1 generation and validation commands."""


@gstr1.command("generate")
@click.option("--sales-file", "-s", required=True, help="Path to sales data JSON file")
@click.option("--gstin", "-g", required=True, help="GSTIN of the supplier")
@click.option("--return-period", "-r", required=True, help="Return period (MMYYYY)")
@click.option("--output", "-o", help="Output file for GSTR-1 JSON")
def gstr1_generate_cmd(sales_file, gstin, return_period, output):
    """Generate GSTR-1 JSON from sales data."""
    gstin_clean = format_gstin(gstin)
    if not gstin_clean:
        console.print(f"[red]Error:[/red] Invalid GSTIN format: {gstin}")
        sys.exit(1)
    try:
        with open(sales_file, "r") as f:
            sales_data = json.load(f)
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] File not found: {e.filename}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        console.print(f"[red]Error:[/red] Invalid JSON: {e}")
        sys.exit(1)
    try:
        gstr1_result = generate_gstr1_json(sales_data, gstin_clean, return_period)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    output_path = output or f"gstr1_{return_period}.json"
    try:
        with open(output_path, "w") as f:
            json.dump(gstr1_result, f, indent=2)
        console.print(f"[green]GSTR-1 JSON generated: {output_path}[/green]")
    except IOError as e:
        console.print(f"[red]Error writing output:[/red] {e}")
        sys.exit(1)


@gstr1.command("validate")
@click.option("--gstr1-file", "-f", required=True, help="Path to GSTR-1 JSON file")
def gstr1_validate_cmd(gstr1_file):
    """Validate GSTR-1 JSON format."""
    try:
        with open(gstr1_file, "r") as f:
            gstr1_data = json.load(f)
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] File not found: {e.filename}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        console.print(f"[red]Error:[/red] Invalid JSON: {e}")
        sys.exit(1)
    errors = validate_gstr1_json(gstr1_data)
    if errors:
        console.print("[red]VALIDATION ERRORS:[/red]")
        for err in errors:
            console.print(f"  [yellow]✗[/yellow] {err}")
    else:
        console.print("[green]✓[/green] GSTR-1 JSON is valid!")


@gstr1.command("summary")
@click.option("--gstr1-file", "-f", required=True, help="Path to GSTR-1 JSON file")
def gstr1_summary_cmd(gstr1_file):
    """Show GSTR-1 summary."""
    try:
        with open(gstr1_file, "r") as f:
            gstr1_data = json.load(f)
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] File not found: {e.filename}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        console.print(f"[red]Error:[/red] Invalid JSON: {e}")
        sys.exit(1)
    summary = generate_gstr1_summary(gstr1_data)
    console.print(summary)


@main.group()
def gstr3b():
    """GSTR-3B generation and validation commands."""


@gstr3b.command("generate")
@click.option("--gstr1-file", "-f", required=True, help="Path to GSTR-1 JSON file")
@click.option("--output", "-o", help="Output file for GSTR-3B JSON")
def gstr3b_generate_cmd(gstr1_file, output):
    """Generate GSTR-3B summary from GSTR-1 data."""
    try:
        with open(gstr1_file, "r") as f:
            gstr1_data = json.load(f)
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] File not found: {e.filename}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        console.print(f"[red]Error:[/red] Invalid JSON: {e}")
        sys.exit(1)
    try:
        gstr3b_result = generate_gstr3b(gstr1_data)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    output_path = output or f"gstr3b_{gstr1_data.get('returnPeriod', 'unknown')}.json"
    try:
        with open(output_path, "w") as f:
            json.dump(gstr3b_result, f, indent=2)
        console.print(f"[green]GSTR-3B JSON generated: {output_path}[/green]")
    except IOError as e:
        console.print(f"[red]Error writing output:[/red] {e}")
        sys.exit(1)


@gstr3b.command("validate")
@click.option("--gstr3b-file", "-f", required=True, help="Path to GSTR-3B JSON file")
@click.option("--gstr1-file", "-g", help="Path to GSTR-1 JSON file (optional, for cross-validation)")
def gstr3b_validate_cmd(gstr3b_file, gstr1_file):
    """Validate GSTR-3B against GSTR-1."""
    try:
        with open(gstr3b_file, "r") as f:
            gstr3b_data = json.load(f)
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] File not found: {e.filename}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        console.print(f"[red]Error:[/red] Invalid JSON: {e}")
        sys.exit(1)
    gstr1_data = None
    if gstr1_file:
        try:
            with open(gstr1_file, "r") as f:
                gstr1_data = json.load(f)
        except FileNotFoundError:
            console.print(f"[red]Error:[/red] GSTR-1 file not found")
            sys.exit(1)
        except json.JSONDecodeError as e:
            console.print(f"[red]Error:[/red] Invalid JSON in GSTR-1: {e}")
            sys.exit(1)
    errors = validate_gstr3b(gstr3b_data, gstr1_data)
    if errors:
        console.print("[red]VALIDATION ERRORS:[/red]")
        for err in errors:
            console.print(f"  [yellow]✗[/yellow] {err}")
    else:
        console.print("[green]✓[/green] GSTR-3B is valid!")


@main.group()
def einvoice():
    """E-invoice generation and QR code commands."""


@einvoice.command("generate")
@click.option("--invoice-file", "-i", required=True, help="Path to invoice data JSON file")
@click.option("--output", "-o", help="Output file for e-invoice JSON")
def einvoice_generate_cmd(invoice_file, output):
    """Generate e-invoice JSON."""
    try:
        with open(invoice_file, "r") as f:
            invoice_data = json.load(f)
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] File not found: {e.filename}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        console.print(f"[red]Error:[/red] Invalid JSON: {e}")
        sys.exit(1)
    try:
        einvoice_result = generate_einvoice_json(invoice_data)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    output_path = output or f"einvoice_{invoice_data.get('docNo', 'unknown')}.json"
    try:
        with open(output_path, "w") as f:
            json.dump(einvoice_result, f, indent=2)
        console.print(f"[green]E-invoice JSON generated: {output_path}[/green]")
    except IOError as e:
        console.print(f"[red]Error writing output:[/red] {e}")
        sys.exit(1)


@einvoice.command("qr")
@click.option("--einvoice-file", "-f", required=True, help="Path to e-invoice JSON file")
@click.option("--output", "-o", default="qr_code.png", help="Output PNG file for QR code")
def einvoice_qr_cmd(einvoice_file, output):
    """Generate QR code for e-invoice."""
    try:
        with open(einvoice_file, "r") as f:
            einvoice_data = json.load(f)
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] File not found: {e.filename}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        console.print(f"[red]Error:[/red] Invalid JSON: {e}")
        sys.exit(1)
    try:
        qr_buf = generate_einvoice_qr(einvoice_data)
    except Exception as e:
        console.print(f"[red]Error generating QR code:[/red] {e}")
        sys.exit(1)
    try:
        with open(output, "wb") as f:
            f.write(qr_buf.read())
        console.print(f"[green]QR code saved: {output}[/green]")
    except IOError as e:
        console.print(f"[red]Error writing QR code:[/red] {e}")
        sys.exit(1)


@main.group()
def ewaybill():
    """E-way bill generation commands."""


@ewaybill.command("generate")
@click.option("--ewaybill-file", "-i", required=True, help="Path to e-way bill data JSON file")
@click.option("--output", "-o", help="Output file for e-way bill JSON")
def ewaybill_generate_cmd(ewaybill_file, output):
    """Generate e-way bill JSON."""
    try:
        with open(ewaybill_file, "r") as f:
            ewaybill_data = json.load(f)
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] File not found: {e.filename}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        console.print(f"[red]Error:[/red] Invalid JSON: {e}")
        sys.exit(1)
    try:
        ewaybill_result = generate_ewaybill_json(ewaybill_data)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    output_path = output or f"ewaybill_{ewaybill_data.get('docNo', 'unknown')}.json"
    try:
        with open(output_path, "w") as f:
            json.dump(ewaybill_result, f, indent=2)
        console.print(f"[green]E-way bill JSON generated: {output_path}[/green]")
    except IOError as e:
        console.print(f"[red]Error writing output:[/red] {e}")
        sys.exit(1)


@main.group()
def track():
    """Track upcoming GST due dates."""


@track.command("due-dates")
@click.option("--months", "-m", default=3, help="Number of months ahead to show (default: 3)")
def track_due_dates_cmd(months):
    """Show upcoming GST due dates."""
    try:
        months = int(months)
    except ValueError:
        console.print("[red]Error:[/red] Months must be a number")
        sys.exit(1)
    due_dates = get_upcoming_due_dates(months)
    result = pretty_due_dates(due_dates)
    console.print(result)


if __name__ == "__main__":
    main()
