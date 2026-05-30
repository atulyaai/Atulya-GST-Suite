import json
from datetime import datetime, date
from typing import List, Optional
from io import BytesIO

from atulya_gst_suite.utils import validate_gstin, split_tax, format_inr


def reconcile_gstr2a(purchase_register: List[dict], gstr2a_data: List[dict]) -> dict:
    matched = []
    unmatched_purchase = []
    unmatched_gstr2a = []
    purchase_by_key = {}
    for inv in purchase_register:
        key = (
            inv.get("gstin", "").strip().upper(),
            inv.get("invoice_number", "").strip().upper(),
        )
        purchase_by_key[key] = purchase_by_key.get(key, []) + [inv]
    gstr2a_by_key = {}
    for inv in gstr2a_data:
        key = (
            inv.get("gstin", "").strip().upper(),
            inv.get("invoice_number", "").strip().upper(),
        )
        gstr2a_by_key[key] = gstr2a_by_key.get(key, []) + [inv]
    for key, purchases in purchase_by_key.items():
        if key in gstr2a_by_key:
            gstr2a_invs = gstr2a_by_key[key]
            for p_inv in purchases:
                best_match = None
                for g_inv in gstr2a_invs:
                    if abs(p_inv.get("taxable_value", 0) - g_inv.get("taxable_value", 0)) < 0.01:
                        best_match = g_inv
                        break
                if best_match:
                    matched.append({
                        "purchase": p_inv,
                        "gstr2a": best_match,
                        "taxable_diff": p_inv.get("taxable_value", 0) - best_match.get("taxable_value", 0),
                        "tax_diff": p_inv.get("tax_amount", 0) - best_match.get("tax_amount", 0),
                    })
                    gstr2a_invs.remove(best_match)
                else:
                    unmatched_purchase.append(p_inv)
            if not gstr2a_invs:
                del gstr2a_by_key[key]
            else:
                gstr2a_by_key[key] = gstr2a_invs
        else:
            unmatched_purchase.extend(purchases)
    for remaining in gstr2a_by_key.values():
        unmatched_gstr2a.extend(remaining)
    purchase_total = sum(inv.get("taxable_value", 0) for inv in purchase_register)
    gstr2a_total = sum(inv.get("taxable_value", 0) for inv in gstr2a_data)
    matched_total = sum(m["purchase"].get("taxable_value", 0) for m in matched)
    return {
        "total_purchases": len(purchase_register),
        "total_gstr2a": len(gstr2a_data),
        "matched": matched,
        "matched_count": len(matched),
        "matched_value": matched_total,
        "unmatched_purchase": unmatched_purchase,
        "unmatched_purchase_count": len(unmatched_purchase),
        "unmatched_purchase_value": sum(inv.get("taxable_value", 0) for inv in unmatched_purchase),
        "unmatched_gstr2a": unmatched_gstr2a,
        "unmatched_gstr2a_count": len(unmatched_gstr2a),
        "unmatched_gstr2a_value": sum(inv.get("taxable_value", 0) for inv in unmatched_gstr2a),
        "purchase_total": purchase_total,
        "gstr2a_total": gstr2a_total,
        "difference": purchase_total - gstr2a_total,
        "match_rate": round(len(matched) / len(purchase_register) * 100, 2) if purchase_register else 0,
    }


def reconcile_gstr2b(purchase_register: List[dict], gstr2b_data: List[dict]) -> dict:
    return reconcile_gstr2a(purchase_register, gstr2b_data)


