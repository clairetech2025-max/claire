import requests

def teach(text, domain):
    requests.post(
        "http://127.0.0.1:8081/ingest",
        json={"text": text, "domain": domain}
    )

# LAW
teach("The Constitution is the supreme law of the United States.", "law")
teach("Due process protects individuals from arbitrary government action.", "law")
teach("42 U.S.C. § 1983 allows lawsuits for constitutional violations.", "law")

# SCIENCE
teach("The scientific method involves hypothesis, experimentation, and validation.", "science")
teach("Energy cannot be created or destroyed, only transformed.", "science")

# FINTECH
teach("FinTech combines finance and technology to improve financial services.", "fintech")
teach("APIs allow financial systems to communicate securely and efficiently.", "fintech")

# CRYPTO
teach("Bitcoin is a decentralized digital currency operating on a blockchain.", "crypto")
teach("Private keys control ownership of cryptocurrency assets.", "crypto")

print("Claire domain knowledge loaded.")
