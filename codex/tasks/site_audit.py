import subprocess

def run(context: dict):
    print("[🧪] Running Lighthouse audit on live site...")
    url = context.get("site_url", "https://myroofgenius.vercel.app")
    report_path = "lighthouse-report.html"

    subprocess.run([
        "npx", "lighthouse", url,
        "--output", "html",
        "--output-path", report_path,
        "--quiet"
    ])

    print(f"[📄] Audit complete. Report saved to {report_path}")