def generate_reconciliation_summary(report: dict) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append("RECONCILIATION SUMMARY")
    lines.append("=" * 60)
    lines.append(f"Total Purchase Invoices : {report['total_purchases']}")
    lines.append(f"Total GSTR-2A/2B Invoices: {report['total_gstr2a']}")
    lines.append(f"Matched                : {report['matched_count']} ({format_inr(report['matched_value'])})")
    lines.append(f"Match Rate             : {report['match_rate']}%")
    lines.append(f"Unmatched in Purchase  : {report['unmatched_purchase_count']} ({format_inr(report['unmatched_purchase_value'])})")
    lines.append(f"Unmatched in GSTR-2A/B : {report['unmatched_gstr2a_count']} ({format_inr(report['unmatched_gstr2a_value'])})")
    lines.append(f"Difference (Purchase - GSTR): {format_inr(report['difference'])}")
    lines.append("=" * 60)
    if report["unmatched_purchase"]:
        lines.append("\nUNMATCHED PURCHASE INVOICES:")
        for inv in report["unmatched_purchase"]:
            lines.append(f"  {inv.get('invoice_number','N/A')} | {inv.get('gstin','N/A')} | {format_inr(inv.get('taxable_value',0))}")
    if report["unmatched_gstr2a"]:
        lines.append("\nUNMATCHED GSTR-2A/2B INVOICES:")
        for inv in report["unmatched_gstr2a"]:
            lines.append(f"  {inv.get('invoice_number','N/A')} | {inv.get('gstin','N/A')} | {format_inr(inv.get('taxable_value',0))}")
    return "\n".join(lines)


def generate_gstr1_json(sales_data: List[dict], gstin: str, return_period: str) -> dict:
    if not validate_gstin(gstin):
        raise ValueError(f"Invalid GSTIN: {gstin}")
    b2b = []
    b2cs = []
    nil = {"nil_rated": [], "exempted": [], "non_gst": []}
    for inv in sales_data:
        invoice_type = inv.get("type", "b2b").lower()
        if invoice_type == "b2b":
            items = []
            for item in inv.get("items", []):
                items.append({
                    "hsn": str(item.get("hsn", "")),
                    "taxableValue": item.get("taxable_value", 0),
                    "rate": item.get("rate", 0),
                    "cgst": item.get("cgst", 0),
                    "sgst": item.get("sgst", 0),
                    "igst": item.get("igst", 0),
                    "cess": item.get("cess", 0),
                })
            b2b.append({
                "gstin": inv.get("buyer_gstin", ""),
                "invoiceNumber": inv.get("invoice_number", ""),
                "invoiceDate": inv.get("invoice_date", ""),
                "invoiceValue": inv.get("invoice_value", 0),
                "placeOfSupply": inv.get("place_of_supply", ""),
                "items": items,
            })
        elif invoice_type == "b2c":
            b2cs.append({
                "invoiceNumber": inv.get("invoice_number", ""),
                "invoiceDate": inv.get("invoice_date", ""),
                "invoiceValue": inv.get("invoice_value", 0),
                "placeOfSupply": inv.get("place_of_supply", ""),
                "rate": inv.get("rate", 0),
                "taxableValue": inv.get("taxable_value", 0),
                "cgst": inv.get("cgst", 0),
                "sgst": inv.get("sgst", 0),
                "igst": inv.get("igst", 0),
            })
        elif invoice_type == "nil":
            nil["nil_rated"].append({
                "invoiceNumber": inv.get("invoice_number", ""),
                "invoiceDate": inv.get("invoice_date", ""),
                "invoiceValue": inv.get("invoice_value", 0),
            })
        elif invoice_type == "exempted":
            nil["exempted"].append({
                "invoiceNumber": inv.get("invoice_number", ""),
                "invoiceDate": inv.get("invoice_date", ""),
                "invoiceValue": inv.get("invoice_value", 0),
            })
        elif invoice_type == "non_gst":
            nil["non_gst"].append({
                "invoiceNumber": inv.get("invoice_number", ""),
                "invoiceDate": inv.get("invoice_date", ""),
                "invoiceValue": inv.get("invoice_value", 0),
            })
    gstr1 = {
        "gstin": gstin,
        "returnPeriod": return_period,
        "version": "GST3.1.2",
        "b2b": b2b,
        "b2cs": b2cs,
        "nil": nil,
    }
    if sales_data and any(inv.get("type", "").lower() in ("cdnr", "cdnr_regular") for inv in sales_data):
        cdnr = []
        for inv in sales_data:
            if inv.get("type", "").lower() in ("cdnr", "cdnr_regular"):
                items = []
                for item in inv.get("items", []):
                    items.append({
                        "hsn": str(item.get("hsn", "")),
                        "taxableValue": item.get("taxable_value", 0),
                        "rate": item.get("rate", 0),
                        "cgst": item.get("cgst", 0),
                        "sgst": item.get("sgst", 0),
                        "igst": item.get("igst", 0),
                    })
                cdnr.append({
                    "gstin": inv.get("buyer_gstin", ""),
                    "invoiceNumber": inv.get("invoice_number", ""),
                    "invoiceDate": inv.get("invoice_date", ""),
                    "invoiceValue": inv.get("invoice_value", 0),
                    "reason": inv.get("reason", ""),
                    "items": items,
                })
        gstr1["cdnr"] = cdnr
    hsn_summary = {}
    for inv in sales_data:
        for item in inv.get("items", []):
            hsn = str(item.get("hsn", ""))
            if hsn:
                if hsn not in hsn_summary:
                    hsn_summary[hsn] = {
                        "hsn": hsn,
                        "description": item.get("description", ""),
                        "uqc": item.get("uqc", "NOS"),
                        "quantity": 0,
                        "taxableValue": 0,
                        "cgst": 0, "sgst": 0, "igst": 0,
                        "cess": 0,
                    }
                hsn_summary[hsn]["quantity"] += item.get("quantity", 0)
                hsn_summary[hsn]["taxableValue"] += item.get("taxable_value", 0)
                hsn_summary[hsn]["cgst"] += item.get("cgst", 0)
                hsn_summary[hsn]["sgst"] += item.get("sgst", 0)
                hsn_summary[hsn]["igst"] += item.get("igst", 0)
                hsn_summary[hsn]["cess"] += item.get("cess", 0)
    if hsn_summary:
        gstr1["hsnSummary"] = list(hsn_summary.values())
    doc_issue = {"documents": len(sales_data), "cancelled": 0}
    credit_notes = [inv for inv in sales_data if inv.get("type", "").lower() in ("cdnr", "cdnr_regular")]
    if credit_notes:
        doc_issue["creditNotes"] = len(credit_notes)
    gstr1["docIssue"] = doc_issue
    return gstr1


