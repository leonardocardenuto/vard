"""Compare real foreground push receipts without printing credentials or tokens."""
import argparse
import getpass
import json
import math
import os
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path

import requests


def summarize(rows):
    result = {}
    for provider in ("onesignal", "fcm"):
        sent = [row for row in rows if row["provider"] == provider]
        valid = [row for row in sent if row.get("receipt_source") == "foreground"
                 and row.get("status") == "received" and row.get("attempts") == 1]
        metrics = {}
        for key in ("queue", "provider_request", "confirmation", "send_to_confirmation"):
            values = [row["timing_ms"][key] for row in valid if row["timing_ms"].get(key) is not None]
            metrics[key] = ({"mean_ms": round(statistics.mean(values)), "median_ms": statistics.median(values),
                             "p95_ms": sorted(values)[math.ceil(len(values) * .95) - 1], "min_ms": min(values),
                             "max_ms": max(values)} if values else None)
        result[provider] = {"sent": len(sent), "foreground_single_attempt": len(valid),
                            "excluded": len(sent) - len(valid), "metrics": metrics}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--email", required=True)
    parser.add_argument("--installation", required=True)
    parser.add_argument("--samples", type=int, default=20, help="Measured samples per provider (1..100)")
    parser.add_argument("--warmup", type=int, default=2, help="Unmeasured warm-up sends per provider (1..10)")
    parser.add_argument("--providers", nargs="+", choices=("fcm", "onesignal"), default=["onesignal", "fcm"])
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--output", default="var/push-benchmark-warm.json")
    args = parser.parse_args()
    if not 1 <= args.samples <= 100 or not 1 <= args.warmup <= 10 or args.timeout <= 0:
        parser.error("Use 1..100 samples, 1..10 warm-ups and a positive timeout")
    if not args.base_url.startswith("https://") and not args.base_url.startswith(("http://127.0.0.1:", "http://localhost:")):
        parser.error("Use HTTPS outside localhost")
    password = os.environ.get("PUSH_TEST_PASSWORD") or getpass.getpass("Senha da conta de teste: ")
    session = requests.Session()
    base = args.base_url.rstrip("/")
    response = session.post(f"{base}/auth/login", json={"email": args.email, "password": password}, timeout=15)
    response.raise_for_status()
    session.headers["Authorization"] = "Bearer " + response.json()["access_token"]
    rows = []
    warmup_rows = []
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    def save_report(complete=False):
        report = {"measured_at": datetime.now(UTC).isoformat(), "complete": complete,
                  "context": "foreground; server timestamps; ACK includes callback/network/DB commit, not exact Android display time",
                  "method": {"samples_per_provider": args.samples, "warmup_per_provider": args.warmup,
                             "providers": args.providers, "order": "alternating forward/reverse", "identical_title_and_body": True,
                             "primary_metric": "send_to_confirmation (queue excluded)",
                             "percentile": "nearest-rank p95"},
                  "summary": summarize(rows), "warmup_deliveries": warmup_rows, "deliveries": rows}
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return report

    print("Mantenha o app aberto em primeiro plano; toques não entram na média.", flush=True)
    for index in range(args.warmup + args.samples):
        warming = index < args.warmup
        # Alternate order so queue position does not consistently favor one provider.
        providers = args.providers if index % 2 == 0 else list(reversed(args.providers))
        for provider in providers:
            deadline = time.monotonic() + 90
            while True:
                response = session.post(f"{base}/push/test", json={"provider": provider,
                    "installation_id": args.installation, "benchmark": True}, timeout=15)
                if response.status_code != 429 or time.monotonic() > deadline:
                    break
                print("Respeitando limite de testes: aguardando 5 s…", flush=True)
                time.sleep(5)
            response.raise_for_status()
            delivery_id = response.json()["delivery_id"]
            deadline = time.monotonic() + args.timeout
            while True:
                response = session.get(f"{base}/push/deliveries/{delivery_id}", timeout=15)
                response.raise_for_status()
                row = response.json()
                if row["status"] in ("received", "failed", "cancelled", "expired") or time.monotonic() >= deadline:
                    break
                time.sleep(0.25)
            row['pair'] = index + 1 if warming else index - args.warmup + 1
            (warmup_rows if warming else rows).append(row)
            save_report()
            phase = 'Aquecimento' if warming else 'Medição'
            print(f'{phase} {provider} #{row["pair"]}: {row["status"]}, origem={row["receipt_source"]}, ms={row["timing_ms"]}', flush=True)
            if warming and (row['status'] != 'received' or row['receipt_source'] != 'foreground' or row['attempts'] != 1):
                raise SystemExit('Aquecimento sem confirmação automática: verifique o app antes de medir.')
    report = save_report(complete=True)
    print(json.dumps(report["summary"], indent=2), flush=True)
    print(f"Relatório: {output}")


if __name__ == "__main__":
    main()
