import os

def run(context: dict):
    print("[📈] Optimizing SEO for page content...")
    site_dir = context.get("html_dir", "public")
    output = []

    for fname in os.listdir(site_dir):
        if fname.endswith(".html"):
            path = os.path.join(site_dir, fname)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            if "<meta name=\"description\"" not in content:
                content = content.replace(
                    "<head>",
                    "<head>\n<meta name=\"description\" content=\"AI Roofing Intelligence by MyRoofGenius\">"
                )
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                output.append(fname)

    print(f"[✅] SEO tags injected into {len(output)} files.")