def validate_gstr1_json(gstr1_data: dict) -> List[str]:
    errors = []
    required_fields = ["gstin", "returnPeriod", "version"]
    for field in required_fields:
        if field not in gstr1_data:
            errors.append(f"Missing required field: {field}")
    gstin = gstr1_data.get("gstin", "")
    if gstin and not validate_gstin(gstin):
        errors.append(f"Invalid GSTIN format: {gstin}")
    return_period = gstr1_data.get("returnPeriod", "")
    if return_period and not (len(return_period) == 6 and return_period.isdigit()):
        errors.append(f"Invalid return period format (expected MMMYYY): {return_period}")
    if "b2b" in gstr1_data:
        for idx, inv in enumerate(gstr1_data["b2b"]):
            if not inv.get("gstin"):
                errors.append(f"b2b[{idx}]: Missing buyer GSTIN")
            if not inv.get("invoiceNumber"):
                errors.append(f"b2b[{idx}]: Missing invoice number")
            for item_idx, item in enumerate(inv.get("items", [])):
                if not item.get("hsn"):
                    errors.append(f"b2b[{idx}].items[{item_idx}]: Missing HSN code")
    if "b2cs" in gstr1_data:
        for idx, inv in enumerate(gstr1_data["b2cs"]):
            if not inv.get("invoiceNumber"):
                errors.append(f"b2cs[{idx}]: Missing invoice number")
    return errors


