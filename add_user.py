"""
======================================
  User add karne ka script
  Pehle PDF upload karo, phir user add karo
======================================
"""
import urllib.request, json, sys

BASE_URL = "https://secure-pdf-viewer.onrender.com"   # Render pe deploy ke baad yahan URL change karo
                                     # jaise: "https://secure-pdf-viewer.onrender.com"

def upload_pdf(pdf_path):
    """Step 1 — PDF Cloudinary pe upload karo"""
    import urllib.parse

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    boundary = "----FormBoundary7MA4YWxkTrZu0gW"
    filename  = pdf_path.split("\\")[-1].split("/")[-1]

    body  = f"--{boundary}\r\n"
    body += f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
    body += "Content-Type: application/pdf\r\n\r\n"
    body  = body.encode() + pdf_bytes + f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        f"{BASE_URL}/admin/upload-pdf",
        data    = body,
        headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    res  = urllib.request.urlopen(req)
    data = json.loads(res.read())
    print(f"\n PDF uploaded!")
    print(f"   Cloudinary ID: {data['cloudinary_id']}")
    print(f"   Total pages:   {data['total_pages']}")
    return data["cloudinary_id"], data["total_pages"]


def add_user(name, email, cloudinary_id, total_pages):
    """Step 2 — User add karo"""
    payload = json.dumps({
        "name":          name,
        "email":         email,
        "cloudinary_id": cloudinary_id,
        "total_pages":   total_pages
    }).encode()

    req = urllib.request.Request(
        f"{BASE_URL}/admin/add-user",
        data    = payload,
        headers = {"Content-Type": "application/json"}
    )
    res  = urllib.request.urlopen(req)
    data = json.loads(res.read())
    print(f"\n User added!")
    print(f"   Email:    {data['email']}")
    print(f"   Password: {data['password']}  ← Yeh user ko bhejo!")
    return data["password"]


if __name__ == "__main__":
    print("=" * 45)
    print("  SECURE PDF — User Setup")
    print("=" * 45)

    pdf_path = input("\n PDF file ka path daalo (jaise: E:\\secure_viewer\\pdfs\\doc.pdf): ").strip()
    cid, pages = upload_pdf(pdf_path)

    print("\n Ab user details daalo:")
    name  = input("   Name:  ").strip()
    email = input("   Email: ").strip()

    add_user(name, email, cid, pages)
    print("\n Done! Ab user login kar sakta hai.\n")