def generate_gstr1_summary(gstr1_data: dict) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append("GSTR-1 SUMMARY")
    lines.append("=" * 60)
    lines.append(f"GSTIN        : {gstr1_data.get('gstin', 'N/A')}")
    lines.append(f"Return Period: {gstr1_data.get('returnPeriod', 'N/A')}")
    lines.append(f"Version      : {gstr1_data.get('version', 'N/A')}")
    lines.append("")
    b2b = gstr1_data.get("b2b", [])
    b2cs = gstr1_data.get("b2cs", [])
    cdnr = gstr1_data.get("cdnr", [])
    nil_data = gstr1_data.get("nil", {})
    lines.append(f"B2B Invoices     : {len(b2b)}")
    lines.append(f"B2C Invoices     : {len(b2cs)}")
    lines.append(f"Credit/Debit Notes: {len(cdnr)}")
    lines.append(f"Nil/Exempt/NON-GST: {len(nil_data.get('nil_rated',[])) + len(nil_data.get('exempted',[])) + len(nil_data.get('non_gst',[]))}")
    total_taxable = sum(inv.get("invoiceValue", 0) for inv in b2b) + sum(inv.get("taxableValue", 0) for inv in b2cs)
    total_cgst = sum(item.get("cgst", 0) for inv in b2b for item in inv.get("items", [])) + sum(inv.get("cgst", 0) for inv in b2cs)
    total_sgst = sum(item.get("sgst", 0) for inv in b2b for item in inv.get("items", [])) + sum(inv.get("sgst", 0) for inv in b2cs)
    total_igst = sum(item.get("igst", 0) for inv in b2b for item in inv.get("items", [])) + sum(inv.get("igst", 0) for inv in b2cs)
    lines.append("")
    lines.append("TAX SUMMARY:")
    lines.append(f"  Total Taxable Value: {format_inr(total_taxable)}")
    lines.append(f"  Total CGST         : {format_inr(total_cgst)}")
    lines.append(f"  Total SGST         : {format_inr(total_sgst)}")
    lines.append(f"  Total IGST         : {format_inr(total_igst)}")
    lines.append(f"  Total Tax          : {format_inr(total_cgst + total_sgst + total_igst)}")
    lines.append("=" * 60)
    return "\n".join(lines)


def generate_gstr3b(gstr1_data: dict, sales_data: Optional[List[dict]] = None) -> dict:
    b2b = gstr1_data.get("b2b", [])
    b2cs = gstr1_data.get("b2cs", [])
    cdnr = gstr1_data.get("cdnr", [])
    nil_data = gstr1_data.get("nil", {})
    inter_state = {"supplies": [], "taxable_value": 0, "cgst": 0, "sgst": 0, "igst": 0}
    intra_state = {"supplies": [], "taxable_value": 0, "cgst": 0, "sgst": 0, "igst": 0}
    for inv in b2b:
        pos = inv.get("placeOfSupply", "")
        is_inter = pos != "" and gstr1_data.get("gstin", "")[:2] != pos
        for item in inv.get("items", []):
            tv = item.get("taxableValue", 0)
            cgst = item.get("cgst", 0)
            sgst = item.get("sgst", 0)
            igst = item.get("igst", 0)
            if is_inter:
                inter_state["taxable_value"] += tv
                inter_state["igst"] += igst
            else:
                intra_state["taxable_value"] += tv
                intra_state["cgst"] += cgst
                intra_state["sgst"] += sgst
    for inv in b2cs:
        pos = inv.get("placeOfSupply", "")
        is_inter = pos != "" and gstr1_data.get("gstin", "")[:2] != pos
        tv = inv.get("taxableValue", 0)
        cgst = inv.get("cgst", 0)
        sgst = inv.get("sgst", 0)
        igst = inv.get("igst", 0)
        if is_inter:
            inter_state["taxable_value"] += tv
            inter_state["igst"] += igst
        else:
            intra_state["taxable_value"] += tv
            intra_state["cgst"] += cgst
            intra_state["sgst"] += sgst
    total_igst = inter_state["igst"]
    total_cgst = intra_state["cgst"]
    total_sgst = intra_state["sgst"]
    total_taxable = inter_state["taxable_value"] + intra_state["taxable_value"]
    cdnr_total = sum(inv.get("invoiceValue", 0) for inv in cdnr)
    itc_available = total_cgst + total_sgst + total_igst
    gstr3b = {
        "gstin": gstr1_data.get("gstin", ""),
        "returnPeriod": gstr1_data.get("returnPeriod", ""),
        "version": "GST3.1.2",
        "outwardSupplies": {
            "interState": {
                "taxableValue": round(inter_state["taxable_value"], 2),
                "igst": round(total_igst, 2),
            },
            "intraState": {
                "taxableValue": round(intra_state["taxable_value"], 2),
                "cgst": round(total_cgst, 2),
                "sgst": round(total_sgst, 2),
            },
            "nilRated": {
                "nilRated": len(nil_data.get("nil_rated", [])),
                "exempted": len(nil_data.get("exempted", [])),
                "nonGst": len(nil_data.get("non_gst", [])),
            },
            "totalTaxableValue": round(total_taxable, 2),
            "totalCgst": round(total_cgst, 2),
            "totalSgst": round(total_sgst, 2),
            "totalIgst": round(total_igst, 2),
            "totalTax": round(total_cgst + total_sgst + total_igst, 2),
        },
        "creditDebitNotes": {
            "count": len(cdnr),
            "totalValue": round(cdnr_total, 2),
        },
        "itc": {
            "itcAvailable": round(itc_available, 2),
            "itcClaimed": 0,
        },
    }
    return gstr3b


def validate_gstr3b(gstr3b_data: dict, gstr1_data: Optional[dict] = None) -> List[str]:
    errors = []
    required_fields = ["gstin", "returnPeriod", "outwardSupplies"]
    for field in required_fields:
        if field not in gstr3b_data:
            errors.append(f"Missing required field: {field}")
    if gstr1_data:
        gstr3b_taxable = gstr3b_data.get("outwardSupplies", {}).get("totalTaxableValue", 0)
        b2b = gstr1_data.get("b2b", [])
        b2cs = gstr1_data.get("b2cs", [])
        gstr1_taxable = sum(inv.get("invoiceValue", 0) for inv in b2b) + sum(inv.get("taxableValue", 0) for inv in b2cs)
        gstr3b_taxable = gstr3b_data.get("outwardSupplies", {}).get("totalTaxableValue", 0)
        if abs(gstr3b_taxable - gstr1_taxable) > 0.01:
            errors.append(f"GSTR-3B taxable value ({gstr3b_taxable}) does not match GSTR-1 ({gstr1_taxable})")
    return errors


def generate_einvoice_json(invoice_data: dict) -> dict:
    required = ["sellerGstin", "buyerGstin", "docNo", "docDt", "items"]
    for field in required:
        if field not in invoice_data:
            raise ValueError(f"Missing required field for e-invoice: {field}")
    seller_gstin = invoice_data["sellerGstin"]
    buyer_gstin = invoice_data["buyerGstin"]
    if not validate_gstin(seller_gstin):
        raise ValueError(f"Invalid seller GSTIN: {seller_gstin}")
    if not validate_gstin(buyer_gstin):
        raise ValueError(f"Invalid buyer GSTIN: {buyer_gstin}")
    items = []
    total_taxable = 0
    total_cgst = 0
    total_sgst = 0
    total_igst = 0
    total_cess = 0
    for idx, item in enumerate(invoice_data.get("items", [])):
        serial_no = str(idx + 1)
        taxable = item.get("taxableValue", 0)
        rate = item.get("rate", 0)
        is_inter = invoice_data.get("isInterState", False)
        tax_split = split_tax(taxable, rate, is_inter)
        cgst = tax_split["cgst"]
        sgst = tax_split["sgst"]
        igst = tax_split["igst"]
        total_cgst += cgst
        total_sgst += sgst
        total_igst += igst
        total_taxable += taxable
        total_cess += item.get("cess", 0)
        items.append({
            "SlNo": serial_no,
            "PrdDesc": item.get("description", ""),
            "IsServc": item.get("isService", "N"),
            "HsnCd": str(item.get("hsn", "")),
            "Qty": item.get("quantity", 1),
            "Unit": item.get("unit", "NOS"),
            "UnitPrice": round(item.get("unitPrice", 0), 2),
            "TotAmt": round(item.get("totalAmount", taxable), 2),
            "AssAmt": round(taxable, 2),
            "GstRt": rate,
            "CgstAmt": round(cgst, 2),
            "SgstAmt": round(sgst, 2),
            "IgstAmt": round(igst, 2),
            "CesAmt": round(item.get("cess", 0), 2),
            "TotItemVal": round(taxable + cgst + sgst + igst + item.get("cess", 0), 2),
        })
    total_invoice_value = total_taxable + total_cgst + total_sgst + total_igst + total_cess
    einvoice = {
        "Version": "1.1",
        "TranDtls": {
            "TaxSch": "GST",
            "SupTyp": invoice_data.get("supplyType", "B2B"),
            "IgstOnIntra": "N",
        },
        "DocDtls": {
            "Typ": "INV",
            "No": invoice_data["docNo"],
            "Dt": invoice_data["docDt"],
        },
        "SellerDtls": {
            "Gstin": seller_gstin,
            "LglNm": invoice_data.get("sellerName", ""),
            "Addr1": invoice_data.get("sellerAddress1", ""),
            "Addr2": invoice_data.get("sellerAddress2", ""),
            "Loc": invoice_data.get("sellerLocation", ""),
            "Pin": invoice_data.get("sellerPin", ""),
            "Stcd": invoice_data.get("sellerStateCode", ""),
        },
        "BuyerDtls": {
            "Gstin": buyer_gstin,
            "LglNm": invoice_data.get("buyerName", ""),
            "Addr1": invoice_data.get("buyerAddress1", ""),
            "Addr2": invoice_data.get("buyerAddress2", ""),
            "Loc": invoice_data.get("buyerLocation", ""),
            "Pin": invoice_data.get("buyerPin", ""),
            "Stcd": invoice_data.get("buyerStateCode", ""),
        },
        "ItemList": items,
        "ValDtls": {
            "AssVal": round(total_taxable, 2),
            "CgstVal": round(total_cgst, 2),
            "SgstVal": round(total_sgst, 2),
            "IgstVal": round(total_igst, 2),
            "CesVal": round(total_cess, 2),
            "TotInvVal": round(total_invoice_value, 2),
        },
    }
    return einvoice


def generate_einvoice_qr(einvoice_data: dict) -> BytesIO:
    import qrcode
    qr_payload = {
        "Version": einvoice_data.get("Version", "1.1"),
        "Gstin": einvoice_data.get("SellerDtls", {}).get("Gstin", ""),
        "DocNo": einvoice_data.get("DocDtls", {}).get("No", ""),
        "DocDt": einvoice_data.get("DocDtls", {}).get("Dt", ""),
        "TotInvVal": einvoice_data.get("ValDtls", {}).get("TotInvVal", 0),
        "ItemCnt": len(einvoice_data.get("ItemList", [])),
    }
    qr_text = json.dumps(qr_payload, separators=(",", ":"))
    qr = qrcode.QRCode(version=2, box_size=10, border=1)
    qr.add_data(qr_text)
    qr.make(fit=True)
    img = qr.make_image(fill="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def generate_ewaybill_json(ewaybill_data: dict) -> dict:
    required = ["docNo", "docDt", "fromGstin", "fromAddress", "toGstin", "toAddress", "items"]
    for field in required:
        if field not in ewaybill_data:
            raise ValueError(f"Missing required field for e-way bill: {field}")
    items = []
    total_value = 0
    for idx, item in enumerate(ewaybill_data.get("items", [])):
        taxable = item.get("taxableValue", 0)
        total_value += taxable
        items.append({
            "SlNo": idx + 1,
            "ProductName": item.get("description", ""),
            "HsnCd": str(item.get("hsn", "")),
            "Quantity": item.get("quantity", 1),
            "Uqc": item.get("unit", "NOS"),
        })
    ewaybill = {
        "Version": "1.0",
        "DocDtls": {
            "No": ewaybill_data["docNo"],
            "Dt": ewaybill_data["docDt"],
        },
        "FromDtls": {
            "Gstin": ewaybill_data["fromGstin"],
            "Address": ewaybill_data["fromAddress"],
            "StateCode": ewaybill_data.get("fromStateCode", ""),
        },
        "ToDtls": {
            "Gstin": ewaybill_data["toGstin"],
            "Address": ewaybill_data["toAddress"],
            "StateCode": ewaybill_data.get("toStateCode", ""),
        },
        "ItemList": items,
        "TotalValue": round(total_value, 2),
        "Distance": ewaybill_data.get("distance", 0),
        "TransporterName": ewaybill_data.get("transporterName", ""),
        "TransporterDocNo": ewaybill_data.get("transporterDocNo", ""),
        "TransporterDocDt": ewaybill_data.get("transporterDocDt", ""),
        "VehicleNo": ewaybill_data.get("vehicleNo", ""),
    }
    return ewaybill


DUE_DATES = {
    1: {"gstr1": 11, "gstr3b": 20},
    2: {"gstr1": 11, "gstr3b": 20},
    3: {"gstr1": 11, "gstr3b": 20},
    4: {"gstr1": 11, "gstr3b": 20},
    5: {"gstr1": 11, "gstr3b": 20},
    6: {"gstr1": 11, "gstr3b": 20},
    7: {"gstr1": 11, "gstr3b": 20},
    8: {"gstr1": 11, "gstr3b": 20},
    9: {"gstr1": 11, "gstr3b": 20},
    10: {"gstr1": 11, "gstr3b": 20},
    11: {"gstr1": 11, "gstr3b": 20},
    12: {"gstr1": 11, "gstr3b": 20},
}


def get_upcoming_due_dates(months_ahead: int = 3) -> List[dict]:
    today = date.today()
    current_month = today.month
    current_year = today.year
    results = []
    for offset in range(months_ahead + 1):
        m = current_month + offset
        y = current_year
        while m > 12:
            m -= 12
            y += 1
        month_name = datetime(y, m, 1).strftime("%B")
        period = f"{m:02d}{y}"
        due_info = DUE_DATES.get(m, {"gstr1": 11, "gstr3b": 20})
        gstr1_due = date(y, m, due_info["gstr1"])
        gstr3b_due = date(y, m, due_info["gstr3b"])
        gstr1_status = "OVERDUE" if gstr1_due < today else "PASSED" if gstr1_due == today else "UPCOMING"
        gstr3b_status = "OVERDUE" if gstr3b_due < today else "PASSED" if gstr3b_due == today else "UPCOMING"
        results.append({
            "period": period,
            "month": month_name,
            "year": y,
            "gstr1_due": gstr1_due.isoformat(),
            "gstr1_day": due_info["gstr1"],
            "gstr1_status": gstr1_status,
            "gstr3b_due": gstr3b_due.isoformat(),
            "gstr3b_day": due_info["gstr3b"],
            "gstr3b_status": gstr3b_status,
        })
    return results


def pretty_due_dates(due_dates: List[dict]) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append("UPCOMING GST DUE DATES")
    lines.append("=" * 60)
    today = date.today()
    for dd in due_dates:
        lines.append("")
        lines.append(f"{dd['month']} {dd['year']} (Period: {dd['period']})")
        lines.append(f"  GSTR-1  Due: {dd['gstr1_due']} (Day {dd['gstr1_day']}) [{dd['gstr1_status']}]")
        lines.append(f"  GSTR-3B Due: {dd['gstr3b_due']} (Day {dd['gstr3b_day']}) [{dd['gstr3b_status']}]")
        gstr1_dt = date.fromisoformat(dd['gstr1_due'])
        gstr3b_dt = date.fromisoformat(dd['gstr3b_due'])
        if gstr1_dt >= today:
            lines.append(f"  GSTR-1: {(gstr1_dt - today).days} days away")
        if gstr3b_dt >= today:
            lines.append(f"  GSTR-3B: {(gstr3b_dt - today).days} days away")
    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)
